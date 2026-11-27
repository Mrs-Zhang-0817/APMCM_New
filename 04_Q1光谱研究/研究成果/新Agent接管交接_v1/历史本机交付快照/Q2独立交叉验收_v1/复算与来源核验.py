"""CR-Q2-b35ac738-v02: targeted read-only audit of heats 5 and 8.
No EDA rerun, plot, cleaning, reconstruction, interpolation, or training.
Never run peer main(). Frozen source reader and corr() only are exercised.
"""
from pathlib import Path
from datetime import datetime,timezone
import csv,io,json,hashlib,subprocess,ast,types,sys
import numpy as np
from pyxlsb import open_workbook
O=Path(__file__).resolve().parent;R=O.parents[2];DATA=R.parent
Q='b35ac738d01642efe11b6e1a759572cace8b0885';Q1='346c64ebe864e7f09fa2de227e7b72709fbb8670';PREFIX='05_Q2供氧与烟气研究/'
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,s):
    p=O/p;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='') as f:f.write(s)
def dump(p,x):write(p,json.dumps(x,ensure_ascii=False,indent=2))
def csvout(p,rows):
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);write(p,'\ufeff'+s.getvalue())
assert git('rev-parse','HEAD').decode().strip()==Q1
assert git('branch','--show-current').decode().strip()=='q1-spectral'
tracked_before={p:sha((R/p).read_bytes()) for p in git('ls-files','-z').decode().split('\0') if p}
sources=[]
def peer(path):
    b=git('show',Q+':'+PREFIX+path);sources.append(dict(Repository='https://github.com/lf21szgmail-sys/Test',Commit=Q,Path=PREFIX+path,Bytes=len(b),SHA256=sha(b)));return b
def table(path):return list(csv.DictReader(io.StringIO(peer(path).decode('utf-8-sig'))))
md={p:peer(p).decode('utf-8-sig') for p in ('Q2_专项调查总报告.md','Q2当前研究进度.md','Q2交叉审核交接说明.md',*[f'专项分析/{p}' for p in ('S01_数据基线.md','S02_零值与常量段.md','S03_数值更新.md','S04_附件5.md','S05_突变上下文.md','S06_供氧烟气关系.md','S07_候选方法与验证.md')])}
reader=peer('代码/q2_load.py');runner=peer('代码/q2_run.py')
write('固定输入/q2_load.py',reader.decode('utf-8'));write('固定输入/q2_run.py',runner.decode('utf-8'))
module=types.ModuleType('frozen_q2_reader');module.__file__=str(O/'固定输入/q2_load.py');exec(compile(reader,'frozen_q2_load.py','exec'),module.__dict__)
# Execute only the standalone pure corr function, not imports/CLI/report writers.
tree=ast.parse(runner.decode('utf-8-sig'));fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='corr')
ns={'np':np};exec(compile(ast.Module(body=[fn],type_ignores=[]),'frozen_corr.py','exec'),ns);peer_corr=ns['corr']
src=table('研究成果/S01-S07/实际来源.csv');desc=table('研究成果/S01-S07/描述关系.csv');lag=table('研究成果/S01-S07/探索滞后曲线.csv');intervals=table('研究成果/S01-S07/零值与常量段.csv');local=table('研究成果/S01-S07/局部原值.csv');events=table('研究成果/S01-S07/候选突变.csv')
manifest=json.loads((R/'01_赛题与原始数据/数据结构清单.json').read_text(encoding='utf-8'))
assert len(src)==len(manifest)==10
assert all(s['heat']==m['sheets'][0] and s['sha256']==m['sha256'] for s,m in zip(src,manifest))
checks=[]
def ck(h,metric,value,expected,location,unit='',scope='本轮原始数据定点复算'):
    match=bool(np.isclose(float(value),float(expected),rtol=1e-10,atol=1e-8)) if expected is not None else None
    basis='新增证据，无队友数值对照' if expected is None else 'Q2报告或发布统计/事件表'
    if '读取器' in metric:basis='两种实际读取器互相核对'
    if '端点恒等式' in metric or '左右平均' in metric:basis='解析恒等式右端，非队友新增实验'
    if metric in ('光谱均值前','光谱均值后'):basis='历史Q1跨模态证据，本轮原始重算'
    if '常量输入' in metric:basis='审核者函数边界期望，非Q2模型性能'
    checks.append(dict(Check_ID='Q2REC-%03d'%(len(checks)+1),Heat_ID=h,Metric=metric,Recomputed=value,Reference_Value=expected if expected is not None else '未报告，本轮补充证据',Comparison_Basis=basis,Match=match if match is not None else 'Not Applicable',Location=location,Unit=unit,Scope=scope,Interpretation='描述性证据；不自动作为异常或因果判断'))
    if match is False:raise AssertionError((h,metric,value,expected))
def corr(x,y):
    return float(np.corrcoef(x,y)[0,1]) if len(x)>=3 and np.std(x)>0 and np.std(y)>0 else None
def scan(x,y,drop_event=None,lo=-60,hi=60):
    out=[];N=len(x)
    for k in range(lo,hi+1):
        ix=np.arange(max(0,-k),min(N,N-k));iy=ix+k;ok=np.ones(len(ix),bool)
        if drop_event is not None:ok=(ix!=drop_event)&(iy!=drop_event)
        r=corr(x[ix[ok]],y[iy[ok]])
        out.append(dict(Lag_nodes=k,Lag_s=.5*k,Pairs=int(ok.sum()),r=r))
    return out
raw={};spectra={};rawsources=[]
for num in (5,8):
    m=manifest[num-1];h=m['sheets'][0];path=DATA/'Data/Data'/Path(m['path']).name
    before=sha(path.read_bytes());assert before==m['sha256']
    vals=[];cache={}
    with open_workbook(str(path)) as book:
        assert book.sheets==[h]
        with book.get_sheet(1) as sh:
            it=sh.rows();head=[c.v for c in next(it)];assert len(head)==2051
            for i,row in enumerate(it):
                v=[c.v for c in row];vals.append([v[j] for j in (0,2048,2049,2050)])
                if num==5 and 732<=i<=772:cache[i]=np.asarray(v[1:2048],float)
    a=np.asarray(vals,float);assert np.isfinite(a).all() and (np.diff(a[:,0])==1).all()
    labels,other=module.read_book(path,h);other=np.asarray(other,float)
    ck(h,'独立pyxlsb与Q2自定义读取器四列最大差',np.max(abs(a-other)),0,'Sequence/累计氧/CO2/CO全部原节点')
    assert np.array_equal(a,other);raw[h]=a;spectra[h]=cache
    after=sha(path.read_bytes());assert after==before
    rawsources.append(dict(Attachment=num,Heat_ID=h,File=path.name,Bytes=path.stat().st_size,SHA256=before,Hash_After=after,Unchanged=True,Rows=len(a),Headers=[head[j] for j in (0,2048,2049,2050)],Finite=True,Independent_Readers_Exact=True))
    print('已读取并双读取器核对',h,len(a),flush=True)
    t=.5*(a[:,0]-a[0,0])
    for j,gas in [(2,'CO2'),(3,'CO')]:
        d=next(r for r in desc if r['heat']==h and r['gas']==gas);g=a[:,j];dt=np.diff(t)
        L=float(np.sum(dt*g[:-1]));U=float(np.sum(dt*g[1:]));T=float(np.sum(dt*(g[:-1]+g[1:])/2))
        for metric,val,key in [('左矩形积分',L,'cumulative_g_left_m3'),('右矩形积分',U,'cumulative_g_right_m3'),('梯形积分',T,'cumulative_g_trapezoid_m3')]:ck(h,gas+'_'+metric,val,float(d[key]),f'记录窗0–{t[-1]}s','m3')
        ck(h,gas+'_右减左端点恒等式',U-L,.5*(g[-1]-g[0]),'固定步长dt=0.5s','m3')
        ck(h,gas+'_梯形为左右平均',T,(L+U)/2,'同一记录窗','m3')
        ck(h,gas+'_原值O与流率相关',corr(a[:,1],g),float(d['r_O_g']),'全记录窗')
        ck(h,gas+'_一阶差分相关',corr(np.diff(a[:,1]),np.diff(g)),float(d['r_dO_dg']),'n−1个转移')
        full=scan(np.diff(a[:,1]),np.diff(g),lo=0)
        expected=[r for r in lag if r['heat']==h and r['gas']==gas]
        assert len(full)==len(expected)==61
        maxerror=max(abs(v['r']-float(e['r_dO_dg'])) for v,e in zip(full,expected));ck(h,gas+'_61个原滞后r最大复算差',maxerror,0,'0–30s/0.5s步长')
        best=max(full,key=lambda r:r['r']);ck(h,gas+'_最大带符号相关峰滞后',best['Lag_s'],float(d['best_positive_lag_s']),'0–30s','s')
        ck(h,gas+'_最大带符号相关峰值',best['r'],float(d['r_at_lag']),'0–30s')
        ck(h,gas+'_常量输入返回不可计算',peer_corr(np.ones(5),np.arange(5)) is None,True,'Q2 corr()直接调用','boolean','审核者纯函数边界测试')
# Heat5 event: original diff index751 corresponds Excel753 ->754.
h='6C02057';a=raw[h];t=.5*(a[:,0]-1);idx=752;e=751
event={};expected_before=[3393.75,13.32,30.37];expected_after=[3448.66,.63,.51]
for j,label in enumerate(('Oxygen','CO2','CO'),1):
    ck(h,label+'_事件前值',a[idx-1,j],expected_before[j-1],'Sequence752 / Excel753 / t375.5s')
    ck(h,label+'_事件后值',a[idx,j],expected_after[j-1],'Sequence753 / Excel754 / t376s')
    ck(h,label+'_事件变化',a[idx,j]-a[idx-1,j],expected_after[j-1]-expected_before[j-1],'Excel753→754')
    peer_event=next(r for r in events if r['heat']==h and r['variable']==label and int(r['rank'])==1)
    ck(h,label+'_Q2事件仍保留',float(peer_event['delta']),a[idx,j]-a[idx-1,j],'Q2候选突变.csv rank1')
    rec=next(r for r in local if r['heat']==h and r['event']==label+'1' and int(r['excel_row'])==754)
    ck(h,label+'_Q2局部原值保留事件后值',float(rec[{'Oxygen':'oxygen_m3','CO2':'co2_m3_s','CO':'co_m3_s'}[label]]),a[idx,j],'Q2局部原值.csv Excel754')
before=spectra[h][751];after=spectra[h][752]
event=dict(Excel_Before=753,Excel_After=754,Sequence_Before=float(a[751,0]),Sequence_After=float(a[752,0]),Time_Before=float(t[751]),Time_After=float(t[752]),Oxygen_Delta=float(a[752,1]-a[751,1]),CO2_Delta=float(a[752,2]-a[751,2]),CO_Delta=float(a[752,3]-a[751,3]),Spectrum_Mean_Before=float(before.mean()),Spectrum_Mean_After=float(after.mean()),Spectrum_Mean_Relative_Change_pct=float((after.mean()/before.mean()-1)*100),Spectrum_65535_Before=int((before==65535).sum()),Spectrum_65535_After=int((after==65535).sum()),Columns=2047)
oldpath=R/'04_Q1光谱研究/实验验证/队友成果综合审核/附件5跨模态事件证据.csv';old=list(csv.DictReader(oldpath.open(encoding='utf-8-sig')))[0]
ck(h,'光谱均值前',event['Spectrum_Mean_Before'],float(old['Spectrum_Mean_Before']),'Excel753全部2047光谱列','原强度单位','本轮原始重算并对照历史证据，不是Q2指标')
ck(h,'光谱均值后',event['Spectrum_Mean_After'],float(old['Spectrum_Mean_After']),'Excel754全部2047光谱列','原强度单位','本轮原始重算并对照历史证据，不是Q2指标')
ck(h,'光谱均值变化百分比',event['Spectrum_Mean_Relative_Change_pct'],None,'分母为事件前2047列均值','%')
ck(h,'供氧相邻窗差商',event['Oxygen_Delta']/.5,109.82,'0.5s记录窗','m3/s')
window=[]
for i in range(742,762):window.append(dict(Heat_ID=h,Window='Before10' if i<idx else 'After10',Excel_Row=i+2,Sequence=float(a[i,0]),Time_s=float(t[i]),Oxygen=float(a[i,1]),CO2=float(a[i,2]),CO=float(a[i,3]),Spectrum_Mean=float(spectra[h][i].mean()),Spectrum_65535=int((spectra[h][i]==65535).sum())))
csvout('附件5事件前后窗口.csv',window)
sens=[];lagrows=[]
for j,gas in ((2,'CO2'),(3,'CO')):
    x=np.diff(a[:,1]);y=np.diff(a[:,j])
    for scenario,mask in [('All',np.ones(len(x),bool)),('Exclude_Event_Transition',np.arange(len(x))!=e)]:
        r=corr(x[mask],y[mask]);ck(h,gas+'_差分相关_'+scenario,r,None,'相同原始索引配对；仅统计对照，不删改数据')
        sens.append(dict(Gas=gas,Scenario=scenario,Metric='Zero_lag_differences_r',Value=r,Pairs=int(mask.sum()),Scope='统计敏感性，非清洗'))
    for scenario,drop in [('All',None),('Exclude_Event_Endpoints',e)]:
        profile=scan(x,y,drop)
        for r in profile:lagrows.append(dict(Heat_ID=h,Gas=gas,Scenario=scenario,**r,Rule='保留原转移索引；若任一配对分量来自事件转移则只在统计对照排除，不压缩时间'))
        for domain in [('Nonnegative',[r for r in profile if r['Lag_nodes']>=0]),('Both_Signs',profile)]:
            name,sub=domain;best=max(sub,key=lambda r:r['r']);ab=max(sub,key=lambda r:abs(r['r']))
            for metric,v in [('Max_Signed_r',best['r']),('Max_Signed_Lag_s',best['Lag_s']),('Max_Absolute_Signed_r',ab['r']),('Max_Absolute_Lag_s',ab['Lag_s'])]:sens.append(dict(Gas=gas,Scenario=scenario+'_'+name,Metric=metric,Value=v,Pairs=best['Pairs'] if metric.startswith('Max_Signed') else ab['Pairs'],Scope='相关极值不是物理延迟'))
    for radius in (5,10,20):
        times=t[1:];ok=(times>=376-radius)&(times<=376+radius)
        for remove in (False,True):
            take=ok&(np.arange(len(x))!=e) if remove else ok
            sens.append(dict(Gas=gas,Scenario=f'Local_radius_{radius}s_exclude_{remove}',Metric='Zero_lag_differences_r',Value=corr(x[take],y[take]),Pairs=int(take.sum()),Scope='窗口在实际记录边界裁切，不重建记录窗'))
csvout('附件5相关与滞后敏感性.csv',sens);csvout('附件5双向滞后配对明细.csv',lagrows)
# Heat8 zero episodes: preserve raw sequences and distinguish span from physical duration.
h8='6C02060';z=raw[h8];tz=.5*(z[:,0]-1);zeros=[]
for j,gas in [(2,'CO2'),(3,'CO')]:
    edges=np.diff(np.r_[False,z[:,j]==0,False].astype(int));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)-1
    expected=[r for r in intervals if r['heat']==h8 and r['variable']==gas and r['kind']=='zero'];assert len(expected)==len(starts)
    for s,end in zip(starts,ends):
        peerrow=next(r for r in expected if int(float(r['sequence_first']))==z[s,0])
        row=dict(Heat_ID=h8,Gas=gas,Start_Sequence=int(z[s,0]),End_Sequence=int(z[end,0]),Start_Excel_Row=int(s+2),End_Excel_Row=int(end+2),Start_s=float(tz[s]),End_s=float(tz[end]),Points=int(end-s+1),Point_Denominator=len(z),Observed_Span_s=float(tz[end]-tz[s]),Physical_Duration='未确定：未约定观测支持与实际仪器时钟',Before_Value=float(z[s-1,j]) if s else None,After_Value=float(z[end+1,j]) if end+1<len(z) else None,Other_Gas_Zero_Count=int((z[s:end+1,5-j]==0).sum()),Blank_Nonfinite_Count=0,Interpretation='零为原始有限观测；数值保持不等于仪器停更，零编码机制未确认')
        zeros.append(row)
        for key,pk in [('Start_Sequence','sequence_first'),('End_Sequence','sequence_last'),('Start_Excel_Row','excel_first'),('End_Excel_Row','excel_last'),('Points','points'),('Observed_Span_s','observed_span_s')]:ck(h8,gas+'_零段'+str(row['Start_Sequence'])+'_'+key,row[key],float(peerrow[pk]),f"Sequence{row['Start_Sequence']}–{row['End_Sequence']}")
csvout('附件8内部零段复算.csv',zeros)
# Known mathematical counterexamples, not peer model performance.
synthetic=[];rng=np.random.default_rng(20261127)
for delay in (6,-6):
    xx=rng.normal(size=160);yy=rng.normal(size=160)
    if delay>0:yy[delay:]=xx[:-delay]
    else:yy[:delay]=xx[-delay:]
    p=scan(xx,yy,lo=-20,hi=20);best=max(p,key=lambda r:r['r'])
    assert best['Lag_nodes']==delay and np.isclose(best['r'],1)
    synthetic.append(dict(Test='Known_delay_sign_'+str(delay),Passed=True,Known_Lag_s=.5*delay,Recovered_Lag_s=best['Lag_s'],r=best['r'],Scope='审核者合成索引检验，不是Q2延迟模型验收或物理运输验证'))
assert peer_corr(np.ones(10),np.arange(10)) is None
synthetic.append(dict(Test='Constant_unidentifiable',Passed=True,Result='None',Scope='Q2纯函数实际调用；无激励相关不可计算'))
slopes=np.diff([0.,1.,3.])/np.diff([0.,1.,2.]);assert slopes[0]!=slopes[1]
synthetic.append(dict(Test='Piecewise_linear_O_derivative_jump',Passed=True,Left_Derivative=float(slopes[0]),Right_Derivative=float(slopes[1]),Scope='解析反例：累计函数可C0，流率不连续；未对真实数据拟合'))
dump('审核者合成反例.json',dict(seed=20261127,tests=synthetic,peer_continuous_model_tested=False,physical_delay_tested=False))
# Check inherited all-heat boundary count from published summary only: do not reread 10 raw heats.
boundary=sum(r['boundary']=='True' for r in desc);ck('All10_published_only','已发表20组边界峰计数',boundary,14,'Q2描述关系.csv','groups','本轮读取发布表复核计数；未重跑十炉原始扫描')
assert len(desc)==20
ck('All10_published_only','已发表20组0秒边界计数',sum(float(r['best_positive_lag_s'])==0 for r in desc),13,'Q2描述关系.csv','groups','发布表复核')
# Version comparison treats byte differences, newline differences and substantive differences separately.
comparisons=[]
for path in [r['Path'] for r in sources]:
    p=path.removeprefix(PREFIX)
    a=git('show',Q+':'+path)
    try:b=git('show','origin/q2-gas-oxygen:'+path)
    except subprocess.CalledProcessError:continue
    comparisons.append(dict(Path=path,Test_Commit=Q,Formal_Commit=git('rev-parse','origin/q2-gas-oxygen').decode().strip(),Same_Bytes=a==b,Same_After_CRLF_Normalization=a.replace(b'\r\n',b'\n')==b.replace(b'\r\n',b'\n'),Test_SHA256=sha(a),Formal_SHA256=sha(b)))
csvout('Test与正式Q2版本对照.csv',comparisons)
csvout('Q2关键问题复算表.csv',checks)
csvout('固定输入来源及SHA256.csv',sources)
assert all(sha((R/p).read_bytes())==digest for p,digest in tracked_before.items())
assert git('rev-parse','HEAD').decode().strip()==Q1
summary=dict(task='A-Q1-CR-Q2-002',review_id='CR-Q2-b35ac738-v02',audit_utc=datetime.now(timezone.utc).isoformat(),reviewed_repository='https://github.com/lf21szgmail-sys/Test',reviewed_branch='q2-gas-oxygen',reviewed_commit=Q,Q1_fixed=Q1,previous_review_same_Test_commit=True,raw_sources=rawsources,checks=len(checks),compared_checks=sum(r['Match'] is True for r in checks),additional_evidence=sum(r['Match']=='Not Applicable' for r in checks),all_compared_match=True,event=event,zeros=zeros,sensitivity=sens,synthetic=synthetic,sources_count=len(sources),Q2_continuous_model_implemented=False,Q2_delay_model_truth_validation=False,tracked_files_unchanged=len(tracked_before),originals_unchanged=True,real_data_cleaning=False,real_masking=False,model_training=False,plots_generated=False,joint_approval='Pending',ready_for_first_real_validation=False,scope='仅两炉目标四变量及附件5局部光谱；其他炉仅已发表表格/历史证据')
dump('复算汇总与验收证据.json',summary)
print(json.dumps(dict(checks=len(checks),matched=summary['compared_checks'],additional=summary['additional_evidence'],event=event,zeros=zeros,sensitivity=[s for s in sens if s['Metric']=='Zero_lag_differences_r'],all_sources_unchanged=True),ensure_ascii=False,indent=2))
