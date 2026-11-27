"""Read only five candidate raw windows. Never creates a real masking experiment."""
import argparse
import csv
import json
import subprocess
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from r0_preparation import load_window, sha256, digest, window_digest

REF = '346c64ebe864e7f09fa2de227e7b72709fbb8670'
IDS = ['REF-6B03205-F','REF-6B03206-F','REF-6B03271-F','REF-6C02058-F','REF-6C02107-A']


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[2]
    code = Path(__file__).parent
    table = subprocess.check_output(['git','show', REF+':04_Q1光谱研究/实验验证/交叉审核整改_v2/Q1_70区修订审核表.csv']).decode('utf-8-sig')
    refs = {r['Reference_ID']:r for r in csv.DictReader(table.splitlines())}
    sources = json.loads((repo/'01_赛题与原始数据/数据结构清单.json').read_text(encoding='utf-8'))
    config = dict(task='A-Q1-MVM-001b', status='Pending', real_data_execution_allowed=False,
                  experiment='R0 interior point masking ONLY AFTER APPROVAL', reference_ids=IDS,
                  seeds=[20261127,20261128,20261129], masked_points_per_region=[1,2],
                  mask_population='core only; finite raw below 65535; uniform without replacement',
                  same_masks_for_both_orders=True, orders=['time-wave','wave-time'],
                  max_time_span_s=1., max_wave_span_nm=1.6, halo_nodes=4,
                  estimated_support='allowed only with explicit provenance; report separately',
                  extrapolation=False, real_validation_executed=False,
                  metrics=['requested','resolved','unresolved','coverage','MAE','RMSE','p95','max',
                           'estimated_support_fraction','order_difference'],
                  comparison_rule='report both orders; no tuning or selecting best using held-out error',
                  acceptance='report requested denominator and every unresolved position; no accuracy claim from this pilot alone',
                  approvers=[], approval_id=None)
    manifest, summaries, frames, bindings = [], [], [], []
    for rid in IDS:
        r = refs[rid]; heat=r['Heat_ID']
        src=next(m for m in sources if m['sheets']==[heat])
        name=Path(src['path']).name
        candidates=[args.source_root/name, args.source_root/'Data'/'Data'/name,
                    args.source_root/'corrected'/name, args.source_root/'original'/name]
        paths=list(dict.fromkeys(p for p in candidates if p.exists()))
        if len(paths)!=1: raise ValueError(f'{heat}: ambiguous/missing source')
        path=paths[0]
        a,b,c,d=[int(float(r[k])) for k in ('Start_Sequence','End_Sequence','Start_Excel_Column','End_Excel_Column')]
        aa,bb,cc,dd=a-4,b+4,c-4,d+4
        x,t,w=load_window(path, src['sha256'], heat, aa,bb,cc,dd)
        core=x[4:-4,4:-4]; cw=w[4:-4]
        item=dict(reference_id=rid, heat=heat, grid=r['Grid'], source_sha256=src['sha256'],
                  source_file=name, core_sequence=[a,b], core_excel_columns=[c,d],
                  loaded_sequence=[aa,bb], loaded_excel_columns=[cc,dd],
                  core_time_s=[float(t[4]),float(t[-5])], core_nm=[float(cw[0]),float(cw[-1])],
                  loaded_time_s=[float(t[0]),float(t[-1])], loaded_nm=[float(w[0]),float(w[-1])],
                  window_sha256=window_digest(x,t,w), approved=False,
                  proposed_use='conditional observed reference for point masking; not certified normal')
        manifest.append(item)
        delta=abs(np.diff(core,axis=0))
        summary=dict(reference_id=rid, grid=r['Grid'], core_points=int(core.size),
                     loaded_points=int(x.size), core_cap=int((core>=65535).sum()),
                     loaded_cap=int((x>=65535).sum()), core_nonfinite=int((~np.isfinite(core)).sum()),
                     core_min=float(core.min()),core_max=float(core.max()),
                     max_frame_mean_absolute_change=float(delta.mean(axis=1).max()),
                     max_adjacent_point_change=float(delta.max()),
                     requested_fraction_1point=1/core.size, requested_fraction_2points=2/core.size,
                     prior_S05_count=r['Prior_S05_Count'], interpretation='Pending local review; low pollution is not normality')
        summaries.append(summary)
        for i,row in enumerate(core):
            j=int(np.argmax(row)); peak=float(row[j])
            frames.append(dict(reference_id=rid,sequence=a+i,time_s=float(t[i+4]),
                               local_max_nm=float(cw[j]),local_max=peak,local_max_index=j,
                               maximum_interior=0<j<len(cw)-1,
                               left_edge=float(row[0]),right_edge=float(row[-1]),
                               left_drop=peak-float(row[0]),right_drop=peak-float(row[-1]),
                               median=float(np.median(row)),mean=float(row.mean()),
                               note='local maximum and window edges only; not physical peak identity or FWHM'))
        # Small raw cutout only; no reconstruction or mask is produced.
        raw=[dict(sequence=aa+i,time_s=float(t[i]),excel_column=cc+j,
                  wavelength_nm=float(w[j]),raw_intensity=float(x[i,j]))
             for i in range(len(t)) for j in range(len(w))]
        write_csv(args.out/(rid+'_raw_support.csv'),raw)
        fig,ax=plt.subplots(1,3,figsize=(15,4),layout='constrained')
        im=ax[0].pcolormesh(w,t,x,shading='nearest');fig.colorbar(im,ax=ax[0],label='Raw intensity')
        ax[0].axhline(t[4],color='r');ax[0].axhline(t[-5],color='r')
        ax[0].axvline(cw[0],color='r');ax[0].axvline(cw[-1],color='r')
        for i,row in enumerate(core):ax[1].plot(w,x[i+4],'.-',lw=.8,label=f'{t[i+4]:g}s')
        ax[1].axvline(cw[0],color='r');ax[1].axvline(cw[-1],color='r');ax[1].legend(fontsize=7)
        ax[2].plot(t[4:-4],core.mean(axis=1),'o-',label='core mean')
        ax[2].plot(t[4:-4],core.max(axis=1),'o-',label='core max');ax[2].legend()
        ax[0].set(xlabel='Wavelength (nm)',ylabel='Time (s)')
        ax[1].set(xlabel='Wavelength (nm)',ylabel='Raw intensity')
        ax[2].set(xlabel='Time (s)',ylabel='Raw intensity')
        fig.suptitle(rid+' | raw observations, no masking/fitting | red: core boundary')
        fig.savefig(args.out/(rid+'.png'),dpi=120);plt.close(fig)
        if sha256(path)!=src['sha256']:raise ValueError('source modified')
    codes={p.name:sha256(p) for p in [code/'r0_preparation.py',code/'prepare_r0_evidence.py']}
    for item in manifest:
        bindings.append(dict(reference_id=item['reference_id'],source_sha256=item['source_sha256'],
                             window_sha256=item['window_sha256'],config_sha256=digest(config),
                             reference_manifest_sha256=digest(manifest), code_sha256=codes))
    for filename,obj in [('config_pending.json',config),('reference_manifest_pending.json',manifest),
                         ('input_bindings.json',bindings)]:
        (args.out/filename).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    write_csv(args.out/'candidate_summary.csv',summaries);write_csv(args.out/'frame_evidence.csv',frames)
    print(json.dumps(summaries,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
