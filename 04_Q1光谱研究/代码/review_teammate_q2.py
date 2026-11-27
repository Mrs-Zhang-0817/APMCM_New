"""Read-only independent Q2 review against our originals and Q1 evidence."""
from pathlib import Path
import argparse,csv,json,hashlib,importlib.util,subprocess
import numpy as np
from pyxlsb import open_workbook
P=Path(__file__).resolve().parents[1];R=P.parent;O=P/'实验验证/队友成果综合审核';O.mkdir(exist_ok=True)
def read(p):
    with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def out(name,rows):
    with (O/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def zero_runs(v):
    dd=np.diff(np.r_[False,v==0,False].astype(int));return list(zip(np.where(dd==1)[0],np.where(dd==-1)[0]-1))
parser=argparse.ArgumentParser();parser.add_argument('--peer',type=Path,required=True);parser.add_argument('--source-root',type=Path,required=True);args=parser.parse_args();Q=args.peer/'05_Q2供氧与烟气研究';E=Q/'研究成果/S01-S07'
spec=importlib.util.spec_from_file_location('peer_q2_load',Q/'代码/q2_load.py');loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
sources=read(E/'实际来源.csv');rels=read(E/'描述关系.csv');baseline=read(E/'逐炉基线.csv');lag=read(E/'探索滞后曲线.csv');intervals=read(E/'零值与常量段.csv');recomputed=[];hashes=[];spectrum_event=[];negative=[]
original=json.loads((R/'01_赛题与原始数据/数据结构清单.json').read_text(encoding='utf-8'))
def ck(h,key,value,expected):
    ok=bool(np.isclose(float(value),float(expected),atol=1e-8,rtol=1e-10));recomputed.append(dict(Heat_ID=h,Metric=key,Recomputed=value,Peer=expected,Match=ok));assert ok,(h,key,value,expected)
for m,peer in zip(original,sources):
    num=m['attachment'];h=m['sheets'][0];file=args.source_root/('附件1.炉号-6B03205.xlsb' if num==1 else 'Data/Data/'+Path(m['path']).name)
    assert peer['heat']==h and peer['sha256']==m['sha256'];before=hashlib.sha256(file.read_bytes()).hexdigest();assert before==peer['sha256']
    labels,rows=loader.read_book(file,h);a=np.array(rows,float);n=len(a);t=(a[:,0]-a[0,0])*.5
    assert n==int(peer['rows']);ck(h,'oxygen_first',a[0,1],next(r for r in baseline if r['heat']==h and r['variable']=='Oxygen')['first']);ck(h,'oxygen_last',a[-1,1],next(r for r in baseline if r['heat']==h and r['variable']=='Oxygen')['last'])
    for j,label in enumerate(['Oxygen','CO2','CO'],1):
        b=next(r for r in baseline if r['heat']==h and r['variable']==label);ck(h,label+'_repeats',np.sum(np.diff(a[:,j])==0),b['repeats']);ck(h,label+'_zeros',np.sum(a[:,j]==0),b['zeros'])
    for j,label in [(2,'CO2'),(3,'CO')]:
        peerrel=next(r for r in rels if r['heat']==h and r['gas']==label);trapezoid=np.sum(np.diff(t)*(a[:-1,j]+a[1:,j])/2);ck(h,label+'_trapezoid',trapezoid,peerrel['cumulative_g_trapezoid_m3'])
        x=np.diff(a[:,1]);y=np.diff(a[:,j]);rr=[]
        for k in range(61):rr.append(np.corrcoef(x[:len(x)-k],y[k:])[0,1])
        k=int(np.argmax(rr));ck(h,label+'_best_signed_positive_peak_lag',k*.5,peerrel['best_positive_lag_s']);ck(h,label+'_peak_r',rr[k],peerrel['r_at_lag'])
        kabs=int(np.argmax(abs(np.array(rr))));negative.append(dict(Heat_ID=h,Gas=label,Positive_Max_Lag_s=k*.5,Positive_Max_r=rr[k],Minimum_r=min(rr),Absolute_Max_Lag_s=kabs*.5,Absolute_Max_Signed_r=rr[kabs],Note='绝对峰仅作符号敏感性，不认作物理延迟'))
    if num in [1,2,5,8]:
        # Compare the independent package reader with the teammate's custom XLSB parser.
        with open_workbook(str(file)) as book:
            with book.get_sheet(1) as sheet:
                it=sheet.rows();header=[c.v for c in next(it)];values=[];spectral=[]
                for row in it:
                    vv=[c.v for c in row];values.append([vv[k] for k in [0,2048,2049,2050]])
                    if num==5:spectral.append(vv[1:2048])
        independent=np.array(values,float);assert np.array_equal(independent,a);ck(h,'independent_reader_max_abs_diff',np.max(abs(independent-a)),0)
        if num==5:
            s=np.array(spectral,float);idx=752;delta=s[idx]-s[idx-1]
            spectrum_event.append(dict(Heat_ID=h,Excel_Before=753,Excel_After=754,Time_Before=t[idx-1],Time_After=t[idx],Oxygen_Before=a[idx-1,1],Oxygen_After=a[idx,1],Oxygen_Delta=a[idx,1]-a[idx-1,1],CO2_Before=a[idx-1,2],CO2_After=a[idx,2],CO_Before=a[idx-1,3],CO_After=a[idx,3],Spectrum_Mean_Before=s[idx-1].mean(),Spectrum_Mean_After=s[idx].mean(),Spectrum_L1_Mean=np.mean(abs(delta)),Spectral_Rising_Columns=int(np.sum(delta>0)),Spectral_Falling_Columns=int(np.sum(delta<0)),Spectral_Total_Columns=s.shape[1],Saturation_Before=int(np.sum(s[idx-1]==65535)),Saturation_After=int(np.sum(s[idx]==65535)),Spectrum_Cosine=float(s[idx-1]@s[idx]/(np.linalg.norm(s[idx-1])*np.linalg.norm(s[idx])))))
            keep=x.copy();keep[idx-1]=np.nan
            for j,label in [(2,'CO2'),(3,'CO')]:
                dd=np.diff(a[:,j]);ok=np.isfinite(keep);recomputed.append(dict(Heat_ID=h,Metric=label+'_r_differences_without_375_5_to_376_event',Recomputed=np.corrcoef(keep[ok],dd[ok])[0,1],Peer='not reported; descriptive leave-one-event sensitivity',Match='new evidence; not cleaning'))
    assert before==hashlib.sha256(file.read_bytes()).hexdigest();hashes.append(dict(Heat_ID=h,SHA256=before,Unchanged=True,Independent_Reader_Check=num in [1,2,5,8]))
out('Q2关键结果独立复算.csv',recomputed);out('滞后符号敏感性.csv',negative);out('附件5跨模态事件证据.csv',spectrum_event)
zerorows=[r for r in intervals if r['heat']=='6C02060' and r['kind']=='zero' and r['variable'] in ['CO2','CO']];out('附件8烟气内部零段.csv',zerorows)
# Verify exact duplicate run-check/final outputs without deleting either peer artifact.
dups=[]
for p in E.iterdir():
    q=Q/'运行检查'/p.name
    if p.is_file() and q.is_file():dups.append(dict(File=p.name,Same_SHA256=hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256(q.read_bytes()).hexdigest()))
out('队友重复产物检查.csv',dups)
(O/'审阅来源与核验.json').write_text(json.dumps(dict(repository='https://github.com/lf21szgmail-sys/Test',reviewed_branch='q2-gas-oxygen',reviewed_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.peer,text=True).strip(),main_has_only_entry=True,peer_pr=1,sources=hashes,custom_reader_all10_read=True,independent_pyxlsb_crosscheck=[1,2,5,8],formal_cleaning=False,delay_estimated_as_physical=False),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(records=len(recomputed),all_ten_sources_match=True,event=spectrum_event,attachment5_sign=[r for r in negative if r['Heat_ID']=='6C02057'],attachment5_event_sensitivity=[r for r in recomputed if 'without_' in r['Metric']]),ensure_ascii=False,indent=2))
