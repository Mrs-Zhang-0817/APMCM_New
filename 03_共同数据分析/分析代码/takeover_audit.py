"""Read-only source audit. Run using bundled Python with .analysis_deps on PYTHONPATH."""
from pathlib import Path
import sys, json, hashlib, csv, re
ROOT = Path(__file__).resolve().parents[2]
import os
DATA_ROOT = Path(os.environ.get('APMCM_DATA_ROOT', ROOT/'01_赛题与原始数据/本地数据'))

import numpy as np
from pyxlsb import open_workbook
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pymupdf

OUT = Path(os.environ.get('APMCM_OUTPUT_ROOT', ROOT/'本地复现输出'))
for folder in ['01_Raw_Data','02_Data_Exploration/Common','02_Data_Exploration/Spectrum','02_Data_Exploration/Oxygen_Gas','03_Data_Preprocessing/Spectrum','03_Data_Preprocessing/Oxygen_Gas','03_Data_Preprocessing/Quality_Masks','04_Models/Q1','04_Models/Q2','04_Models/Q3','05_Results/Figures','05_Results/Tables','06_Paper']:
    (OUT/folder).mkdir(parents=True, exist_ok=True)
TABLE = OUT/'05_Results/Tables'
FIG = OUT/'05_Results/Figures'
def writecsv(path, rows):
    if not rows: return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def load(path):
    with open_workbook(str(path)) as w:
        names=w.sheets[:]
        with w.get_sheet(1) as s:
            rows=list(s.rows())
    header=[c.v for c in rows[0]]
    raw=np.empty((len(rows)-1,len(header)),object);raw[:]=None
    for i,row in enumerate(rows[1:]):
        for c in row:
            if c.c<len(header):raw[i,c.c]=c.v
    a=np.full(raw.shape,np.nan)
    nonnumeric=0
    for ix,v in np.ndenumerate(raw):
        if v is None or v=='':continue
        try:a[ix]=float(v)
        except (ValueError,TypeError):nonnumeric+=1
    return header,a,names,nonnumeric
sources=sorted((DATA_ROOT/'original').glob('*.xlsb'), key=lambda p:int(re.search(r'Attachment (\d+)',p.name)[1]))
corrected=DATA_ROOT/'corrected/附件1.炉号-6B03205.xlsb'
if not corrected.is_file():
    raise FileNotFoundError('Official corrected attachment 1 is required; legacy fallback is forbidden.')
manifest=[];summary=[];issues=[];variables=[];intervals=[];corrs=[];datasets=[]
def issue(heat,var,loc,obs,evidence,cause='待查',status='观测事实；原因未确认'):
    issues.append(dict(Issue_ID=f'DQ{len(issues)+1:03}',Heat_ID=heat,Variable=var,Location=loc,Observation=obs,Evidence=evidence,Possible_Cause=cause,Status=status,Potential_Impact='需评估，当前不删除或替换'))
def runs(mask):
    d=np.diff(np.r_[False,mask,False].astype(int));return list(zip(np.where(d==1)[0],np.where(d==-1)[0]-1))
for num,old in enumerate(sources,1):
    path=corrected if num==1 and corrected.exists() else old
    h,a,sheets,nn=load(path);heat=sheets[0];n,p=a.shape
    print(f'{num}: {path.name}: {a.shape}',flush=True)
    manifest.append(dict(attachment=num,path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size,sheets=sheets,headers=h,data_range=f'rows 2:{n+1}, columns 1:{p}'))
    if num==1 and path!=old:
        ho,ao,so,no=load(old)
        diff={'old_path':str(old),'old_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'new_path':str(path),'same_headers':ho==h,'old_shape':ao.shape,'new_shape':a.shape,'columns':[]}
        if ao.shape==a.shape:
            changed=~((ao==a)|(np.isnan(ao)&np.isnan(a)))
            for j in np.where(changed.any(axis=0))[0]:
                idx=np.where(changed[:,j])[0]
                diff['columns'].append(dict(column=int(j+1),header=h[j],changed_cells=len(idx),first_excel_row=int(idx[0]+2),last_excel_row=int(idx[-1]+2),old_zero_count=int(np.sum(ao[:,j]==0)),new_zero_count=int(np.sum(a[:,j]==0))))
        diff['header_changes']=[dict(excel_column=j+1,old=ho[j],new=h[j]) for j in range(min(len(ho),len(h))) if ho[j]!=h[j]]
        (TABLE/'attachment1_version_diff.json').write_text(json.dumps(diff,ensure_ascii=False,indent=2),encoding='utf-8')
    wave=np.array(h[1:-3],float);s=a[:,1:-3];seq=a[:,0];t=(seq-seq[0])*.5;ds=np.diff(seq)
    row=dict(attachment=num,heat=heat,samples=n,columns=p,spectral_columns=len(wave),sequence_first=seq[0],sequence_last=seq[-1],duration_s=t[-1],sequence_bad_steps=int(np.sum(ds!=1)),duplicate_sequence=n-len(np.unique(seq)),wavelength_min_nm=wave.min(),wavelength_max_nm=wave.max(),wavelength_increasing=bool(np.all(np.diff(wave)>0)),missing_cells=int(np.isnan(a).sum()),nonnumeric_cells=nn,duplicate_full_rows=n-len(np.unique(a,axis=0)),spectral_min=np.nanmin(s),spectral_median=np.nanmedian(s),spectral_p99=np.nanquantile(s,.99),spectral_max=np.nanmax(s),spectral_zero_cells=int(np.sum(s==0)),spectral_65535_cells=int(np.sum(s==65535)),spectral_negative_cells=int(np.sum(s<0)),oxygen_decreases=int(np.sum(np.diff(a[:,-3])<0)),oxygen_repeated_steps=int(np.sum(np.diff(a[:,-3])==0)),co2_zero_samples=int(np.sum(a[:,-2]==0)),co_zero_samples=int(np.sum(a[:,-1]==0)))
    summary.append(row);datasets.append((heat,t,wave,s,a[:,-3:]))
    if row['spectral_65535_cells']:issue(heat,'spectrum','详见 quality_locations.csv','出现 65535',str(row['spectral_65535_cells'])+' cells','可能为仪器饱和，需仪器量程证据')
    if row['oxygen_decreases']:issue(heat,'oxygen','diff(O)<0','累计氧下降',str(row['oxygen_decreases'])+' steps')
    if row['missing_cells'] or nn:issue(heat,'all','manifest range','存在缺失或非数值',str(row['missing_cells']))
    if num>1 and not np.array_equal(wave,datasets[0][2]):issue(heat,'wavelength','header B: spectral end','波长网格与附件1不同',f'{wave.min()} to {wave.max()} nm','可能为设备标定差异；不能按列号直接融合')
    for k,label in enumerate(['oxygen','CO2','CO']):
        v=a[:,-3+k];finite=v[np.isfinite(v)]
        variables.append(dict(heat=heat,variable=label,header=str(h[-3+k]),min=float(np.min(finite)),max=float(np.max(finite)),mean=float(np.mean(finite)),median=float(np.median(finite)),std=float(np.std(finite)),zero_count=int(np.sum(v==0)),negative_count=int(np.sum(v<0)),missing_count=int(np.isnan(v).sum())))
        for kind,mask in [('zero',v==0),('repeated_transition',np.r_[False,np.diff(v)==0])]:
            for start,end in runs(mask):intervals.append(dict(heat=heat,variable=label,kind=kind,start_excel_row=int(start+2),end_excel_row=int(end+2),start_s=t[start],end_s=t[end],count=int(end-start+1)))
        if np.all(v==0):issue(heat,label,f'rows 2:{n+1}','全列为零','zero count='+str(n),'真实零值或缺测编码尚待确认')
    # Descriptive only. Adjacent differences are noisy and are not an accepted oxygen model.
    signals=np.column_stack([np.nanmedian(s,axis=1),a[:,-3:],np.r_[np.nan,np.diff(a[:,-3])/.5]])
    labels=['spectral_median','oxygen','CO2','CO','oxygen_first_difference']
    for x in range(5):
        for y in range(x+1,5):
            ok=np.isfinite(signals[:,x])&np.isfinite(signals[:,y]);xx=signals[ok,x];yy=signals[ok,y]
            r=float(np.corrcoef(xx,yy)[0,1]) if xx.std()>0 and yy.std()>0 else None
            corrs.append(dict(heat=heat,x=labels[x],y=labels[y],pearson_r=r,interpretation='描述相关，非因果或延迟估计'))
    fig,ax=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    im=ax[0,0].pcolormesh(wave,t,s,shading='auto',rasterized=True,vmin=np.nanquantile(s,.01),vmax=np.nanquantile(s,.99));fig.colorbar(im,ax=ax[0,0],label='Intensity (official W/cm2)');ax[0,0].set(xlabel='Wavelength (nm)',ylabel='Time (s)',title='Raw spectrum (color clipped 1-99%)')
    for i in np.linspace(0,n-1,4,dtype=int):ax[0,1].plot(wave,s[i],label=f'{t[i]:g}s',lw=.7)
    ax[0,1].legend();ax[0,1].set(title='Selected raw spectra',xlabel='Wavelength (nm)')
    for j in np.linspace(0,len(wave)-1,4,dtype=int):ax[0,2].plot(t,s[:,j],label=f'{wave[j]:.1f}nm',lw=.6)
    ax[0,2].legend();ax[0,2].set(title='Selected wavelength traces',xlabel='Time (s)')
    ax[1,0].hist(s[np.isfinite(s)],bins=100);ax[1,0].set_yscale('log');ax[1,0].set(title='Raw intensity histogram',xlabel='Intensity',ylabel='Count (log scale)')
    ax[1,1].plot(t,a[:,-3]);ax[1,1].set(title='Cumulative oxygen',xlabel='Time (s)',ylabel='m3')
    ax[1,2].plot(t,a[:,-2],label='CO2');ax[1,2].plot(t,a[:,-1],label='CO');ax[1,2].legend();ax[1,2].set(title='Measured gas volume flow',xlabel='Time (s)',ylabel='m3/s')
    fig.suptitle(heat+' | observed data; no cleaning or alignment');fig.savefig(FIG/f'{heat}_eda.png',dpi=140);plt.close(fig)
    loc=[]
    for label,mask in [('suspected_saturation',s==65535),('missing',~np.isfinite(s)),('negative',s<0)]:
        for i,j in np.argwhere(mask):loc.append(dict(heat=heat,label=label,excel_row=int(i+2),excel_column=int(j+2),sequence=seq[i],time_s=t[i],wavelength_nm=wave[j],value=s[i,j]))
    writecsv(OUT/'02_Data_Exploration/Spectrum'/f'{heat}_quality_locations.csv',loc)
writecsv(TABLE/'ten_heat_overview.csv',summary);writecsv(TABLE/'variable_statistics.csv',variables);writecsv(TABLE/'zero_repeat_intervals.csv',intervals);writecsv(TABLE/'descriptive_correlations.csv',corrs);writecsv(OUT/'Data_Issue_Register.csv',issues)
(TABLE/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
for heat,t,w,s,g in datasets:
    axes[0].plot(t,g[:,0],label=heat,lw=.8);axes[1].plot(w,np.nanmedian(s,axis=0),label=heat,lw=.8);axes[2].plot(t,g[:,1],label=heat,lw=.8)
for ax,title,x,y in zip(axes,['Cumulative oxygen','Median raw spectrum','CO2 volume flow'],['Time (s)','Wavelength (nm)','Time (s)'],['m3','Intensity (official W/cm2)','m3/s']):ax.set(title=title,xlabel=x,ylabel=y)
axes[2].legend(fontsize=6);fig.savefig(FIG/'cross_heat.png',dpi=150);plt.close(fig)
if (DATA_ROOT/'2026 APMCM Problem B.pdf').exists():
    doc=pymupdf.open(DATA_ROOT/'2026 APMCM Problem B.pdf')
    (OUT/'02_Data_Exploration/Common/official_statement_extracted.txt').write_text('\n'.join(f'PAGE {i+1}\n'+p.get_text() for i,p in enumerate(doc)),encoding='utf-8')
    doc[2].get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(str(OUT/'02_Data_Exploration/Common/statement_page3.png'))
print('AUDIT COMPLETE',flush=True)
