"""Frozen point-pilot runner. Real CLI always requires separate human approval."""
import json
import platform
from pathlib import Path
import numpy as np
import r0_preparation as r0

ACTION = 'R0_conditional_point_pilot'


def runtime_fingerprint():
    import pyxlsb
    return dict(python=platform.python_version(), numpy=np.__version__, pyxlsb=pyxlsb.__version__,
                direct_package_entry_sha256={
                    'numpy':r0.sha256(np.__file__), 'pyxlsb':r0.sha256(pyxlsb.__file__)})


def contract(config, references, codes):
    return dict(config_sha256=r0.digest(config), references_sha256=r0.digest(references),
                code_manifest_sha256=r0.digest(codes))


def authorize(approval, config, references, codes, *, domain='real', action=ACTION):
    if domain not in ('real', 'synthetic_fixture'):
        raise PermissionError('unknown domain')
    if not isinstance(approval, dict) or approval.get('status') != 'Approved':
        raise PermissionError('missing concrete approval')
    if approval.get('domain') != domain or approval.get('permitted_action') != action or action != ACTION:
        raise PermissionError('domain/action mismatch')
    ids = [r['reference_id'] for r in references]
    if approval.get('reference_ids') != ids or len(set(ids)) != len(ids):
        raise PermissionError('reference scope mismatch')
    people = approval.get('approvers', [])
    if (len(people) != 2 or any(not isinstance(p, dict) or not p.get('name', '').strip()
                              or not p.get('confirmed_at', '').strip() for p in people)
            or len({p['name'].strip() for p in people}) != 2
            or not approval.get('approval_id')):
        raise PermissionError('two explicit human confirmations required')
    if approval.get('contract') != contract(config, references, codes):
        raise PermissionError('approved version differs')
    if approval.get('permitted_uses') != config['reference_strata']:
        raise PermissionError('reference uses differ')
    return True  # Structural checks only; authenticity is a human responsibility.


def checked_code_manifest(codes):
    folder = Path(__file__).resolve().parent
    if Path(r0.__file__).resolve() != folder/'r0_preparation.py':
        raise PermissionError('unexpected imported dependency')
    expected_names = {'r0_runner.py', 'r0_preparation.py'}
    if set(codes['files']) != expected_names:
        raise PermissionError('incomplete executable dependency manifest')
    for name, expected in codes['files'].items():
        if r0.sha256(folder/name) != expected:
            raise PermissionError('code bytes changed: '+name)
    versions = codes['runtime']
    if versions != runtime_fingerprint():
        raise PermissionError('runtime version differs from frozen manifest')


def sample_two(eligible, seed, region_ordinal):
    """C-order eligible positions; independent PCG64 per seed/region ordinal.

    region_ordinal is index in lexicographically sorted frozen reference IDs.
    This function receives qualification only, never reference intensities.
    """
    valid = np.asarray(eligible)
    if valid.ndim != 2 or valid.dtype != np.bool_:
        raise ValueError('boolean core eligibility required')
    if type(seed) is not int or type(region_ordinal) is not int or min(seed, region_ordinal) < 0:
        raise ValueError('nonnegative integer seed/ordinal required')
    flat = np.flatnonzero(valid.ravel(order='C'))
    if len(flat) < 2:
        raise ValueError('need two eligible core positions')
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, region_ordinal])))
    selected = rng.choice(flat, size=2, replace=False)
    return [list(map(int, np.unravel_index(int(i), valid.shape, order='C'))) for i in selected]


def evaluate(estimate, reference, requested, t, w, info):
    e, y = np.asarray(estimate), np.asarray(reference)
    mask = np.asarray(requested)
    if e.shape != y.shape or mask.shape != y.shape or mask.dtype != np.bool_:
        raise ValueError('evaluation shape/mask')
    if not np.isfinite(y[mask]).all():
        raise ValueError('requested reference must be finite')
    resolved = mask & np.isfinite(e)
    count, done = int(mask.sum()), int(resolved.sum())
    errors = abs(e[resolved]-y[resolved])
    details=[]
    supports={tuple(s['target']):s for s in info['supports']}
    for i,j in np.argwhere(mask):
        supported=bool(resolved[i,j]); source=supports.get((int(i),int(j)))
        details.append(dict(row=int(i),column=int(j),time_s=float(t[i]),wavelength_nm=float(w[j]),
                            resolved=supported,reason=None if supported else 'no_admissible_two_sided_support_within_limits',
                            reference=float(y[i,j]),estimate=float(e[i,j]) if supported else None,
                            support=source,used_estimated_support=bool(info['used_estimated_support'][i,j]) if supported else None))
    return dict(requested=count,resolved=done,unresolved=count-done,coverage=done/count if count else None,
                coverage_gate_passed=(done==count) if count else None,
                MAE=float(errors.mean()) if done else None,
                RMSE=float(np.sqrt(np.mean(errors**2))) if done else None,
                p95=float(np.quantile(errors,.95)) if done else None,
                max=float(errors.max()) if done else None,
                estimated_support_count=sum(d['used_estimated_support'] is True for d in details),
                estimated_support_fraction=sum(d['used_estimated_support'] is True for d in details)/done if done else None,
                points=details)


def summarize(records):
    # Validate BEFORE combining rows: short and long ledgers must not cancel.
    for record in records:
        if len(record['points']) != record['requested']:
            raise ValueError('per-record point ledger does not match requested denominator')
    def one(rows):
        n=sum(r['requested'] for r in rows);d=sum(r['resolved'] for r in rows)
        positions=[(r['reference_id'],p['row'],p['column']) for r in rows for p in r['points']]
        if len(positions)!=n:
            raise ValueError('point ledger does not match requested denominator')
        counts={key:positions.count(key) for key in set(positions)}
        return dict(requested=n,resolved=d,unresolved=n-d,coverage=d/n if n else None,
                    coverage_gate_passed=(d==n) if n else None,
                    unique_requested_positions=len(counts), repeated_request_occurrences=n-len(counts),
                    positions_requested_more_than_once=sum(v>1 for v in counts.values()),
                    repeat_definition='key=(reference_id,loaded_row,loaded_column); includes nested k, seeds and orders within this grouping',
                    interpretation='repeated recovery requests, not independent original observations or heats')
    groups={}
    for field in ('reference_id','stratum','order'):
        groups[field]={key:one([r for r in records if r[field]==key]) for key in sorted({r[field] for r in records})}
    return dict(all_requests=one(records),groups=groups)


def run_arrays(x,t,w,ref,config,ordinal):
    """Evaluation kernel; called with synthetic arrays in this preparation round.

    Actual raw loading and real authorization live exclusively in run_real.
    No callable kernel can certify human authorization by itself.
    """
    i0,i1,j0,j1=config['core_slice']
    core=x[i0:i1,j0:j1]
    if core.shape != (7,17) or not np.isfinite(x).all() or np.any(x>=65535):
        raise ValueError('frozen core/support qualification differs')
    records=[]
    for seed in config['seeds']:
        chosen=sample_two(np.isfinite(core)&(core<65535),seed,ordinal)
        for k in config['masked_points_per_region']:
            mask=np.zeros(x.shape,bool)
            for i,j in chosen[:k]:mask[i+i0,j+j0]=True
            observed=x.copy();observed[mask]=np.nan
            paired=[]
            for order in config['orders']:
                estimated,info=r0.reconstruct_r0_limited(observed,t,w,order=order,
                    max_time_span_s=config['max_time_span_s'],max_wave_span_nm=config['max_wave_span_nm'])
                result=evaluate(estimated,x,mask,t,w,info)
                result.update(reference_id=ref['reference_id'],seed=seed,k=k,order=order,
                              stratum=next(s for s,ids in config['reference_strata'].items() if ref['reference_id'] in ids),
                              requested_positions=[d for d in chosen[:k]],
                              actual_mask_fraction=result['requested']/core.size,core_points=int(core.size))
                paired.append((result,estimated))
            both=mask&np.isfinite(paired[0][1])&np.isfinite(paired[1][1])
            diff=abs(paired[0][1][both]-paired[1][1][both])
            comparison=dict(requested=int(mask.sum()),both_resolved=int(both.sum()),
                            mean_abs_difference=float(diff.mean()) if len(diff) else None,
                            max_abs_difference=float(diff.max()) if len(diff) else None)
            for result,_ in paired:result['order_comparison']=comparison;records.append(result)
    return records


def run_real(bundle, approval_path, sources_path, output):
    """Only real CLI path: approve, verify all inputs, THEN sample and recover."""
    bundle,output=Path(bundle),Path(output)
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    cfg=read(bundle/'parameters.json');refs=read(bundle/'references.json');codes=read(bundle/'code_manifest.json')
    approval=read(approval_path)
    authorize(approval,cfg,refs,codes,domain='real')
    checked_code_manifest(codes)
    if output.exists():raise FileExistsError(output)
    sources=read(sources_path)
    if set(sources)!={r['reference_id'] for r in refs}:raise PermissionError('source mapping scope')
    loaded=[]
    # Complete qualification and binding before ANY random sampling.
    for ref in refs:
        a,b=ref['loaded_sequence'];c,d=ref['loaded_excel_columns']
        path=Path(sources[ref['reference_id']]).resolve()
        if output.resolve()==path or path in output.resolve().parents:
            raise ValueError('output intersects source file')
        x,t,w=r0.load_window(path,ref['source_sha256'],ref['heat'],a,b,c,d)
        binding=dict(source_sha256=ref['source_sha256'],window_sha256=ref['window_sha256'],
                     config_sha256=r0.digest(cfg),reference_manifest_sha256=r0.digest(refs),code_sha256=codes['files'])
        r0.verify_binding(x,t,w,binding,cfg,refs,{n:Path(__file__).parent/n for n in codes['files']},path)
        if x.shape!=(15,25) or np.any(x>=65535):raise ValueError('support qualification differs')
        loaded.append((ref,x,t,w))
    records=[];ids=sorted(r['reference_id'] for r in refs)
    for ref,x,t,w in loaded:records.extend(run_arrays(x,t,w,ref,cfg,ids.index(ref['reference_id'])))
    result=dict(task='A-Q1-R0-POINT-001',contract=contract(cfg,refs,codes),approval=approval,
                input_windows=[dict(reference_id=r['reference_id'],window_sha256=r['window_sha256'],source_sha256=r['source_sha256']) for r in refs],
                records=records,summary=summarize(records),scope=cfg['claim_scope'])
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--bundle',required=True);p.add_argument('--approval',required=True)
    p.add_argument('--sources',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run_real(a.bundle,a.approval,a.sources,a.out)
