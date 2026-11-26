"""J01-J05: read original observations, descriptive review only; no preprocessing."""
from pathlib import Path
import sys,json,csv,hashlib
ROOT=Path(__file__).resolve().parents[2]
import os
import numpy as np
from pyxlsb import open_workbook
P=Path(os.environ.get('APMCM_OUTPUT_ROOT', ROOT/'本地复现输出'));T=P/'05_Results/Tables';E=P/'02_Data_Exploration/Common'
if (P/'Collaborative_Research_Protocol.md').exists():
    raise RuntimeError('Later collaboration standards exist. This historical J01-J05 builder must not overwrite current shared documents; submit a versioned change proposal instead.')
def read(p):
    with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def csvout(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def save(n,s):(P/n).write_text(s.strip()+'\n',encoding='utf-8')
def ranges(mask):
    d=np.diff(np.r_[False,mask,False].astype(int));return list(zip(np.where(d==1)[0],np.where(d==-1)[0]-1))
manifest=json.loads((T/'source_manifest.json').read_text(encoding='utf-8'))
previous={r['heat']:r for r in read(T/'ten_heat_overview.csv')}
oldissues=read(P/'Data_Issue_Register.csv');issues=[];rows=[];checks=[];relationships=[];events=[];topjumps=[];grids=[]
def issue(cat,h,v,obs,ev,impact,invest,status='事实已确认；成因未确认',loc='全观测窗口',legacy=''):
    issues.append(dict(Issue_ID=f'JQ{len(issues)+1:03}',Category=cat,Heat_ID=h,Variable=v,Location=loc,Observation=obs,Evidence=ev,Potential_Impact=impact,Current_Status=status,Recommended_Further_Investigation=invest,Legacy_Issue_ID=legacy))
for m in manifest:
    path=Path(m['path']);num=m['attachment'];sha=hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha==m['sha256'],f'Changed source: {path}'
    if num==1:assert path==Path(os.environ.get('APMCM_DATA_ROOT', ROOT/'01_赛题与原始数据/本地数据'))/'corrected/附件1.炉号-6B03205.xlsb','Corrected attachment 1 required'
    with open_workbook(str(path)) as w:
        names=w.sheets[:]
        with w.get_sheet(1) as sh:
            it=sh.rows();headers=[c.v for c in next(it)];data=[];missing=0;nonnum=0
            for rr in it:
                values=[None]*len(headers)
                for c in rr:
                    if c.c<len(headers):values[c.c]=c.v
                converted=[]
                for v in values:
                    if v is None or v=='':missing+=1;converted.append(np.nan)
                    else:
                        try:converted.append(float(v))
                        except (TypeError,ValueError):nonnum+=1;converted.append(np.nan)
                data.append(converted)
    a=np.array(data);del data
    n,p=a.shape;heat=names[0];seq=a[:,0];wave=np.array(headers[1:-3],float);s=a[:,1:-3];g=a[:,-3:];t=(seq-seq[0])*.5
    assert np.isfinite(a).all(),'Unexpected nonfinite observations; manual review needed'
    assert np.all(np.diff(seq)==1),'Time convention requires review'
    old=previous[heat];assert int(old['samples'])==n and int(old['co2_zero_samples'])==int(np.sum(g[:,1]==0)) and int(old['co_zero_samples'])==int(np.sum(g[:,2]==0))
    grids.append(wave)
    spectral=np.median(s,axis=1);sat=s==65535
    r=dict(Attachment=num,Heat_ID=heat,Source_File=str(path),Source_SHA256=sha,Sheet=heat,Data_Range=f'A2:column{p}_row{n+1}',Samples=n,Variables=p,Spectral_Rows=n,Spectral_Columns=s.shape[1],Sequence_First=seq[0],Sequence_Last=seq[-1],Sequence_Bad_Steps=int(np.sum(np.diff(seq)!=1)),Duration_s=t[-1],Wavelength_Group='A' if np.array_equal(wave,grids[0]) else 'B',Wavelength_Min_nm=wave.min(),Wavelength_Max_nm=wave.max(),Wavelength_Step_Min_nm=np.diff(wave).min(),Wavelength_Step_Max_nm=np.diff(wave).max(),Missing_Observations=missing,Nonnumeric_Observations=nonnum,Duplicate_Full_Rows=n-len(np.unique(a,axis=0)),Duplicate_Payload_Rows=n-len(np.unique(a[:,1:],axis=0)),Spectrum_Min=s.min(),Spectrum_Q01=np.quantile(s,.01),Spectrum_Q25=np.quantile(s,.25),Spectrum_Median=np.median(s),Spectrum_Q75=np.quantile(s,.75),Spectrum_Q99=np.quantile(s,.99),Spectrum_Max=s.max(),Spectrum_Zero_Count=int(np.sum(s==0)),Spectrum_Negative_Count=int(np.sum(s<0)),Value_65535_Count=int(sat.sum()),Value_65535_Fraction=float(sat.mean()),Value_65535_Affected_Rows=int(sat.any(axis=1).sum()),Value_65535_Affected_Wavelengths=int(sat.any(axis=0).sum()),Oxygen_First=g[0,0],Oxygen_Last=g[-1,0],Oxygen_Increase=g[-1,0]-g[0,0],Oxygen_Average_Increment_m3_per_s=(g[-1,0]-g[0,0])/t[-1],Oxygen_Decreases=int(np.sum(np.diff(g[:,0])<0)))
    if num>1:
        for j in range(len(wave)):checks.append(dict(Check='wavelength_grid_vs_first',Heat_ID=heat,Index=j,Value=wave[j],Difference_nm=wave[j]-grids[0][j]))
    for k,label in enumerate(['Oxygen','CO2','CO']):
        v=g[:,k];dv=np.diff(v);repeat=ranges(dv==0);zero=ranges(v==0)
        for name,val in [('Min',v.min()),('Q25',np.quantile(v,.25)),('Median',np.median(v)),('Q75',np.quantile(v,.75)),('Max',v.max()),('Mean',v.mean()),('Std',v.std()),('Zero_Count',int(np.sum(v==0))),('Negative_Count',int(np.sum(v<0))),('Repeated_Transitions',int(np.sum(dv==0))),('Longest_Constant_Run_Samples',max([b-a+2 for a,b in repeat],default=1)),('Max_Abs_Adjacent_Change',np.max(abs(dv)))]:r[label+'_'+name]=val
        for kind,rr in [('zero',zero),('constant_transition',repeat)]:
            for start,end in rr:
                end=end+1 if kind=='constant_transition' else end
                events.append(dict(Heat_ID=heat,Variable=label,Kind=kind,Start_Excel_Row=int(start+2),End_Excel_Row=int(end+2),Start_s=t[start],End_s=t[end],Samples=int(end-start+1),Value=v[start]))
        if zero:issue('Zero Values',heat,label,f'{int(np.sum(v==0))}个零值，{len(zero)}个连续零段',f'Ten_Heat_Comparison.csv:{label}_Zero_Count; Joint_Interval_Evidence.csv','将零值误作缺失会改变起始及结束响应','检查零段时序位置和另外两类信号；核实缺测编码')
        if repeat:issue('Cross-Heat Inconsistencies',heat,label,f'{int(np.sum(dv==0))}个相邻重复转移，最长常量段{r[label+"_Longest_Constant_Run_Samples"]}点','Joint_Interval_Evidence.csv','0.5秒采样不等于0.5秒有效仪器更新率','比较气体联合保持与累计氧保持；核实量化精度及设备更新率')
        for idx in np.argsort(abs(dv))[-3:][::-1]:topjumps.append(dict(Heat_ID=heat,Variable=label,Excel_Row_Before=int(idx+2),Excel_Row_After=int(idx+3),Time_Before_s=t[idx],Time_After_s=t[idx+1],Value_Before=v[idx],Value_After=v[idx+1],Signed_Change=dv[idx],Judgment='变化幅度排名；不代表异常标签'))
    # No threshold: list only largest raw adjacent spectral change per direction.
    for direction,ds in [('time',np.diff(s,axis=0)),('wavelength',np.diff(s,axis=1))]:
        i,j=np.unravel_index(np.argmax(abs(ds)),ds.shape)
        topjumps.append(dict(Heat_ID=heat,Variable='Spectrum_'+direction,Excel_Row_Before=int(i+2),Excel_Row_After=int(i+3 if direction=='time' else i+2),Time_Before_s=t[i],Time_After_s=t[i+1] if direction=='time' else t[i],Value_Before=s[i,j],Value_After=s[i+1,j] if direction=='time' else s[i,j+1],Signed_Change=ds[i,j],Judgment=f'原始最大相邻差；列{j+2}，波长{wave[j]}nm；非异常判定'))
    issue('Local Discontinuities',heat,'all','已定位原始相邻差最大的候选点','Joint_Largest_Adjacent_Changes.csv','真实工艺变化、谱峰及记录错误可能混淆','联合检查前后时点和相邻波长，不按排名删除',status='候选审查位置；尚未确认为异常')
    if sat.any():
        legacy=';'.join(x['Issue_ID'] for x in oldissues if x['Heat_ID']==heat and x['Variable']=='spectrum')
        issue('Potential Instrument Saturation',heat,'Spectrum',f'{int(sat.sum())}个65535；影响{int(sat.any(axis=1).sum())}个时点和{int(sat.any(axis=0).sum())}个波长',f'02_Data_Exploration/Spectrum/{heat}_quality_locations.csv','峰高可能受上限截断；不能假称可恢复真实峰高','检查二维连片、削顶和邻域；核查量程及标定',legacy=legacy)
    signals={'Spectral_Median':spectral,'Oxygen':g[:,0],'CO2':g[:,1],'CO':g[:,2]}
    for xname,x in signals.items():
        for yname,y in signals.items():
            if list(signals).index(xname)>=list(signals).index(yname):continue
            for kind,xx,yy in [('levels',x,y),('adjacent_changes',np.diff(x),np.diff(y))]:
                pearson=float(np.corrcoef(xx,yy)[0,1]) if xx.std()>0 and yy.std()>0 else None
                relationships.append(dict(Heat_ID=heat,X=xname,Y=yname,Representation=kind,N=len(xx),Pearson_r=pearson,Meaning='原始水平/相邻变化的零移位描述；非因果，非延迟估计'))
    joint=np.all(np.diff(g[:,1:],axis=0)==0,axis=1)
    r['Gas_Joint_Held_Transitions']=int(joint.sum());r['Spectral_Median_Max_Time_s']=t[np.argmax(spectral)];r['CO2_Max_First_Time_s']=t[np.argmax(g[:,1])];r['CO_Max_First_Time_s']=t[np.argmax(g[:,2])]
    rows.append(r);print(f'Reviewed {num}: {heat}, {n} samples; source hash verified',flush=True)

assert all(np.array_equal(g,grids[0]) for g in grids[:4])
assert all(np.array_equal(g,grids[4]) for g in grids[4:])
issue('Structural Issues','ALL','headers','列数相同，Sequence及累计氧列名存在语言/别名差异，包括YQXH','source_manifest.json; variable_statistics.csv','按固定英文列名读取可能漏列','明确列位置+波长类型+语义映射并验证，保留原表头',status='已确认结构差异；不是无效观测')
issue('Time Coordinate Issues','ALL','time','Sequence均从1开始且步长1；时间窗387–777秒，非共同物理起点证明','Ten_Heat_Comparison.csv','采样索引一致不保证工艺阶段一致或烟气物理同步','核实开采时刻、吹炼起止和设备时钟；Q2评估延迟',status='采样结构已确认；物理对齐未确认')
issue('Wavelength Coordinate Issues','ALL','wavelength','附件1–4与5–10各自网格逐点完全一致，两组之间不同','Joint_Wavelength_Evidence.csv','同一列号对应不同物理波长；直接跨炉融合可能失真','保留坐标，Q1研究共同波段与标定差异，不在本阶段重采样',legacy=';'.join(x['Issue_ID'] for x in oldissues if x['Variable']=='wavelength'))
issue('Missing Values','ALL','all','本次原始读取空白/非数值/非有限值为0','Ten_Heat_Comparison.csv; source_manifest.json','无显式缺失不代表没有停更或编码缺失','调查零段和重复段机制',status='已确认本次读取无显式缺失；非异常清零')
issue('Extreme Values','ALL','Spectrum','各炉强度分布及最大值不同；65535不等同于所有异常点','Ten_Heat_Comparison.csv:Spectrum_*','全局强度阈值可能误删真实谱峰或不同工况','Q1结合波长/时间邻域和工艺阶段审查，不先选阈值')
issue('Cross-Heat Inconsistencies','ALL','all','炉时、光谱尺度、累计氧增量及气体范围不一致','Ten_Heat_Comparison.csv','样本多的炉权重更大，短炉可能覆盖不同阶段；范围偏移影响泛化','核实工艺完整性；后续按炉汇总指标并跨炉留出')
issue('Cross-Variable Relationships','ALL','Spectrum/Oxygen/CO2/CO','零移位原始水平与相邻变化的相关已分别计算','Joint_Variable_Relationships.csv','累计量趋势、自相关及延迟会混淆相关，无法据此推断因果','Q2分工况延迟诊断；Q1解释光谱摘要；共同明确Q3实时可用信息')
issue('Structural Issues','6B03205','version','清单使用修正版；本轮10份哈希均与首轮一致，附件1零值计数吻合首轮修正版统计','source_manifest.json; attachment1_version_diff.json; Joint_Source_Verification.json','旧版全零气体若混入会污染结论','旧版仅作明确标注的历史比较；所有入口缺少修正版应报错',status='已核验当前计算来源；旧版仍保留')
csvout(P/'Ten_Heat_Comparison.csv',rows);csvout(P/'Unified_Data_Quality_Issue_Summary.csv',issues);csvout(P/'Updated_Data_Issue_Register.csv',issues)
csvout(E/'Joint_Variable_Relationships.csv',relationships);csvout(E/'Joint_Interval_Evidence.csv',events);csvout(E/'Joint_Largest_Adjacent_Changes.csv',topjumps);csvout(E/'Joint_Wavelength_Evidence.csv',checks)
(E/'Joint_Source_Verification.json').write_text(json.dumps(dict(sources=[dict(path=m['path'],sha256=m['sha256'],verified=True) for m in manifest],attachment1='corrected only',baseline_sample_and_gas_zero_counts_match=True,transformations='none; descriptive reductions and adjacent differences only'),ensure_ascii=False,indent=2),encoding='utf-8')
def table(cols):
    return '|'+ '|'.join(cols)+'|\n|'+'|'.join(['---']*len(cols))+'|\n'+'\n'.join('|'+ '|'.join(f'{r[c]:.5g}' if isinstance(r[c],float) else str(r[c]) for c in cols)+'|' for r in rows)
standards='''# 统一数据质量判断标准 v1（J05）

这些原则是供两名队员共同使用的研究基准；文档已建立不等于队员已经共同审阅。具体异常数值阈值和最终检测算法均未确定。

1. 原始数据只读。统计、候选问题、确认标签、清洗与重建分别保存。每次运行记录来源文件、SHA256、sheet、Excel行列、Sequence、时间、波长和程序版本。
2. 附件1必须使用根目录中文文件名修正版。旧版只允许在显式版本比较中出现；缺少修正版必须报错，禁止静默回退。原始表头保留，读取映射需验证2051列和2047数值波长列，不只依赖英文名称。
3. 时间使用t=(Sequence-Sequence首值)*0.5秒，先核验有限、唯一、严格递增且差1。保留Sequence，不排序、不删点。起始时刻只是记录坐标，不保证炉次工艺起点一致或两设备物理同步。
4. 保留每炉全部原始波长。按列索引比较只能在实际波长网格一致时解释；网格不同不得直接做逐点跨炉比较。本阶段不统一网格。
5. 空白、非数值、非有限值分别计数。零值按原值保留，需明确仪器缺测编码才能确认为缺失。连续常量不自动认定停更或错误。
6. 极端值、大相邻差和跨炉尺度差异都是证据线索，不直接成为无效标签。需在原值上下文、二维邻域、跨变量以及工艺阶段中审核。
7. 65535仅产生疑似饱和标签。削顶、连片和持续性可增强证据，但确认饱和还应取得设备量程/记录机制或可靠独立证据。饱和点若属截断观测，应记录为受限信息，不当成普通随机缺失。
8. 连续性不等于平滑性。保留真实谱线、工艺突变与启停响应；不得以图形不平滑判错。当前最大相邻差仅用于挑选审阅位置，无阈值含义。
9. 质量状态至少区分：观察事实、疑似解释、确认问题、处理提案。既有mask码0未识别问题、1疑似异常、2缺失、3疑似饱和、4疑似无效、5确认无效继续沿用；另保留独立布尔标记及证据字段以支持多问题共存。0不代表已证明有效。当前未生成最终逐点mask。
10. CO2/CO按题目明确的瞬时体积流率m³/s解释，累计氧为m³，强度按题目W/cm²记录但绝对标定待核。累计氧分布受采样窗影响，均值不是平均供氧流率。端点氧增量/时长仅是观察窗口平均速率，不是拟合瞬时氧枪流率。
11. 同行不等于相同炉内反应时刻。原始相关、峰值时刻差或最大相关移位都不能单独确认为运输延迟；不可由相关宣称因果。后续延迟分析应说明符号、变化工况、稳定性与不确定性。
12. 当前允许计数、分位数、原始相邻差、描述性相关和坐标比较；禁止删除、插值、平滑、归一化、重采样、拟合或模型训练。Pearson公式中的中心化/标准差仅用于统计定义，没有生成归一化数据集。
13. 审核顺序：整体共同审查→共同统一标准→Q1/Q2专项分析→交换交叉审核→共同预处理设计→人工遮蔽验证→正式预处理。当前不执行遮蔽实验。
14. 专项任务完成后每项提案给出事实、假设、反例、影响和验证办法。跨炉验证不随机拆相邻时点；实时模型的特征、对齐与处理必须防止未来信息泄漏。
'''
save('Unified_Data_Quality_Standards.md',standards)
report='''# 整体数据审查报告（J01–J05，2026-11-27）

本轮建立两人共同审阅的完整基准，未宣称两名队员已经完成阅读或达成口头共识。已重新读取全部项目文档、十份当前原始XLSB并逐份校验SHA256，复核第一轮统计。没有修改原始观测或执行预处理。

## 概念与研究目标

共同掌握四个概念：测量坐标（measurement coordinates）、观测与质量判断的区分、跨炉可比性（comparability）、相关与延迟的区别。建议两人共同阅读与讨论45–60分钟，再开展专项调查。输出为七份主交付及四份证据CSV和来源核验JSON。

## J01 数据结构与完整性

十炉均为2051变量：Sequence、2047波长强度、累计供氧、CO2、CO。光谱矩阵为n×2047；Sequence均为1到n，步长1，采样间隔0.5秒。时长采用首末时刻差(n-1)×0.5。没有空白、非数值、非有限值和完整重复行。由于Sequence唯一，完整行不重复不能证明其他变量没有停更，因此另外计算不含Sequence的payload重复行与各变量连续常量段。

'''+table(['Attachment','Heat_ID','Samples','Duration_s','Wavelength_Group','Spectrum_Median','Value_65535_Count'])+'''

附件1：清单、代码路径、首轮附件1样本数及气体零值数、本轮重读均指向修正版。旧版只用于历史版本差异文件，未混入本轮十炉统计。原审计入口曾允许修正版不存在时回退旧版，本轮将其改为明确报错。原文档包含旧版全零的历史描述且明确标注，不能当作当前气体事实。官方身份依据仍为用户补充说明。

## J02 总体统计与问题登记

'''+table(['Heat_ID','Spectrum_Q01','Spectrum_Median','Spectrum_Q99','Spectrum_Max','Spectrum_Zero_Count','CO2_Zero_Count','CO_Zero_Count'])+'''

显式缺失和负值计数见Ten_Heat_Comparison.csv。零值、重复转移、极端值都保留。八炉出现65535，尚未确认仪器饱和。缺失类和时间类中正常检查结果也已登记，避免“没有问题记录”等于“未检查”的歧义。每项含事实、证据位置、影响、状态、后续调查及旧问题编号映射。

原Issue Register仅记录饱和值和波长差异，不足以覆盖全部质量类别；本轮补齐十类观察。Updated_Data_Issue_Register为当前扩展登记表，旧表保留历史。

## J03 跨炉比较及可比性

波长A组附件1–4：340.535–1027.963 nm；B组附件5–10：339.390–1023.303 nm。已对2047个坐标逐点检验：各组内部一致，组间不同。两组步长均非严格常数，完整差值见Joint_Wavelength_Evidence.csv。不能因为列数相同就将列当作相同物理特征；也不能只通过加一个常数假设完全校准。波段交集339.390与340.535的较大者到两个上限的较小者，即340.535–1023.303 nm；本轮没有截取或重采样。

炉时最短387秒，最长777秒，相差约两倍。短炉覆盖的工艺阶段是否完整仍不确定；累计氧端点和单位时间增量只能描述采样窗口，不能直接推断设备效率或炉容。同一秒时刻或同一行号也不保证同一工艺阶段。

'''+table(['Heat_ID','Oxygen_First','Oxygen_Last','Oxygen_Average_Increment_m3_per_s','Oxygen_Repeated_Transitions','CO2_Min','CO2_Max','CO_Max','Gas_Joint_Held_Transitions'])+'''

光谱尺度、气体峰值、零段和保持特征均有炉间差异；强度的全局分位数跨坐标比较只描述分布，不能证明某个谱峰更强。累计氧均单调非减，但相邻重复普遍存在。气体联合保持次数提示要调查有效更新率，不能直接断言数据采集出错。训练时长炉可能主导样本损失，波长与工况差异会影响泛化；后续应同时报告逐炉和汇总性能，目前不训练。

## J04 整体变量关联

本轮对每炉四个描述量（每时刻全谱中位数、累计氧、CO2、CO）两两计算零移位Pearson相关，并对原始相邻变化重复计算。谱中位数是探索摘要，可能掩盖窄谱线和局部饱和，不能代表Q3最终特征。

数学定义r=Σ(x-x̄)(y-ȳ)/sqrt[Σ(x-x̄)²Σ(y-ȳ)²]；相邻变化Δx_i=x_(i+1)-x_i仅描述两次原值差，没有平滑或重建。例：x=(1,2,3)、y=(2,4,6)相关为1，即便两者只是同时随时间上升；不能据此证明x导致y。原始水平与变化相关若不同，说明共同趋势可能影响观察，但差分自身也会放大噪声。

所有真实数据相关结果见Joint_Variable_Relationships.csv。没有计算显著性p值或假定相邻样本独立，没有对信号移位，没有把最大峰时差解释为运输延迟。共同时间网格支持同行记录比较，却不消除烟气运输延迟。官方描述已给出延迟方向及流率依赖，本轮数据只作描述，未量化tau。

Q3意义：后续必须明确“预测炉内当前对应烟气”还是“预测探头当前读数”。当tau>0时，炉内t对应探头t+tau标签是延迟观测，不能把t+tau的信息当实时输入。先由Q1解释谱特征、Q2验证工况延迟，再共同确认目标与无泄漏的按炉验证。

## J05 统一原则与后续顺序

完整执行规则见Unified_Data_Quality_Standards.md。原则不是异常数值阈值；当前没有最终异常检测器和逐点确认掩码。

Q1专项调查任务：保留两套网格并核验设备/标定解释；对各炉65535位置检查时间—波长连片、削顶和峰邻域；区分谱线、整段强度变化及孤立异常；为候选问题提交具体行列、波长、证据图和反例。暂不清洗、重采样或插值。

Q2专项调查任务：联合审查氧/气体零段和常量段；核实更新率、量化、吹炼起止与记录窗完整性；审查最大相邻差的局部上下文；为后续分流率延迟研究提出可辨识工况和验证方案。暂不拟合氧流率、积分模型或校正延迟。

两条工作线交换成果，逐项交叉审核；随后共同设计预处理，再开展遮蔽验证，最后正式预处理。不按成员姓名分配，因为尚未指定实际成员归属。

验证：10份源哈希与原清单一致，首轮样本与气体零计数一致；两组波长逐点一致性已检查。剩余限制：缺设备量程、标定、真实启停及运输参照证据；描述统计无法确认异常成因或证明因果。
'''
save('Joint_Overall_Data_Review.md',report)
master=(P/'Project_Master.md').read_text(encoding='utf-8')
update='''

## 2026-11-27共同审查阶段更新（优先于旧安排）

正确顺序：两人整体共同审查→共同统一标准→分别Q1/Q2专项分析→交换交叉审核→共同设计预处理→Masked Validation→正式预处理。
J01–J05证据分析与统一原则文件已完成，供两名队员共同审阅；不能宣称已代替队员达成共识。详细结论与任务见Joint_Overall_Data_Review.md，当前问题表为Updated_Data_Issue_Register.csv。
已确认两组波长坐标、不同炉时和尺度、零段及重复段；65535饱和解释、零值机制、工艺完整性和真实延迟仍待专项证据。附件1所有当前计算必须使用修正版并核验来源；禁止静默回退旧版。
'''
save('Updated_Project_Master.md',master+update);save('Project_Master.md',master+update)
status='''# 项目进度（2026-11-27，整体质量共同审查）

J01–J05分析与七份主交付已完成。阶段：Data Understanding & Data Quality Review；尚未开始预处理。
完成：读取既有文档；重读10份当前XLSB并核验哈希；独立复核样本和气体零值；十炉结构/分布/时间/波长/重复/极值比较；十类问题登记；水平与相邻变化相关调查；统一原则与专项任务清单。
人为协作状态：已建立供两名队员共同审阅的材料，尚无证据证明队员均已阅读或完成共同确认。
附件1：仅使用官方修正版作为当前分析源；旧版保留于历史比较。原始数据无改动，无删除、插值、平滑、归一化、重采样、连续拟合或模型训练。
不确定事项：65535是否饱和；零段/常量段机制；不同网格标定；起止工艺完整性；真实延迟及其供氧依赖。
下一步：共同阅读报告与统一标准→Q1/Q2各自调查报告中列明的任务→交换交叉复核→共同预处理设计→遮蔽验证→正式预处理。
交付入口：Joint_Overall_Data_Review.md、Ten_Heat_Comparison.csv、Unified_Data_Quality_Issue_Summary.csv、Unified_Data_Quality_Standards.md、Updated_Data_Issue_Register.csv、Updated_Project_Master.md、Updated_Project_Status.md。
证据位置：02_Data_Exploration/Common/Joint_*.csv及Joint_Source_Verification.json。既有Data_Issue_Register保留历史，当前使用Updated_Data_Issue_Register。
'''
save('Updated_Project_Status.md',status);save('Project_Status.md',status)
for name in ['Research_Decision_Log.md','Handover_Summary.md']:
    text=(P/name).read_text(encoding='utf-8');save(name,text+'\n\n2026-11-27更新：J01–J05完成；顺序以共同整体审查→统一标准→专项分析→交叉复核→共同预处理设计→遮蔽验证→正式预处理为准。当前交接见Joint_Overall_Data_Review.md和Updated_Project_Status.md。\n')
print(f'COMPLETE: {len(rows)} heats, {len(issues)} observations/issues, {len(relationships)} correlations.',flush=True)
