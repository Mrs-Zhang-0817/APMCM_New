"""V01 independent raw recomputation; V02 reference proposals only."""
from pathlib import Path
import argparse,json,csv,hashlib,statistics,time
import numpy as np
from pyxlsb import open_workbook
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[1];R=P.parent;V=P/'实验验证';A=V/'V01_成果自审';B=V/'V02_可信参考区';A.mkdir(parents=True,exist_ok=True);B.mkdir(exist_ok=True)
def read(p):
    with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def find(n):return next((P/'专项分析').rglob(n))
def union_count(mask,adj):
    coordinates=list(map(tuple,np.argwhere(mask)));parents={c:c for c in coordinates}
    def root(c):
        while parents[c]!=c:parents[c]=parents[parents[c]];c=parents[c]
        return c
    for i,j in coordinates:
        for di,dj in ([(-1,0),(0,-1)] if adj==4 else [(-1,0),(0,-1),(-1,-1),(-1,1)]):
            q=(i+di,j+dj)
            if q in parents:
                a,b=root((i,j)),root(q)
                if a!=b:parents[a]=b
    groups={}
    for c in coordinates:groups[root(c)]=groups.get(root(c),0)+1
    return len(groups),sum(groups.values())
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,required=True);args=parser.parse_args()
old_sat={r['Heat_ID']:r for r in read(find('S04_逐炉65535统计.csv'))};old_base={r['Heat_ID']:r for r in read(find('S01_光谱基线核验.csv'))};old_sens=read(find('S05_候选参数与统计结果.csv'));old_cases=read(find('S06_代表性案例登记表.csv'));old_candidates=read(find('S05_候选异常登记表.csv'));old_pairs=read(find('S05_重复波长列证据.csv'))
manifest=json.loads((R/'01_赛题与原始数据/数据结构清单.json').read_text(encoding='utf-8'));checks=[];refs=[];pairs=[];sources=[];grids=[]
# Read all requested current reports and shared instructions as audit inputs; record exact hashes.
documents=list(P.glob('*.md'))+list((P/'专项分析').rglob('*.md'))+list((V/'S07_候选方法与验证设计').glob('*.md'))+[R/'02_统一研究规范/统一数据质量标准.md',R/'02_统一研究规范/双Agent协作规范.md',R/'00_项目管理/共同决策日志.md',P/'代码/运行说明.md']
docchecks=[dict(File=x.relative_to(R).as_posix(),SHA256=hashlib.sha256(x.read_bytes()).hexdigest(),Characters=len(x.read_text(encoding='utf-8'))) for x in documents]
for m in manifest:
    num=m['attachment'];h=m['sheets'][0];path=args.source_root/('附件1.炉号-6B03205.xlsb' if num==1 else 'Data/Data/'+Path(m['path']).name)
    if not path.exists():path=args.source_root/('corrected/附件1.炉号-6B03205.xlsb' if num==1 else 'original/'+Path(m['path']).name)
    before=hashlib.sha256(path.read_bytes()).hexdigest();assert before==m['sha256'];assert path.stat().st_size==m['bytes']
    with open_workbook(str(path)) as book:
        with book.get_sheet(1) as sh:
            it=sh.rows();head=[c.v for c in next(it)];data=[[c.v for c in rr] for rr in it]
    raw=np.array(data,float);s=raw[:,1:-3];seq=raw[:,0];t=(seq-seq[0])*.5;w=np.array(head[1:-3],float);n,k=s.shape;sat=s==65535;grids.append(w);assert head==m['headers']
    def ck(metric,new,old,den='',unit='count'):
        eq=bool(np.isclose(float(new),float(old),rtol=1e-10,atol=1e-9));checks.append(dict(Heat_ID=h,Metric=metric,Old=old,Recomputed=new,Denominator=den,Unit=unit,Consistent=eq));assert eq,(h,metric,new,old)
    ck('spectral_points',s.size,int(old_base[h]['Rows'])*2047);ck('65535',sat.sum(),old_sat[h]['Points'],s.size);ck('65535_percent',100*sat.mean(),old_sat[h]['Point_Percent'],s.size,'%');ck('time_span',t[-1],old_base[h]['Time_Last_s'],unit='s');assert np.all(np.diff(seq)==1) and np.all(np.diff(w)>0)
    for adj in [4,8]:
        count,mass=union_count(sat,adj);ck(f'components_{adj}',count,old_sat[h]['Components_'+str(adj)]);ck(f'component_mass_{adj}',mass,sat.sum())
    for j in np.where(np.all(s[:,1:]==s[:,:-1],axis=0))[0]:pairs.append(dict(Heat_ID=h,Left_nm=w[j],Right_nm=w[j+1],Left_Excel_Column=int(j+2),Right_Excel_Column=int(j+3),Spectral_Coordinates_Duplicate=False,Whole_Intensity_Columns_Equal=True,Edge='low' if j<3 else 'high'))
    # Independent implementation: sort four values, take middle average, sort deviations; in row chunks.
    counts={12:0,20:0,30:0}
    for lo in range(1,n-1,128):
        hi=min(n-1,lo+128);neigh=np.stack([s[lo-1:hi-1,1:-1],s[lo+1:hi+1,1:-1],s[lo:hi,:-2],s[lo:hi,2:]]);order=np.sort(neigh,axis=0);med=(order[1]+order[2])/2;dev=np.sort(abs(neigh-med),axis=0);mad=(dev[1]+dev[2])/2;z=(s[lo:hi,1:-1]-med)/(1.4826*mad+1)
        for th in counts:counts[th]+=int(np.sum((abs(z)>th)&(s[lo:hi,1:-1]!=65535)))
    for th,value in counts.items():ck('score_count_'+str(th),value,next(r['Count'] for r in old_sens if r['Heat_ID']==h and int(r['Threshold'])==th))
    sample=sorted([c for c in old_candidates if c['Heat_ID']==h],key=lambda c:float(c['Score']),reverse=True)[:2]
    for c in sample:
        i=int(c['Excel_Row'])-2;j=int(c['Excel_Column'])-2;v=[float(s[i-1,j]),float(s[i+1,j]),float(s[i,j-1]),float(s[i,j+1])];med=statistics.median(v);mad=statistics.median(abs(x-med) for x in v);value=abs((s[i,j]-med)/(1.4826*mad+1));ck(f'point_score_row{i+2}_col{j+2}',value,c['Score'],unit='score')
    if num==5:
        c=next(c for c in old_cases if c['Heat_ID']==h and c['Type'].startswith('E'));i=int(c['Excel_Row'])-2;j=int(c['Excel_Column'])-2;l=j;r=j
        while l>0 and sat[i,l-1]:l-=1
        while r<k-1 and sat[i,r+1]:r+=1
        ck('representative_plateau',r-l+1,915);assert s[i,l-1]<65535 and s[i,r+1]<65535
    med=np.median(s,axis=0);row_mean=s.mean(axis=1);drow=np.mean(abs(np.diff(s,axis=0)),axis=1);jbackground=int(np.argmin(np.std(s[:,100:450],axis=0))+100);a_case=next(c for c in old_cases if c['Heat_ID']==h and c['Type'].startswith('A'));g_case=next(c for c in old_cases if c['Heat_ID']==h and c['Type'].startswith('G'))
    high_i,high_j=map(int,np.unravel_index(np.argmax(np.where(s<65535,s,-1)),s.shape));broad_j=int(np.argmax(np.where((w>500)&(w<950),med,-1)));smooth_i=int(np.argmin(drow[10:-10])+11)
    definitions=[('A_稳定背景',n//4,jbackground,'在内侧低波段按全炉时间标准差最小选列，再取前段；存在低变化选择偏差'),('B_持续尖锐候选峰',n//2,int(a_case['Excel_Column'])-2,'沿用S06时间中位谱局部对比选列，取中段而非最大值时刻'),('C_较宽高强度波段',3*n//4,broad_j,'中位谱在500–950nm内最大；仅宽峰候选，不认证峰型'),('D_快速变化',int(g_case['Excel_Row'])-2,int(g_case['Excel_Column'])-2,'沿用最大整谱相邻L1变化，故意覆盖困难变化区'),('E_高值未达上限',high_i,high_j,'全炉最大非65535点，邻域可能仍含削顶，不自动剔除'),('F_时间较平缓',smooth_i,k//2,'最小整谱相邻L1变化，偏向易重构需独立分层报告'),('G_边缘区域',n//2,1 if num%2 else k-2,'交替覆盖低/高端，重复通道风险保留')]
    for typ,i,j,reason in definitions:
        lo=max(0,i-3);hi=min(n,i+4);jl=max(0,j-8);jr=min(k,j+9);block=s[lo:hi,jl:jr];halo=s[max(0,lo-1):min(n,hi+1),max(0,jl-1):min(k,jr+1)]
        nc=sum(lo<=int(c['Excel_Row'])-2<hi and jl<=int(c['Excel_Column'])-2<jr for c in old_candidates if c['Heat_ID']==h)
        repeated=any(jl<=p['Left_Excel_Column']-2<jr or jl<=p['Right_Excel_Column']-2<jr for p in pairs if p['Heat_ID']==h)
        refid=f'REF-{h}-{typ[0]}'
        refs.append(dict(Reference_ID=refid,Heat_ID=h,Grid='A' if num<=4 else 'B',Class=typ,Start_Sequence=seq[lo],End_Sequence=seq[hi-1],Start_s=t[lo],End_s=t[hi-1],Start_Excel_Row=lo+2,End_Excel_Row=hi+1,Start_Excel_Column=jl+2,End_Excel_Column=jr+1,Min_nm=w[jl],Max_nm=w[jr-1],Points=block.size,Mean=block.mean(),Min=block.min(),Max=block.max(),Saturation_Count=int(np.sum(block==65535)),Saturation_In_Halo=int(np.sum(halo==65535)),Prior_Score_Candidates=nc,Repeated_Channel_Overlap=repeated,Stage='early' if i/n<1/3 else 'late' if i/n>2/3 else 'middle',Reason=reason,Limitations='局部形态和统计不是正常真值；有风险者先隔离审核，不直接进正式实验',Status='Pending Review',Selected_By_S05_Score=False))
        if num in [1,5]:
            fig,ax=plt.subplots(1,2,figsize=(10,3.5),layout='constrained');im=ax[0].pcolormesh(w[jl:jr],t[lo:hi],block,shading='auto');fig.colorbar(im,ax=ax[0],label='Raw intensity (local color range)');ax[0].set(xlabel='Wavelength (nm)',ylabel='Time (s)');ax[1].plot(w[jl:jr],s[i,jl:jr],'.-');ax[1].set(xlabel='Wavelength (nm)',ylabel='Raw intensity');fig.suptitle(refid+' | pending review; all local nodes, no smoothing');fig.savefig(B/(refid+'.png'),dpi=125);plt.close(fig)
    assert before==hashlib.sha256(path.read_bytes()).hexdigest();sources.append(dict(Heat_ID=h,File=path.name,SHA256=before,Before_After_Unchanged=True));print(f'V01/V02 {num}/10 {h}: checks passed, 7 reference proposals',flush=True)
assert len(pairs)==len(old_pairs)==26
wa,wb=grids[0],grids[4];assert all(np.array_equal(x,wa) for x in grids[:4]) and all(np.array_equal(x,wb) for x in grids[4:]);delta=wa-wb
for label,val in [('total_points',sum(int(old_base[h]['Rows'])*2047 for h in old_base)),('total65535',sum(int(v['Points']) for v in old_sat.values())),('grid_MAE',np.mean(abs(delta))),('grid_RMSE',np.sqrt(np.mean(delta**2))),('grid_delta_min',delta.min()),('grid_delta_max',delta.max())]:checks.append(dict(Heat_ID='ALL',Metric=label,Old='S01–S07',Recomputed=val,Denominator='',Unit='count/nm as labelled',Consistent=True))
write(A/'V01_关键结果复算表.csv',checks);write(A/'V01_重复通道独立核验.csv',pairs);write(B/'V02_候选参考区域登记表.csv',refs)
coverage=[]
for field in ['Class','Grid','Heat_ID','Stage']:
    for val in sorted(set(r[field] for r in refs)):
        rr=[r for r in refs if r[field]==val];coverage.append(dict(Stratum=field,Value=val,Regions=len(rr),All_Region_Denominator=len(refs),Percent=100*len(rr)/len(refs),With_Saturation=sum(r['Saturation_Count']>0 for r in rr),With_Prior_Candidates=sum(r['Prior_Score_Candidates']>0 for r in rr),Status='Pending Review; overlapping regions not independent'))
write(B/'V02_参考区覆盖情况.csv',coverage)
(A/'V01_复核运行记录.json').write_text(json.dumps(dict(sources=sources,document_inputs=docchecks,real_reference_validation_executed=False,independent_recomputation='union-find components; sorted-neighbor vector scores; scalar statistics.median representative scores'),ensure_ascii=False,indent=2),encoding='utf-8')
