"""Read-only three-branch and legacy-copy inventory. Never reads raw workbooks."""
import csv
import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path


def git(*args):return subprocess.check_output(['git',*args])
def sha(data):return hashlib.sha256(data).hexdigest()
def normalized(data):return data.replace(b'\r\n',b'\n')
def csv_out(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--legacy-root',type=Path,help='Optional local historical project; never published as a current source')
    args=parser.parse_args()
    out=Path(__file__).resolve().parent
    if (out/'同步核查.json').exists():raise FileExistsError('Use a new audit version')
    heads={branch:git('rev-parse','origin/'+branch).decode().strip() for branch in ('main','q1-spectral','q2-gas-oxygen')}
    trees={}
    for branch,commit in heads.items():
        with zipfile.ZipFile(io.BytesIO(git('archive','--format=zip',commit))) as z:
            trees[branch]={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
    allpaths=sorted(set().union(*(set(t) for t in trees.values())))
    inventory=[];selected={};conflicts=[]
    for path in allpaths:
        priority=('q1-spectral','q2-gas-oxygen','main') if path.startswith('04_') else ('q2-gas-oxygen','q1-spectral','main') if path.startswith('05_') else ('main','q1-spectral','q2-gas-oxygen')
        source=next(b for b in priority if path in trees[b]);data=trees[source][path]
        selected[path]=data
        variants={b:sha(t[path]) for b,t in trees.items() if path in t}
        row=dict(path=path,recommended_source_branch=source,source_commit=heads[source],bytes=len(data),sha256=sha(data),
                 main_present=path in trees['main'],q1_present=path in trees['q1-spectral'],q2_present=path in trees['q2-gas-oxygen'],
                 different_branch_contents=len(set(variants.values()))>1)
        inventory.append(row)
        if row['different_branch_contents']:conflicts.append(dict(path=path,**{b+'_sha256':variants.get(b,'ABSENT') for b in heads},recommended_source=source))
    csv_out(out/'三分支文件来源索引.csv',inventory)
    if conflicts:csv_out(out/'跨分支内容差异.csv',conflicts)
    allhashes={sha(normalized(data)) for t in trees.values() for data in t.values()}
    legacy=args.legacy_root
    oldrows=[]
    if legacy is not None and legacy.exists():
        for p in sorted(legacy.rglob('*')):
            if not p.is_file():continue
            relative=p.relative_to(legacy)
            if not relative.parts[0][:2] in ('00','01','02','03','04','05','06','07','08') and relative.as_posix() not in ('README.md','AGENTS.md','requirements.txt'):continue
            if '本地数据' in relative.parts or p.suffix.lower() not in ('.md','.txt','.py','.json','.csv','.png','.zip'):continue
            if any(part.startswith('.') or part=='__pycache__' for part in relative.parts):continue
            data=p.read_bytes();key=relative.as_posix();h=sha(normalized(data))
            samepath=any(key in t and sha(normalized(t[key]))==h for t in trees.values())
            state='远程同路径内容相同（LF规范比较）' if samepath else '远程其他路径有同内容（历史快照等）' if h in allhashes else '旧副本差异或未收录：不能自动当当前成果'
            oldrows.append(dict(legacy_relative_path=key,bytes=len(data),raw_sha256=sha(data),status=state))
        if oldrows:csv_out(out/'旧副本受控资料核对.csv',oldrows)
    source_manifest=json.loads(selected['01_赛题与原始数据/数据结构清单.json'])
    raw_required=[dict(attachment=m['attachment'],heat=m['sheets'][0],filename=Path(m['path']).name,sha256=m['sha256'],bytes=m['bytes'],in_git=False) for m in source_manifest]
    local_status=git('status','--porcelain=v1','--untracked-files=all').decode('utf-8')
    result=dict(task='J-SINGLE-HANDOVER-009',date='2026-11-28',repository='https://github.com/Mrs-Zhang-0817/APMCM_New',
                frozen_heads=heads,branch_file_counts={b:len(t) for b,t in trees.items()},union_file_count=len(allpaths),
                selected_files_missing_from_main=sum(not r['main_present'] for r in inventory),cross_branch_differences=len(conflicts),
                legacy_files_checked=len(oldrows),legacy_status_counts={s:sum(r['status']==s for r in oldrows) for s in sorted({r['status'] for r in oldrows})},
                ahead_behind={b:git('rev-list','--left-right','--count','origin/'+b+'...'+b).decode().strip() for b in heads},
                status_during_audit=local_status,raw_required=raw_required,
                boundary='Inventory is a read-only source map, not a branch merge, normal-data certification or scientific approval')
    (out/'同步核查.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('raw_required','status_during_audit')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
