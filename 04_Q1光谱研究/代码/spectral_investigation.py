"""S01-S06 read-only investigation. No cleaning, fitting, resampling or model training."""
from pathlib import Path
import argparse,os,csv,json,hashlib,sys,platform,time,subprocess,importlib.metadata
import numpy as np
from pyxlsb import open_workbook
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE=Path(__file__).resolve().parents[1];REPO=BASE.parent
DIRS={s:BASE/'专项分析'/name for s,name in [('S01','S01_光谱基线核验'),('S02','S02_波长网格调查'),('S03','S03_光谱结构调查'),('S04','S04_65535候选饱和调查'),('S05','S05_其他候选异常调查'),('S06','S06_谱峰与异常反例研究')]}
def writecsv(path,rows,fields=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def hashfile(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def runs(mask):
    d=np.diff(np.r_[False,mask,False].astype(int));return zip(np.where(d==1)[0],np.where(d==-1)[0]-1)
def component_records(mask,neighbors):
    remaining=set(map(tuple,np.argwhere(mask)));groups=[]
    offsets=[(-1,0),(1,0),(0,-1),(0,1)]
    if neighbors==8:offsets += [(-1,-1),(-1,1),(1,-1),(1,1)]
    while remaining:
        root=min(remaining);remaining.remove(root);stack=[root];group=[]
        while stack:
            i,j=stack.pop();group.append((i,j))
            for di,dj in offsets:
                nxt=(i+di,j+dj)
                if nxt in remaining:remaining.remove(nxt);stack.append(nxt)
        groups.append(group)
    return sorted(groups,key=lambda g:(-len(g),min(g)))
def plot_case(path,s,t,w,i,j,title):
    il=max(0,i-5);ir=min(len(t),i+6);jl=max(0,j-20);jr=min(len(w),j+21)
    fig,ax=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    im=ax[0,0].pcolormesh(w[jl:jr],t[il:ir],s[il:ir,jl:jr],shading='auto',vmin=0,vmax=65535);fig.colorbar(im,ax=ax[0,0],label='Raw intensity')
    for ii in sorted(set([max(0,i-1),i,min(len(t)-1,i+1)])):ax[0,1].plot(w[jl:jr],s[ii,jl:jr],marker='.',label=f'{t[ii]:g}s')
    ax[0,1].axhline(65535,c='grey',ls='--');ax[0,1].legend()
    ax[1,0].plot(t[il:ir],s[il:ir,j],'.-');ax[1,0].axhline(65535,c='grey',ls='--')
    ax[1,1].plot(t,s[:,j],lw=.6);ax[1,1].axvline(t[i],c='r');ax[1,1].set(title=f'Full-window trace at {w[j]:.3f}nm')
    for a in ax[0,:]:a.set(xlabel='Wavelength (nm)')
    ax[0,0].set(ylabel='Time (s)')
    for a in ax[1,:]:a.set(xlabel='Time (s)',ylabel='Raw intensity')
    ax[0,1].set(ylabel='Raw intensity');fig.suptitle(title+' | raw observations; no smoothing/resampling')
    fig.savefig(path,dpi=130);plt.close(fig)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);args=parser.parse_args()
    for d in DIRS.values():d.mkdir(parents=True,exist_ok=True)
    if (BASE/'研究成果/运行核验.json').exists():raise RuntimeError('Published run exists; use a separate versioned checkout/run rather than overwrite.')
    start=time.time();manifest=json.loads((REPO/'01_赛题与原始数据/数据结构清单.json').read_text(encoding='utf-8'))
    with (REPO/'01_赛题与原始数据/原始数据版本清单.csv').open(encoding='utf-8-sig') as f:versions={int(r['附件编号']):r for r in csv.DictReader(f)}
    with (REPO/'03_共同数据分析/十炉数据对比表.csv').open(encoding='utf-8-sig') as f:prior={r['Heat_ID']:r for r in csv.DictReader(f)}
    # Existing migrated loader is exercised on one complete original workbook, not assumed operational.
    import importlib.util
    spec=importlib.util.spec_from_file_location('migrated_audit',REPO/'03_共同数据分析/分析代码/takeover_audit.py')
    # That legacy module executes on import, so inspect/compile without importing it; reuse its pyxlsb row convention below.
    ast_source=Path(spec.origin).read_text(encoding='utf-8');compile(ast_source,spec.origin,'exec')
    baselines=[];stats=[];satstats=[];components=[];satloc=[];satruns=[];sens=[];candidates=[];cases=[];rowstats=[];wavestats=[];grids=[];medians=[];verified=[];widths=[]
    sourcepaths=[]
    for m in manifest:
        num=m['attachment'];p=args.source_root/('附件1.炉号-6B03205.xlsb' if num==1 else 'Data/Data/'+Path(m['path']).name)
        if not p.exists():p=args.source_root/('corrected/附件1.炉号-6B03205.xlsb' if num==1 else 'original/'+Path(m['path']).name)
        assert p.is_file(),p.name
        assert p.stat().st_size==int(versions[num]['文件字节数'])
        assert hashfile(p)==m['sha256']==versions[num]['SHA256'];sourcepaths.append((p,m['sha256']))
        with open_workbook(str(p)) as book:
            assert book.sheets==m['sheets']
            with book.get_sheet(1) as sheet:
                iterator=sheet.rows();header=[c.v for c in next(iterator)];data=[];missing=0;nonnum=0;types=set()
                for row in iterator:
                    values=[None]*len(header)
                    for c in row:
                        if c.c<len(header):values[c.c]=c.v
                    for v in values[1:-3]:
                        types.add(type(v).__name__)
                        if v is None or v=='':missing+=1
                        elif not isinstance(v,(float,int)):nonnum+=1
                    data.append(values)
        a=np.asarray(data,dtype=float);del data
        h=book.sheets[0];s=a[:,1:-3];seq=a[:,0];t=(seq-seq[0])*.5;w=np.asarray(header[1:-3],float);n,k=s.shape;grids.append(w);medians.append(np.median(s,axis=0))
        assert len(header)==2051 and k==2047 and header==m['headers'];assert np.all(np.diff(seq)==1)
        assert np.isfinite(s).all() and missing==nonnum==0
        old=prior[h];assert n==int(old['Samples']) and s.max()==float(old['Spectrum_Max']) and int(np.sum(s==65535))==int(old['Value_65535_Count'])
        base=dict(Heat_ID=h,Attachment=num,Rows=n,Spectral_Columns=k,Time_Count=n,Sequence_First=seq[0],Sequence_Last=seq[-1],Time_First_s=t[0],Time_Last_s=t[-1],Wavelength_Min_nm=w.min(),Wavelength_Max_nm=w.max(),Wavelength_Strictly_Increasing=bool(np.all(np.diff(w)>0)),Duplicate_Wavelengths=k-len(np.unique(w)),Step_Min_nm=np.diff(w).min(),Step_Max_nm=np.diff(w).max(),Uniform_Step_at_1e_9=bool(np.allclose(np.diff(w),np.diff(w)[0],rtol=0,atol=1e-9)),Original_Types=';'.join(sorted(types)),Loaded_Dtype=str(s.dtype),Missing=missing,Nonnumeric=nonnum,Nonfinite=int(np.sum(~np.isfinite(s))),Negative=int(np.sum(s<0)),Zero=int(np.sum(s==0)),Maximum=s.max(),Duplicate_Spectral_Rows=n-len(np.unique(s,axis=0)),Same_As_Joint_Baseline=True)
        baselines.append(base);verified.append(dict(Heat_ID=h,Attachment=num,File=p.name,Bytes=p.stat().st_size,SHA256=m['sha256'],Version=versions[num]['当前有效版本'],Sheet=h,Excel_Rows=f'2:{n+1}',Excel_Spectral_Columns='2:2048',Hash_Before_OK=True))
        quant=np.quantile(s,[.01,.05,.25,.5,.75,.95,.99,.999]);mad=np.median(abs(s-quant[3]));sat=s==65535
        stats.append(dict(Heat_ID=h,N=n*k,Min=s.min(),Max=s.max(),Mean=s.mean(),Median=quant[3],Std=s.std(),MAD_raw=mad,IQR=quant[4]-quant[2],Q01=quant[0],Q05=quant[1],Q25=quant[2],Q75=quant[4],Q95=quant[5],Q99=quant[6],Q999=quant[7],Zero_Count=int(np.sum(s==0)),Zero_Percent=100*np.mean(s==0),Count_65535=int(sat.sum()),Percent_65535=100*sat.mean()))
        ds=np.diff(s,axis=0);l1=np.mean(abs(ds),axis=1);l2=np.sqrt(np.mean(ds**2,axis=1));cos=np.sum(s[:-1]*s[1:],axis=1)/(np.linalg.norm(s[:-1],axis=1)*np.linalg.norm(s[1:],axis=1))
        for i in range(n):rowstats.append(dict(Heat_ID=h,Sequence=seq[i],Time_s=t[i],Mean=s[i].mean(),Median=np.median(s[i]),Min=s[i].min(),Max=s[i].max(),Saturation_Count=int(sat[i].sum()),L1_Mean_From_Previous=l1[i-1] if i else '',L2_RMS_From_Previous=l2[i-1] if i else '',Cosine_With_Previous=cos[i-1] if i else ''))
        for j in range(k):wavestats.append(dict(Heat_ID=h,Column_Index=j,Excel_Column=j+2,Wavelength_nm=w[j],Mean=s[:,j].mean(),Median=np.median(s[:,j]),Std=s[:,j].std(),Q05=np.quantile(s[:,j],.05),Q95=np.quantile(s[:,j],.95),Max=s[:,j].max(),Saturation_Count=int(sat[:,j].sum())))
        st=dict(Heat_ID=h,Points=int(sat.sum()),Point_Denominator=n*k,Point_Percent=100*sat.mean(),Affected_Rows=int(sat.any(axis=1).sum()),Row_Denominator=n,Row_Percent=100*sat.any(axis=1).mean(),Affected_Columns=int(sat.any(axis=0).sum()),Column_Denominator=k,Column_Percent=100*sat.any(axis=0).mean(),Max_Per_Row=int(sat.sum(axis=1).max()),Max_Per_Column=int(sat.sum(axis=0).max()),Near_Upper_60000_65535_Count=int(np.sum((s>=60000)&(s<65535))),Near_Upper_Threshold_Exploratory=60000)
        comps4=component_records(sat,4);comps8=component_records(sat,8);st['Components_4']=len(comps4);st['Components_8']=len(comps8);st['Largest_4']=max(map(len,comps4),default=0);st['Largest_8']=max(map(len,comps8),default=0);satstats.append(st)
        for adj,groups in [(4,comps4),(8,comps8)]:
            for ci,g in enumerate(groups,1):
                ii,jj=np.array(g).T;components.append(dict(Heat_ID=h,Adjacency=adj,Component_ID=ci,Points=len(g),Min_Row=int(ii.min()),Max_Row=int(ii.max()),Min_Column=int(jj.min()),Max_Column=int(jj.max()),Start_s=t[ii.min()],End_s=t[ii.max()],Time_Span_s=t[ii.max()]-t[ii.min()],Min_nm=w[jj.min()],Max_nm=w[jj.max()],Wavelength_Span_nm=w[jj.max()]-w[jj.min()],Bounding_Box_Fill=len(g)/((ii.max()-ii.min()+1)*(jj.max()-jj.min()+1)),Interpretation='观测连通区域，非故障次数'))
        for i,j in np.argwhere(sat):satloc.append(dict(Heat_ID=h,Sequence=seq[i],Time_s=t[i],Wavelength_nm=w[j],Excel_Row=int(i+2),Excel_Column=int(j+2),Original_Value=65535))
        for direction in ['time','wavelength']:
            count=k if direction=='time' else n
            for fixed in range(count):
                mask=sat[:,fixed] if direction=='time' else sat[fixed]
                for lo,hi in runs(mask):satruns.append(dict(Heat_ID=h,Direction=direction,Fixed_Index=fixed,Start_Index=int(lo),End_Index=int(hi),Points=int(hi-lo+1),Start_s=t[lo] if direction=='time' else t[fixed],End_s=t[hi] if direction=='time' else t[fixed],Min_nm=w[fixed] if direction=='time' else w[lo],Max_nm=w[fixed] if direction=='time' else w[hi],Span_s=(hi-lo)*.5 if direction=='time' else 0,Span_nm=0 if direction=='time' else w[hi]-w[lo]))
        # Four cardinal neighbors, center excluded; diagnostics only, no replacement signal.
        center=s[1:-1,1:-1];neighbors=np.stack([s[:-2,1:-1],s[2:,1:-1],s[1:-1,:-2],s[1:-1,2:]])
        localmed=np.median(neighbors,axis=0);localmad=np.median(abs(neighbors-localmed),axis=0);signed=(center-localmed)/(1.4826*localmad+1.0);del neighbors
        score=abs(signed);eligible=center!=65535;selected=(score>12)&eligible
        for threshold in [12,20,30]:
            mm=(score>threshold)&eligible;rr=mm.any(axis=1);cc=mm.any(axis=0)
            sens.append(dict(Heat_ID=h,Method='four_cardinal_neighbors_MAD',Threshold=threshold,Window='3x3 cardinal 4 only',Scale_Floor=1.0,Count=int(mm.sum()),Evaluated_Points=int(eligible.sum()),Evaluated_Percent=100*mm.sum()/eligible.sum(),All_Spectral_Points=n*k,All_Point_Percent=100*mm.sum()/(n*k),Affected_Rows=int(rr.sum()),All_Rows=n,Row_Percent=100*rr.sum()/n,Affected_Columns=int(cc.sum()),All_Columns=k,Column_Percent=100*cc.sum()/k,Status='探索参数，非最终阈值；边界及65535不参与此分数筛查'))
        for i0,j0 in np.argwhere(selected):
            i,j=i0+1,j0+1;candidates.append(dict(Issue_ID=f'A-Q1-C{len(candidates)+1:07}',Task_ID='S05',Heat_ID=h,Sequence=seq[i],Time_s=t[i],Wavelength_nm=w[j],Excel_Row=int(i+2),Excel_Column=int(j+2),Original_Value=s[i,j],Candidate_Type='局部正残差' if signed[i0,j0]>0 else '局部负残差',Score=score[i0,j0],Neighbor_Median=localmed[i0,j0],Neighbor_MAD=localmad[i0,j0],Evidence='四邻域分数>12，完整位置表；代表案例另见S06',Alternative_Explanation='真实窄谱线/工艺突变/量化亦可产生高分',Candidate_Method='探索局部稳健残差，未定案',Decision_Status='Hypothesis',Approval_Status='Pending'))
        # Representative case selection is deterministic; labels describe morphology, not physical truth.
        med=medians[-1];contrast=med[1:-1]-(med[:-2]+med[2:])/2;jpeak=int(np.argmax(contrast)+1)
        bi,bj=map(int,np.unravel_index(np.argmax(abs(ds)),ds.shape))
        ci,cj=map(int,np.unravel_index(np.argmax(np.where(s<65535,s,-1)),s.shape))
        di,dj=map(int,np.array(np.unravel_index(np.argmax(np.where(eligible,score,-1)),score.shape))+1)
        selections=[('A_持续候选谱峰',int(np.argmax(s[:,jpeak])),jpeak),('B_最大时间变化',bi+1,bj),('C_未到上限高值',ci,cj),('D_高局部残差',di,dj),('G_多波长同步变化',int(np.argmax(l1)+1),int(np.argmax(abs(ds[np.argmax(l1)]))))]
        if comps4:
            best=max([(hi-lo+1,i,int(lo)) for i in range(n) for lo,hi in runs(sat[i])],default=(0,0,0));selections.append(('E_最长上限平台',best[1],best[2]+best[0]//2))
            smallest=min(comps4,key=lambda c:(len(c),min(c)));selections.append(('F_最小上限连片',*map(int,smallest[0])))
        else:
            fi,fj=map(int,np.unravel_index(np.argmax(s),s.shape))
            selections.append(('F_无65535近上限对照',fi,fj))
        for typ,i,j in selections:
            caseid=f'{h}_{typ[0]}';out=DIRS['S06']/(caseid+'_局部证据.png');plot_case(out,s,t,w,i,j,caseid)
            plateau=next(((int(lo),int(hi)) for lo,hi in runs(sat[i]) if lo<=j<=hi),None)
            lp=plateau[1]-plateau[0]+1 if plateau else 0
            left=s[i,plateau[0]-1] if plateau and plateau[0]>0 else None;right=s[i,plateau[1]+1] if plateau and plateau[1]<k-1 else None
            support=bool(lp>=2 and left is not None and right is not None and left<65535 and right<65535)
            case=dict(Case_ID=caseid,Heat_ID=h,Type=typ,Sequence=seq[i],Time_s=t[i],Wavelength_nm=w[j],Excel_Row=i+2,Excel_Column=j+2,Original_Value=s[i,j],Plateau_Points=lp,Left_Shoulder=left,Right_Shoulder=right,Temporal_Neighbors=';'.join(str(v) for v in s[max(0,i-2):i+3,j]),Repeated_Local_Peak_Fraction=float(np.mean((s[:,j]>s[:,max(0,j-1)])&(s[:,j]>s[:,min(k-1,j+1)]))),Evidence_Class='支持削顶形态假设' if support else '证据不足；无明显平台不能否定削顶',Alternative_Explanation='真实谱线/过程整体变化/记录机制；不能确认元素或错误',Decision_Status='Observed Fact' if support else 'Hypothesis',Approval_Status='Pending',Evidence_File=out.relative_to(BASE).as_posix())
            cases.append(case)
            if typ.startswith('A'):
                # Crude observed half-height-above-local-min width, not instrument-corrected FWHM.
                lo=max(0,j-20);hi=min(k,j+21);baseline=s[i,lo:hi].min();level=baseline+(s[i,j]-baseline)/2;l=j;r=j
                while l>lo and s[i,l-1]>=level:l-=1
                while r<hi-1 and s[i,r+1]>=level:r+=1
                widths.append(dict(Case_ID=caseid,Heat_ID=h,Local_Baseline=baseline,Half_Height=level,Left_nm=w[l],Right_nm=w[r],Observed_Width_nm=w[r]-w[l],Boundary_Truncated=l==lo or r==hi-1,Interpretation='离散局部半高宽；无拟合/插值；非仪器校正峰宽'))
        fig,ax=plt.subplots(2,3,figsize=(16,8),layout='constrained');im=ax[0,0].pcolormesh(w,t,s,shading='auto',vmin=0,vmax=65535,rasterized=True);fig.colorbar(im,ax=ax[0,0],label='Raw intensity [official W/cm2; calibration unverified]')
        for ii in np.linspace(0,n-1,4,dtype=int):ax[0,1].plot(w,s[ii],lw=.7,label=f'{t[ii]:g}s')
        ax[0,1].legend()
        for jj in sorted(set([0,jpeak,k//2,k-1])):ax[0,2].plot(t,s[:,jj],lw=.6,label=f'{w[jj]:.3f}nm')
        ax[0,2].legend();ax[1,0].plot(t,s.mean(axis=1),label='mean');ax[1,0].plot(t,np.median(s,axis=1),label='median');ax[1,0].legend();ax[1,1].hist(s.ravel(),100);ax[1,1].set_yscale('log');ax[1,1].set(xlabel='Raw intensity',ylabel='Count (log scale)');ax[1,2].plot(t[1:],l1,label='mean abs adjacent change');ax[1,2].legend()
        for aa in [ax[0,0],ax[0,1]]:aa.set(xlabel='Wavelength (nm)')
        ax[0,0].set(ylabel='Time (s)');ax[0,1].set(ylabel='Raw intensity')
        for aa in [ax[0,2],ax[1,0],ax[1,2]]:aa.set(xlabel='Time (s)',ylabel='Raw intensity / change')
        fig.suptitle(h+' | full heatmap, linear color 0-65535, no sampling; profiles: 4 selected times/wavelengths');fig.savefig(DIRS['S03']/(h+'_光谱结构.png'),dpi=125);plt.close(fig)
        fig,ax=plt.subplots(1,3,figsize=(15,4),layout='constrained');ii,jj=np.where(sat);ax[0].scatter(w[jj],t[ii],s=2);ax[0].set(xlim=(w.min(),w.max()),ylim=(0,t[-1]),xlabel='Wavelength (nm)',ylabel='Time (s)',title='Exact 65535 locations (all)');ax[1].plot(t,sat.sum(axis=1));ax[1].set(xlabel='Time (s)',ylabel='65535 count / row');ax[2].plot(w,sat.sum(axis=0));ax[2].set(xlabel='Wavelength (nm)',ylabel='65535 count / wavelength');fig.suptitle(h+' | all upper-value points, no log/sampling');fig.savefig(DIRS['S04']/(h+'_上限位置分布.png'),dpi=125);plt.close(fig)
        print(f'{num}/10 {h}: {n}x{k}, saturation={sat.sum()}, score>12 candidates={selected.sum()}',flush=True)
        del a,s,ds,localmed,localmad,score,signed
    # Wavelength-only analysis across actual grids; no signal interpolation.
    wa,wb=grids[0],grids[4];assert all(np.array_equal(x,wa) for x in grids[:4]);assert all(np.array_equal(x,wb) for x in grids[4:])
    delta=wa-wb;gridstat=[];gridevidence=[]
    for group,w in [('A',wa),('B',wb)]:
        step=np.diff(w);gridstat.append(dict(Group=group,Min_nm=w.min(),Max_nm=w.max(),Columns=len(w),Step_Min=step.min(),Step_Max=step.max(),Step_Mean=step.mean(),Step_Std=step.std(),Step_Median=np.median(step),Overlap_Min=max(wa.min(),wb.min()),Overlap_Max=min(wa.max(),wb.max()),Column_Diff_A_minus_B_Min=delta.min(),Column_Diff_Max=delta.max(),Mean_Abs_Column_Diff=np.mean(abs(delta)),RMSE_Column_Diff=np.sqrt(np.mean(delta**2))))
    for j in range(len(wa)):
        nb=int(np.argmin(abs(wb-wa[j])));na=int(np.argmin(abs(wa-wb[j])));gridevidence.append(dict(Index=j,Excel_Column=j+2,A_nm=wa[j],B_nm=wb[j],A_minus_B_nm=delta[j],Nearest_B_to_A_Index=nb,Nearest_B_to_A_Distance_nm=abs(wb[nb]-wa[j]),Nearest_A_to_B_Index=na,Nearest_A_to_B_Distance_nm=abs(wa[na]-wb[j]),A_Inside_Common=max(wa.min(),wb.min())<=wa[j]<=min(wa.max(),wb.max()),B_Inside_Common=max(wa.min(),wb.min())<=wb[j]<=min(wa.max(),wb.max())))
    fig,ax=plt.subplots(2,2,figsize=(12,7),layout='constrained');ax[0,0].plot([wa.min(),wa.max()],[0,0],label='A');ax[0,0].plot([wb.min(),wb.max()],[1,1],label='B');ax[0,0].legend();ax[0,0].set(xlabel='Wavelength (nm)',title='Actual coverage')
    for label,w in [('A',wa),('B',wb)]:ax[0,1].hist(np.diff(w),bins=40,alpha=.5,label=label)
    ax[0,1].legend();ax[0,1].set(xlabel='Grid step (nm)',ylabel='Count');ax[1,0].plot(wa,delta);ax[1,0].set(xlabel='A wavelength (nm)',ylabel='Corresponding-column A-B (nm)')
    for label,w in [('A',wa),('B',wb)]:ax[1,1].plot(w[990:1010],np.arange(990,1010),'.-',label=label)
    ax[1,1].legend();ax[1,1].set(xlabel='Actual wavelength (nm)',ylabel='Column index');fig.savefig(DIRS['S02']/'两组网格对比.png',dpi=140);plt.close(fig)
    cross=[]
    for case in cases:
        for m,w,med in zip(manifest,grids,medians):
            j=int(np.argmin(abs(w-case['Wavelength_nm'])));cross.append(dict(Case_ID=case['Case_ID'],Comparison_Heat=m['sheets'][0],Nearest_nm=w[j],Distance_nm=abs(w[j]-case['Wavelength_nm']),Median_Intensity=med[j],Local_Peak_Contrast=med[j]-(med[max(0,j-1)]+med[min(len(w)-1,j+1)])/2,Interpretation='最近物理坐标描述，不把不同位置当同一谱线'))
    writecsv(DIRS['S01']/'S01_光谱基线核验.csv',baselines);writecsv(DIRS['S02']/'S02_波长网格统计.csv',gridstat);writecsv(DIRS['S02']/'S02_波长网格差异证据.csv',gridevidence)
    writecsv(DIRS['S03']/'S03_逐炉光谱统计.csv',stats);writecsv(DIRS['S03']/'S03_逐时刻结构统计.csv',rowstats);writecsv(DIRS['S03']/'S03_逐波长结构统计.csv',wavestats);writecsv(DIRS['S03']/'S03_候选峰宽证据.csv',widths)
    writecsv(DIRS['S04']/'S04_逐炉65535统计.csv',satstats);writecsv(DIRS['S04']/'S04_二维连通区域登记表.csv',components);writecsv(DIRS['S04']/'S04_65535完整位置.csv',satloc);writecsv(DIRS['S04']/'S04_连续段证据.csv',satruns);writecsv(DIRS['S04']/'S04_代表性局部证据.csv',[c for c in cases if c['Type'][0] in 'EF'])
    writecsv(DIRS['S05']/'S05_候选异常登记表.csv',candidates);writecsv(DIRS['S05']/'S05_候选参数与统计结果.csv',sens);writecsv(DIRS['S06']/'S06_代表性案例登记表.csv',cases);writecsv(DIRS['S06']/'S06_跨炉相近波长调查.csv',cross)
    # Single authoritative point register; root issue index links instead of duplicating it.
    writecsv(BASE/'Q1问题登记表.csv',[dict(Issue_ID='A-Q1-S'+str(i),Task_ID=task,Heat_ID='ALL',Observation=obs,Evidence_File=path,Decision_Status='Observed Fact',Interpretation_Status='Hypothesis',Approval_Status='Pending') for i,(task,obs,path) in enumerate([('S02','两组原始网格不同','专项分析/S02_波长网格调查/S02_波长网格差异证据.csv'),('S04','65535位置与连通性已统计，未确认无效','专项分析/S04_65535候选饱和调查/S04_65535完整位置.csv'),('S05','全部局部分数候选位置','专项分析/S05_其他候选异常调查/S05_候选异常登记表.csv'),('S06','代表案例与反例，非物理真值标签','专项分析/S06_谱峰与异常反例研究/S06_代表性案例登记表.csv')],1)])
    for (p,hh),v in zip(sourcepaths,verified):assert hashfile(p)==hh;v['Hash_After_OK']=True
    BASE.joinpath('研究成果').mkdir(exist_ok=True)
    record=dict(task='A-Q1-S01-S07-R1',date='2026-11-27',sources=verified,python=platform.python_version(),dependencies={p:importlib.metadata.version(p) for p in ['numpy','pyxlsb','matplotlib','pymupdf']},seed='deterministic; no random experiment executed',parameters=dict(local_neighbors=4,MAD_multiplier=1.4826,score_floor=1,thresholds=[12,20,30],boundary='exclude first/last rows/columns from score',saturation='==65535, four/eight adjacency',near_upper_threshold=60000),runtime_seconds=time.time()-start,code_sha256=hashfile(Path(__file__)),branch=subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip(),baseline_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),raw_changed=False,preprocessing=False,prediction_training=False,migrated_code_validation='syntax and actual pyxlsb conventions checked; legacy top-level full generator not rerun',official_q1='去除异常、连续重建离散光谱，并画全部十炉连续3D图；本轮仅调查，非完成最终Q1模型')
    doc=__import__('pymupdf').open(args.source_root/'2026 APMCM Problem B.pdf');text=doc[2].get_text();q=text[text.index('The spectral data'):text.index('Cumulative',text.index('The spectral data'))]
    record['official_q1_page']=3;record['official_q1_text']=q
    (BASE/'研究成果/运行核验.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('COMPLETE: all ten sources unchanged; descriptive outputs saved.',flush=True)
if __name__=='__main__':main()
