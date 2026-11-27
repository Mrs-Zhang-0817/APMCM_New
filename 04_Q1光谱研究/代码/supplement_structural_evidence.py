"""Additional counterexamples and full plateau shoulders; read-only raw access."""
from pathlib import Path
import argparse,csv,json,hashlib
import numpy as np
from pyxlsb import open_workbook
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from spectral_investigation import BASE,REPO,DIRS,plot_case,writecsv,runs
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);args=p.parse_args()
manifest=json.loads((REPO/'01_赛题与原始数据/数据结构清单.json').read_text(encoding='utf-8'))
with (DIRS['S06']/'S06_代表性案例登记表.csv').open(encoding='utf-8-sig') as f:cases=list(csv.DictReader(f))
columnpairs=[];plates=[];extra=[];events=[];hashes=[]
for m in manifest:
    num=m['attachment'];path=args.source_root/('附件1.炉号-6B03205.xlsb' if num==1 else 'Data/Data/'+Path(m['path']).name)
    if not path.exists():path=args.source_root/('corrected/附件1.炉号-6B03205.xlsb' if num==1 else 'original/'+Path(m['path']).name)
    before=hashlib.sha256(path.read_bytes()).hexdigest();assert before==m['sha256']
    with open_workbook(str(path)) as book:
        with book.get_sheet(1) as sh:
            it=sh.rows();header=[c.v for c in next(it)];data=[[c.v for c in row] for row in it]
    a=np.array(data,float);s=a[:,1:-3];w=np.array(header[1:-3],float);t=(a[:,0]-a[0,0])*.5;h=m['sheets'][0];n,k=s.shape
    for j in np.where(np.all(s[:,1:]==s[:,:-1],axis=0))[0]:columnpairs.append(dict(Heat_ID=h,Left_Excel_Column=int(j+2),Right_Excel_Column=int(j+3),Left_nm=w[j],Right_nm=w[j+1],Identical_Samples=n,Sample_Denominator=n,Identical_Percent=100.0,Interpretation='不同波长的完整时间列完全相同，原因待查，不自动判无效'))
    count=0;longest=(0,0,0)
    for i in range(n):
        equal=s[i,1:]==s[i,:-1]
        for lo,hi in runs(equal):
            length=int(hi-lo+2)
            if length>=3 and s[i,lo]!=65535:
                count+=1
                if length>longest[0]:longest=(length,i,int(lo))
    length,ii,jj=longest
    plates.append(dict(Heat_ID=h,Non65535_Horizontal_Constant_Runs_ge3=count,Longest_Points=length,Longest_Time_s=t[ii] if length else '',Longest_Start_nm=w[jj] if length else '',Longest_End_nm=w[jj+length-1] if length else '',Value=s[ii,jj] if length else '',Interpretation='精确相等的平台观察，不是异常判定；每行分段计数'))
    neighbors=np.stack([s[:-2,1:-1],s[2:,1:-1],s[1:-1,:-2],s[1:-1,2:]]);med=np.median(neighbors,axis=0);mad=np.median(abs(neighbors-med),axis=0);z=(s[1:-1,1:-1]-med)/(1.4826*mad+1)
    i,j=map(int,np.array(np.unravel_index(np.argmin(z),z.shape))+1);cid=h+'_H';outfile=DIRS['S06']/(cid+'_低点对照.png');plot_case(outfile,s,t,w,i,j,cid+' negative local-score candidate')
    extra.append(dict(Case_ID=cid,Heat_ID=h,Type='H_最负局部分数候选',Sequence=a[i,0],Time_s=t[i],Wavelength_nm=w[j],Excel_Row=i+2,Excel_Column=j+2,Original_Value=s[i,j],Signed_Score=z[i-1,j-1],Neighbors_Median=med[i-1,j-1],Neighbors_MAD=mad[i-1,j-1],Evidence_File=outfile.relative_to(BASE).as_posix(),Alternative_Explanation='吸收型局部谷/谱线结构/量化均可能，低点非已确认错误',Decision_Status='Hypothesis',Approval_Status='Pending'))
    for c in cases:
        if c['Heat_ID']!=h:continue
        if c['Type'].startswith('G'):
            i=int(c['Excel_Row'])-2;d=s[i]-s[i-1];events.append(dict(Case_ID=c['Case_ID'],Heat_ID=h,Time_s=t[i],Positive_Columns=int(np.sum(d>0)),Negative_Columns=int(np.sum(d<0)),Unchanged_Columns=int(np.sum(d==0)),Denominator=k,Positive_Percent=100*np.mean(d>0),Negative_Percent=100*np.mean(d<0),Mean_Abs_Change=np.mean(abs(d)),Interpretation='同一原始相邻时刻方向比例，未确认工艺因果'))
            fig,ax=plt.subplots(figsize=(10,4),layout='constrained');ax.plot(w,s[i-1],label=f'{t[i-1]}s');ax.plot(w,s[i],label=f'{t[i]}s');ax.legend();ax.set(xlabel='Actual wavelength (nm)',ylabel='Raw intensity',title=c['Case_ID']+' | full spectra; no log / no sampling');fig.savefig(DIRS['S06']/(c['Case_ID']+'_整谱变化.png'),dpi=130);plt.close(fig)
        if c['Type'].startswith('E'):
            i=int(c['Excel_Row'])-2;j=int(c['Excel_Column'])-2;lo,hi=next((lo,hi) for lo,hi in runs(s[i]==65535) if lo<=j<=hi);jl=max(0,lo-10);jr=min(k,hi+11);il=max(0,i-2);ir=min(n,i+3)
            fig,ax=plt.subplots(1,2,figsize=(13,4),layout='constrained');im=ax[0].pcolormesh(w[jl:jr],t[il:ir],s[il:ir,jl:jr],vmin=0,vmax=65535,shading='auto');fig.colorbar(im,ax=ax[0]);ax[0].set(xlabel='Actual wavelength (nm)',ylabel='Time (s)')
            for r in sorted(set([max(0,i-1),i,min(n-1,i+1)])):ax[1].plot(w[jl:jr],s[r,jl:jr],label=f'{t[r]}s')
            ax[1].legend();ax[1].axhline(65535,ls='--',c='grey');ax[1].set(xlabel='Actual wavelength (nm)',ylabel='Raw intensity');fig.suptitle(c['Case_ID']+' | complete plateau + 10 shoulder nodes each side; no sampling');fig.savefig(DIRS['S06']/(c['Case_ID']+'_完整平台肩部.png'),dpi=135);plt.close(fig)
    assert before==hashlib.sha256(path.read_bytes()).hexdigest();hashes.append(dict(Heat_ID=h,SHA256=before,After_Unchanged=True))
    print(f'Supplement {num}/10: {h}, repeated adjacent columns={sum(x["Heat_ID"]==h for x in columnpairs)}',flush=True)
writecsv(DIRS['S05']/'S05_重复波长列证据.csv',columnpairs,fields=['Heat_ID','Left_Excel_Column','Right_Excel_Column','Left_nm','Right_nm','Identical_Samples','Sample_Denominator','Identical_Percent','Interpretation'])
writecsv(DIRS['S05']/'S05_非上限平台统计.csv',plates);writecsv(DIRS['S06']/'S06_低点补充案例.csv',extra);writecsv(DIRS['S06']/'S06_整体变化方向证据.csv',events)
(BASE/'研究成果/补充核验.json').write_text(json.dumps(dict(sources=hashes,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),preprocessing=False),ensure_ascii=False,indent=2),encoding='utf-8')
