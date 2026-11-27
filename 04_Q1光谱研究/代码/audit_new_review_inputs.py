"""Read-only integrity audit for incremental review; no masking or raw workbook IO."""
import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from r0_preparation import digest, window_digest, sha256
import numpy as np


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise FileExistsError(args.out)
    repo=Path(__file__).resolve().parents[2]
    package=repo/'04_Q1光谱研究/实验验证/R0点遮蔽审批准备_v1'
    config=json.loads((package/'config_pending.json').read_text(encoding='utf-8'))
    manifest=json.loads((package/'reference_manifest_pending.json').read_text(encoding='utf-8'))
    bindings=json.loads((package/'input_bindings.json').read_text(encoding='utf-8'))
    def git(*args):return subprocess.check_output(['git',*args],cwd=repo).decode('utf-8').strip()
    results=[]
    for ref,b in zip(manifest,bindings,strict=True):
        rid=ref['reference_id']
        with (package/(rid+'_raw_support.csv')).open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        times=sorted(set(float(r['time_s']) for r in rows)); waves=sorted(set(float(r['wavelength_nm']) for r in rows))
        x=np.array([float(r['raw_intensity']) for r in rows]).reshape(len(times),len(waves))
        code_checks={name:sha256(repo/'04_Q1光谱研究/代码'/name)==expected for name,expected in b['code_sha256'].items()}
        results.append(dict(reference_id=rid,ids_match=rid==b['reference_id'],
                            actual_saved_window_hash_matches=window_digest(x,times,waves)==b['window_sha256']==ref['window_sha256'],
                            config_matches=digest(config)==b['config_sha256'],
                            manifest_matches=digest(manifest)==b['reference_manifest_sha256'],
                            code_matches=all(code_checks.values()),code_checks=code_checks))
    old='b35ac738d01642efe11b6e1a759572cace8b0885'
    files=git('-c','core.quotepath=false','ls-tree','-r','--name-only',old).splitlines()
    q2_sources={}
    for name in files:
        if name.startswith('05_Q2') and name.endswith('.py'):
            data=subprocess.check_output(['git','show',old+':'+name],cwd=repo)
            q2_sources[name]=hashlib.sha256(data).hexdigest()
    report=dict(task='A-Q1-CR-Q2-003',review_head=git('rev-parse','HEAD'),
                q2_old_baseline=old,old_q2_python_files=q2_sources,
                q2_new_model_received=False,q2_new_configs_received=False,q2_r0_review_received=False,
                scope='Only existing saved Q1 window integrity; not independent Q2 model verification',
                config_sha256=digest(config),manifest_sha256=digest(manifest),
                q1_integrity=results,q1_status=config['status'],
                q1_execution_allowed=config['real_data_execution_allowed'],
                formal_experiment_executed=False,raw_workbooks_read=False,
                source_files={p.name:sha256(p) for p in [package/'config_pending.json',package/'reference_manifest_pending.json',package/'input_bindings.json']})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
