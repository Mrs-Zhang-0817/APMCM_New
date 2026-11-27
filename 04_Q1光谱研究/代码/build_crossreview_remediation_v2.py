"""Build versioned audit delivery from frozen evidence, never reads workbooks.
Run once per output directory. Existing outputs are refused (except test JSON).
"""
from pathlib import Path
import csv,json,hashlib,subprocess,io,sys,shutil,tempfile,os
from collections import Counter,defaultdict
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parent;O=P/'实验验证/交叉审核整改_v2'
BASE='3172d088feb9da0fed3a784e5071fcb9905b6a9e'
REVIEW='7652b32ac0e0f474610d7beb278b9eb2af240354'
PREFIX='05_Q2供氧与烟气研究/交叉审核/CR-A-Q1-3172d08-v01/'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return list(csv.DictReader(io.StringIO(p.read_text(encoding='utf-8-sig'))))
def write(name,text):
    p=O/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='') as f:f.write(text)
def dump(name,obj):write(name,json.dumps(obj,ensure_ascii=False,indent=2))
def csvout(name,rows):
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);write(name,'\ufeff'+s.getvalue())
assert subprocess.check_output(['git','branch','--show-current'],cwd=R).decode().strip()=='q1-spectral'
historical={p.relative_to(R).as_posix():sha(p.read_bytes()) for p in P.rglob('*') if p.is_file() and '__pycache__' not in str(p) and O not in p.parents and p.name not in ('validation_modules_v2.py','test_validation_v2.py','build_crossreview_remediation_v2.py')}
sources=[]
for name in ('审核报告.md','逐条问题清单.csv','70区独立意见.csv','关键复算记录.md','关键复算结果.json','复算.py'):
    b=subprocess.check_output(['git','show',REVIEW+':'+PREFIX+name],cwd=R)
    dest=O/'审核输入快照'/name;dest.parent.mkdir(exist_ok=True)
    with dest.open('xb') as f:f.write(b)
    sources.append(dict(Source_Commit=REVIEW,Source_Path=PREFIX+name,Snapshot_Path=dest.relative_to(R).as_posix(),Bytes=len(b),SHA256=sha(b)))
issues=read(O/'审核输入快照/逐条问题清单.csv');independent=read(O/'审核输入快照/70区独立意见.csv');key=json.loads((O/'审核输入快照/关键复算结果.json').read_text(encoding='utf-8-sig'))
assert len(issues)==13 and len(independent)==70
# Read every supplied record and preserve all fields, not filenames or summary.
assert all(r['Field_Comparison']=='全部核对一致' for r in independent)
assert key['Commit']==BASE and key['Hash_Manifest_Entries']==244
print('审核输入：',[(s['Source_Path'].split('/')[-1],s['Bytes']) for s in sources])
for r in issues:print(r['意见ID'],r['问题'])
old=read(P/'实验验证/正式清洗前置审核/Q1参考区域审核表.csv');byid={r['Reference_ID']:r for r in independent}
assert len(old)==70 and set(byid)=={r['Reference_ID'] for r in old}
sat=defaultdict(set)
for s in read(P/'专项分析/S04_65535候选饱和调查/S04_65535完整位置.csv'):sat[s['Heat_ID']].add((int(s['Excel_Row']),int(s['Excel_Column'])))
waves=defaultdict(dict)
for s in read(P/'专项分析/S03_光谱结构调查/S03_逐波长结构统计.csv'):waves[s['Heat_ID']][int(s['Excel_Column'])]=float(s['Wavelength_nm'])
durations=dict(zip(['6B03205','6B03206','6B03270','6B03271','6C02057','6C02058','6C02059','6C02060','6C02107','6C02108'],[1479,1311,1413,1420,775,1343,1555,1373,1459,1461]))
revised=[];pollution=[]
for a in old:
    b=byid[a['Reference_ID']];h=a['Heat_ID'];lo,hi,jl,jr=[int(a[k]) for k in ('Start_Excel_Row','End_Excel_Row','Start_Excel_Column','End_Excel_Column')]
    assert b['Q1_Recommendation']==a['Recommendation']
    contamination={};spans={};mincounts={};affected={}
    for radius in (1,2,4):
        cnt=0;axiscnt=[0,0];minaxis=[999,999];hits=[]
        for i in range(lo,hi+1):
            for j in range(jl,jr+1):
                tv=[(q,j) for q in range(max(2,i-radius),min(durations[h]+1,i+radius)+1) if q!=i]
                wv=[(i,q) for q in range(max(2,j-radius),min(2048,j+radius)+1) if q!=j]
                ht=[v for v in tv if v in sat[h]];hw=[v for v in wv if v in sat[h]]
                cnt+=bool(ht or hw);axiscnt[0]+=bool(ht);axiscnt[1]+=bool(hw)
                minaxis[0]=min(minaxis[0],len(tv)-len(ht));minaxis[1]=min(minaxis[1],len(wv)-len(hw))
                hits.extend(ht+hw)
        contamination[radius]=cnt;mincounts[radius]=minaxis
        if radius in (2,4):assert cnt==int(b[f'Radius{radius}_Upper_Neighbor_Centers'])
        spans[radius]=[waves[h][max(2,jl-radius)],waves[h][min(2048,jr+radius)]]
        affected[radius]=sorted(set(hits))
        pollution.append(dict(Reference_ID=a['Reference_ID'],Radius=radius,Centers_With_Upper_Neighbor=cnt,Denominator=int(a['Points']),Time_Direction_Centers=axiscnt[0],Wave_Direction_Centers=axiscnt[1],Minimum_Usable_Time_Neighbors=minaxis[0],Minimum_Usable_Wave_Neighbors=minaxis[1],Full_Nominal_Neighbors=2*radius,Time_Radius_s=.5*radius,Expanded_Min_nm=spans[radius][0],Expanded_Max_nm=spans[radius][1],Upper_Excel_Positions=json.dumps(affected[radius]),Basis='冻结S04完整上限位置+S03逐波长坐标；非真实检测性能'))
    letter=a['Class'][0];reject=a['Recommendation']=='Reject Candidate'
    use={'A':'Ordinary Reference','B':'Peak Preservation','C':'High Intensity','D':'Rapid Variation','E':'High Intensity','F':'Ordinary Reference','G':'Boundary Stress'}[letter]
    uses=[use]
    if contamination[4] or int(a['Within_65535']):uses.append('Saturation Stress')
    if use=='Ordinary Reference' and (reject or contamination[4]):uses[0]='Unresolved'
    missing=[b['Q2_Evidence_Request'],'逐帧独立峰窗/双肩与噪声解释；窗口用途需两人签署；真实正常性未认证']
    if contamination[4]:missing.append('冻结污染排除策略并确认方向支持，不能用被删失邻域作普通真值')
    if letter in 'AF':missing.append('框内稳定性与严格局部峰的成因；全谱选窗不等于局部平稳')
    if letter=='B':missing.append('逐帧峰位/峰宽/幅高稳定性和谱线来源证据')
    if letter=='D':missing.append('相邻全谱与Q2同期事件；区分真实工艺跃变和记录错误')
    if letter=='G':missing.append('边缘重复通道采集机制及双侧支撑')
    if letter in 'CE':missing.append('高背景与局部峰的分离、独立肩部窗及量程解释')
    row=dict(a);row.update(Original_Recommendation=a['Recommendation'],Q2_Opinion=b['Q2_Opinion'],Q2_Evidence_Request=b['Q2_Evidence_Request'],Source_SHA256=b['Source_SHA256'],Review_Status='Reject Candidate' if reject else 'Needs More Evidence',Proposed_Use='; '.join(dict.fromkeys(uses)),Ordinary_Truth_Allowed=False,Missing_Evidence='；'.join(missing),Radius1_Upper_Neighbor_Centers=contamination[1],Radius2_Upper_Neighbor_Centers=contamination[2],Radius4_Upper_Neighbor_Centers=contamination[4],Pollution_Range='各半径、轴、实际nm跨度及上限Excel坐标见70区_方向邻域复算.csv',Expanded_Radius4_nm=json.dumps(spans[4]),Revised_Support=a['Support']+'；Q2逐区可复算字段一致；半径2/4由冻结位置表再次核对',Revised_Opposition=a['Opposition']+'；'+b['Q2_Evidence_Request'],Joint_Approval='Pending',Normal_Truth_Certified=False)
    revised.append(row);print(a['Reference_ID'],row['Review_Status'],contamination[1],contamination[2],contamination[4],row['Proposed_Use'],b['Q2_Evidence_Request'])
csvout('Q1_70区修订审核表.csv',revised);csvout('70区_方向邻域复算.csv',pollution)
assert Counter(r['Review_Status'] for r in revised)=={'Reject Candidate':25,'Needs More Evidence':45}
csvout('审核输入来源清单.csv',sources)
# Historical tests run in isolated temp layout because their original writers target old paths.
legacy=[]
with tempfile.TemporaryDirectory(prefix='q1_synthetic_regression_') as tmp:
    root=Path(tmp);(root/'代码').mkdir();(root/'实验验证').mkdir()
    for name in ('validation_modules.py','test_validation_modules.py','preclean_risk_tests.py'):shutil.copy2(P/'代码'/name,root/'代码'/name)
    for script,relative in [('test_validation_modules.py','V04_实验程序准备/V04_模拟功能测试结果.json'),('preclean_risk_tests.py','正式清洗前置审核/独立模拟风险测试.json')]:
        proc=subprocess.run([sys.executable,str(root/'代码'/script)],capture_output=True,text=True,encoding='utf-8')
        if proc.returncode:raise RuntimeError(proc.stderr)
        result=json.loads((root/'实验验证'/relative).read_text(encoding='utf-8'))
        name='历史61项_隔离重跑.json' if script.startswith('test') else '历史12项_隔离重跑.json';dump(name,result)
        count=len(result['checks']);assert count==(61 if script.startswith('test') else 12)
        legacy.append(dict(script=script,checks=count,exit_code=proc.returncode,isolated=True))
testpath=O/'v2_模拟回归测试.json'
# Normalize the current, unpublished test capture before hashing; JSON values unchanged.
testbytes=testpath.read_bytes()
if b'\r\n' in testbytes:testpath.write_bytes(testbytes.replace(b'\r\n',b'\n'))
reg=json.loads(testpath.read_text(encoding='utf-8-sig'));assert reg['all_pass'];N=len(reg['checks'])
# S06 semantics supplement preserves all historical evidence.
s06=[]
for a in read(P/'专项分析/S06_谱峰与异常反例研究/S06_代表性案例登记表.csv'):
    row=dict(a);plateau=int(float(a['Plateau_Points']))
    row.update(Original_Evidence_Class=a['Evidence_Class'],Original_Decision_Status=a['Decision_Status'],Observed_Morphology=f"中心原值{a['Original_Value']}；上限平台节点{plateau}；左右首肩{a['Left_Shoulder']}/{a['Right_Shoulder']}；重复局部峰比例{a['Repeated_Local_Peak_Fraction']}",Physical_Hypothesis='平台形态可支持删失假设，不能确认设备机理' if plateau else '本案例无上限平台，仅作峰/变化对照；不能据此推断本点削顶',Instrument_Evidence='缺少量程、标定和记录机制独立证据',Morphology_Status='Observed Fact',Physical_Status='Hypothesis' if plateau else 'Not Claimed',Joint_Approval='Pending')
    s06.append(row)
csvout('S06_形态与解释分列补充表_v2.csv',s06)
plans=[
('Accepted','实际可用计数缺陷成立；修复资格与输出状态，不改变D1/D2候选性质。','逐轴至少2点且占名义2r不少于0.5；上限污染方向不可评估；双轴不足不返回False。','validation_modules_v2.py:detect_v2','十类构造、覆盖与误报/漏检风险均留存','代码及模拟完成，待Q2复核'),
('Accepted','同意禁用开关及单字段审批不足。结构校验不能替代真实签署。','新增显式开关、两人身份、批准号、配置及清单哈希绑定；不提供真实执行入口。','validation_modules_v2.py:authorize_real_v2','各必填字段缺失、开关False和篡改均拒绝','结构门控已修复，真实批准不存在'),
('Accepted','半径污染事实成立；一节点环不能担保半径4。','70区逐点复算半径1/2/4轴邻域，独立核对Q2半径2/4计数。','Q1_70区修订审核表.csv;70区_方向邻域复算.csv','70区唯一且140个半径2/4计数匹配；新增两区保留证据','证据补充完成，实际物理窗待共同冻结'),
('Accepted','候选用途不能认证真实正常。','25区困难层、45区逐区补证；不批准任何真值。','Q1_70区修订审核表.csv','70个Missing_Evidence非空且批准全Pending','用途草案完成，真实证据待补'),
('Accepted','窄峰误报、块漏检和尺度依赖是方法局限，邻居修复无法消除。','保留正负扰动、持续/瞬变峰及块内失败；阈值/尺度底扫描写入基准。','test_validation_v2.py;Q1_验证基准v2草案.md','困难场景须可评估并如实保留风险','回归完成，最终检测器未选'),
('Partially Accepted','接受不可辨识与收敛风险；本轮不把C2扩展成可用真实峰顶估计器。','增加输入检查、显式convergence_certified=False；C2真实使用继续禁用，完整收敛/先验扫描列Pending。','validation_modules_v2.py:c2_checked_v2;Q1_待共同决策事项.md','下界满足与非辨识分开；不得报告峰高准确或已收敛','部分代码保护完成；优化验收仍未完成'),
('Accepted','reference>C与observed>=C对象不同，不能合并真值标签。','clip_v2独立输出严格截断、恰等和观测达帽；C2仍以达帽为约束，恰等单列评价。','validation_modules_v2.py:clip_v2,c2_checked_v2','相等标签分离；非法输入/坐标/负参数拒绝','模拟完成，设备阈值解释Pending'),
('Accepted','全域最大值会遮蔽目标峰损失；原Shoulder_MAE不是局部肩部指标。','显式峰窗、肩窗、背景；实现nm FWHM和分项覆盖/分布/逐行失败。','validation_modules_v2.py:reconstruction_metrics_v2','无关更高峰不能掩盖目标高度误差；缺肩/缺值不报0误差','代码与模拟完成，真实峰窗未批准'),
('Accepted','同意轴顺序依赖，二次估计支撑必须可追溯。','R0双顺序与provenance/estimated_support输出；边界不外推，R1保留未实现。','validation_modules_v2.py:r0_with_support_v2;Q1_R1实现与验收报告.md','6与5反例保留；二次源标记和边界缺口通过','R0追踪完成，R1未实现'),
('Accepted','0比例和未知kind静默改变场景确为漏洞。','select_mask_v2校验枚举/尺寸/比例，0请求为0，返回请求量与实际量。','validation_modules_v2.py:select_mask_v2','0/1、未知类型、越界、尺寸和种子测试','代码与模拟完成'),
('Partially Accepted','接受LOHO与available_time不足；本轮无真实到达时钟证据，不能声明已解决。','给出按炉内外层设计与网格覆盖、Q3可用时间强制字段；不伪造工况或部署时延。','Q1_正式验证配置v2草案.json;Q1_验证基准v2草案.md','按炉集合及网格覆盖可复算；工况/可用时间缺失时阻断实时结论','设计补充完成；工况与时钟证据Pending'),
('Partially Accepted','同意形态/物理分列；原6B03205_A的Decision_Status实际为Hypothesis，不应把所有历史行概括为Observed Fact。','新增68行语义补充，保留原状态；无平台对照不作本点削顶主张。','S06_形态与解释分列补充表_v2.csv','68行ID不变，原解释保留，观测与假设分别列出','补充完成，物理解释未确证'),
('Accepted','计数时间点不一致且旧进度未标上传，接受改进导航。','本目录导航注明243/244/245口径和冻结Git基线；新清单明确排除自身。','Q1_整改总报告.md;版本变更与SHA256清单.csv','历史文件SHA不变；本次清单逐字节核验','本线说明完成，共同进度不改')]
matrix=[]
for a,p in zip(issues,plans):
    state,response,plan,files,criteria,progress=p
    matrix.append(dict(Issue_ID=a['意见ID'],原始审核意见=a['问题'],对应文件和代码=a['证据位置'],原始证据=a['独立证据与影响'],原始验收建议=a['修改或验收建议'],Q1负责人回应=response,是否接受审核意见=state,修改方案=plan,修改文件=files,验收标准=criteria,当前状态=state,实施进度=progress,Q2复审='Pending',共同批准='Pending'))
csvout('Q1_13项交叉审核整改矩阵.csv',matrix)
heats=list(durations);grids={h:('A' if i<4 else 'B') for i,h in enumerate(heats)};folds=[]
for test in heats:
    remaining=[h for h in heats if h!=test]
    inner=[dict(fit=[h for h in remaining if h!=val],validation=[val]) for val in remaining]
    assert all(set(grids[h] for h in f['fit'])=={'A','B'} for f in inner)
    folds.append(dict(test=[test],outer_train=remaining,inner=inner,fit_grid_groups=['A','B'],physical_condition_coverage='Unknown / Pending'))
config=dict(task='A-Q1-CR-002',version='v2-draft',status='Pending',frozen=False,real_data_execution_allowed=False,real_validation_executed=False,reference_manifest='Q1_70区修订审核表.csv',reference_manifest_sha256=sha((O/'Q1_70区修订审核表.csv').read_bytes()),ordinary_truth_approved_count=0,R1_implemented=False,C2_real_ready=False,seed=20261127,detectors=dict(kinds=['D0 weak baseline','D1','D2'],threshold_candidates=[4,6,8,12],floor_candidates=[.5,1,2],radius_candidates=[1,2,4],min_neighbors=2,min_fraction=.5,min_fraction_sensitivity=[.5,.75,1],denominator='nominal 2r per axis',contamination='exclude cap and invalidate affected axis',partial_axis='Fallback Required, prediction NaN',units='floor scales with intensity units; node radii physical windows not frozen'),masking=dict(kinds=['points','time','wavelength','block','peak'],point_fractions=[0,.001,.01,.05],structured_sizes=[[1,1],[1,3],[3,1],[3,5],[7,17]],clipping_target_width_nodes=[1,2,4,8,16],upper_policy='choose C on training/approved untruncated profile to obtain width; record actual width and equality separately',positive_negative_injection_multipliers=[2,5,10],amplitude_basis='training-only robust/local-noise scale; not test labels'),metrics=dict(detection=['TP','FP','FN','TN','Precision','Recall','F1','FPR','coverage','unknown_positive_count','protected_peak_flag_rate','block_interior_recall','block_boundary_recall'],reconstruction=['MAE','RMSE','median','p95','max','peak_position_nm','peak_height','FWHM_nm','area','gradient_RMSE','point/peak/shoulder/edge_coverage'],peak_window=None,shoulder_windows=None,background=None,failure_thresholds='Pending: training calibration plus human approval, never tune to held-out errors'),folds=folds,approval=dict(approval_id=None,approvers=[],config_sha256=None,reference_approval_manifest=None),Q3=dict(allowed=False,reason='available_time and physical delays unknown'),scope='本轮仅配置设计与独立合成回归；不代表已执行该参数扫描')
dump('Q1_正式验证配置v2草案.json',config)
write('Q1_D1_D2邻居不足修复报告.md',f'''# D1/D2邻居支持修复 v2

Task A-Q1-CR-002；来源 CR-A-Q1-3172d08-v01；标准v2。结论：代码修复为 Candidate Method，{N}项独立模拟检查为 Experimentally Supported；共同批准 Pending。

原版检查几何索引长度而非每个中心实际有限邻居，NaN中位数仍可能凭1点给分。原版不变，新文件 `../../代码/validation_modules_v2.py`。

对轴d、节点半径r，去除中心，令 G_d 为域内槽位，V_d 为有限且小于上限的节点。输出几何槽位数、|V_d|、|V_d|/(2r)、污染标记与MAD0。可评分条件：中心有限且低于上限，|V_d|≥2，|V_d|/(2r)≥0.5，方向邻域无任何达上限观测。阈值0.5与2点是本轮模拟提案，不能解释为真实最优阈值。边界分母仍为名义2r，同时输出域内槽位数，防止缩小分母隐藏缺支持。

z_d=(I-med(V_d))/(1.4826 MAD(V_d)+floor)。floor>0且有限；MAD0可计算但另标记，不能把有限评分解释为统计可信。floor必须随强度单位同比缩放。阈值6、floor1仅模拟默认；量化尺度尚未校准。

两轴均满足才进入D1 OR或D2 AND同号的完整评价。输出四状态：Evaluable Triggered、Evaluable Not Triggered、Unassessable、Fallback Required。仅一轴可用时保留partial_direction_trigger，但完整预测为NaN；两轴均不足或中心受限也为NaN。备用算法未选，不能自动调用D0后把未触发记正常。该保守D1语义比原OR更严格，需共同选择是否接受；覆盖下降必须连同原始分母报告。

65535在本实现仅作为保守受限观测排除规则，不确认仪器机理。不仅剔除污染邻居，也使受污染轴不可评估，避免伪装为干净参考。测试包含仍有3个干净邻居但1个65535的方向。未来可比较排除后评分策略，须另版本，不能混合分母。

十类规定情形均构造：每轴1/2点、单轴不足、双不足、65535、持续/瞬变真峰、块内部、边界、MAD0。每轴2点、满支持尖点和角点可触发；并未屏蔽全部困难点。持续窄峰D1误报、瞬变峰D2误报、块内D1/D2漏检继续在结果中显式保留；这些检查“通过”表示风险被重现。

运行 `python ../../代码/test_validation_v2.py` 输出JSON到新run目录。v2_模拟回归测试.json记录逐构造状态、计数、可评估点/全点与标记数。未对真实70区运行此检测器或评价Precision/Recall。
''')
write('Q1_R1实现与验收报告.md','''# R1二维PCHIP决策与R0支撑审计

Task A-Q1-CR-002。R1仍未实现、无验收性能；保持禁用，Candidate Method / Pending。未创建假R1函数，也未以R0或一维PCHIP冒充R1。

原数学定义已审阅：先在各实际波长λ_j上，以实际时间节点构造f_j(t)=PCHIP_t；查询任意t后，在原非均匀λ_j上对f_j(t)构造PCHIP_λ，得到F(t,λ)。相反次序需单列，非线性斜率计算通常不交换。不能按列号作等距λ，也不能将缺失节点当0；需要有限节点、两侧支撑、最大支撑跨度和禁止外推规则。整行/整列缺失时对应方向可能完全无函数；第二轴不得隐瞒第一轴估计源。

一维PCHIP在其支撑段内为分段三次、节点函数值和一阶导连续，轴上形状保持不能推出整个组合曲面全局C1：斜率分支可随另一坐标改变；二维偏导、混合导和峰形物理真实性需要另验。边界只有域内支撑，不可声称外域可靠。

本轮选择暂缓：尚无获批普通参考真值，峰窗和缺口支撑策略尚未冻结；目前关键缺陷在检测资格与评价指标。即使现在能实现PCHIP，也无法凭此证明对未采样峰顶有收益。延后理由为收益证据和支撑协议不足，非声称技术无法实现，也不将缺少SciPy视为数学障碍。保持可解释R0作为模拟基准，避免在未经验证时增加轴顺序和光滑性假设。

R0新增r0_with_support_v2，可选择time-wave与wave-time，记录0原始、1第一步、2第二步、-1未解决，并逐点标记是否依赖估计支撑。3×3原反例两序分别6与5；边界整行缺口保留NaN；二步估计源案例通过。它是节点补点审计；完整网格的原GridSurface才提供双线性任意坐标求值，未把节点补点包装为光滑二维曲面。

R1重启门槛：共同批准缺口/最大跨度规则，冻结方向次序，准备独立合成测试：二维解析平面及曲面、非均匀λ、窄峰/未采样峰、随机及块遮蔽、边界、缺轴、域外拒绝、非采样点求值。与相同输入R0比较误差分布、峰宽、覆盖、耗时和两序差异；无实证收益则继续保留候选。上述R1测试本轮未执行，不计入通过数。
''')
write('Q1_回归测试报告.md',f'''# 回归测试记录 v2

Task A-Q1-CR-002。只用独立合成数组，无真实工作簿读取、真实遮蔽或真实性能验证。

原功能测试61/61、风险测试12/12在临时隔离布局重跑成功；原程序会写结果，因此复制三个历史代码文件到临时目录运行，结果另存本目录，未运行原路径覆盖历史。新回归{N}/{N}通过，完整断言、案例、覆盖和状态在v2_模拟回归测试.json。环境Python {sys.version.split()[0]} / NumPy {np.__version__}。

新增覆盖：单/双有效邻居、缺轴、污染、边界可评分及严格比例下拒绝评分、MAD0、正负尖点、单位同比变换、持续/瞬变峰和块内漏检；遮蔽0与1比例、非法枚举/尺寸、种子；配置每项缺失与篡改；R0两序及估计源；截断相等点、C2输入域与参数；固定峰窗/FWHM、无关高峰和峰窗缺值。

功能通过不能理解为所有方法有效。持续真实窄峰D1仍可误标；瞬变真峰D2仍可误标；连续块内部仍漏检。C2下界可满足但convergence_certified=False、real_data_ready=False。R1无实现和验收测试。13条审核的代码修复、补证和共同决策分别记录，不把全部标为已关闭。

v2回归运行入口：`python ../../代码/test_validation_v2.py > 新run结果.json`。完整交付构建入口为`build_crossreview_remediation_v2.py`，已有输出时拒绝覆盖，应复制到新版本目录并修改O；不可直接重复运行覆盖本次证据。原测试独立复现记录：{json.dumps(legacy,ensure_ascii=False)}。

局限：本轮未执行配置中全部参数笛卡尔积、真实工况覆盖、C2收敛/先验敏感性或R1比较；其余报告不能将这些计划当已完成实验。
''')
write('Q1_验证基准v2草案.md','''# 统一验证基准 v2 草案

Task A-Q1-CR-002；Candidate Method / Pending。实际参数、真值资格、峰窗及失败阈值未冻结；配置real_data_execution_allowed=False。本轮只做独立模拟回归，没有正式真实验证。

|类别|遮蔽真值资格|异常注入资格|重点指标|失败条件|不可评估条件|
|---|---|---|---|---|---|
|Ordinary Reference|当前0区批准；仅补证后逐用途签署的未削顶、无污染、支撑充分观测代理|同样先补证，正负点/段/块|MAE、RMSE、分布、覆盖；检测混淆矩阵|越过冻结误差容限或覆盖底线；擅用未签署区域直接判协议失败|缺真值/输入支撑或分母0|
|Peak Preservation|已审核未截断且完整峰窗/双肩才可；不将局部峰判异常|扰动与未扰动保护峰分开，禁止将未注入真峰标阳性|峰位nm、高度、FWHM nm、面积、峰误标率|峰形误差超冻结容限、明显峰消失或新伪峰|峰窗不足、半高双侧不闭合、缺节点、多峰归属不明|
|Rapid Variation|需证实真实工艺变化并冻结窗|可作压力测试，标签仅注入位置|分时误差、跃变前后及边界召回、覆盖|抹平已确认变化或误检超限|变化成因不明时不能宣称正常真值|
|High Intensity|未达帽、无污染、噪声及峰背景解释充分后|正负及强度尺度扫描|绝对/有定义的相对误差、MAD0层、饱和邻域覆盖|尺度变换无解释地改判或误差超限|近帽/不明删失与支持不足|
|Boundary Stress|仅既有可靠观测可遮；不为无支撑域编真值|可，保留域内/名义分母|边界点/峰/肩覆盖、外推率、最大误差|静默外推、将unknown计TN或只报成功窗|一轴/双轴支持不足分别报告，不能剔除整个类别|
|Saturation Stress|真实65535不能作未知峰顶真值；仅已知未截断合成/获批代理可人工削顶|可模拟不同宽度；真实受限值不得当正常背景注入基底|截断/恰等/肩部/未截断MAE与RMSE，峰低估、约束违反、收敛与先验敏感性|违反下界、未收敛却报恢复成功、把真实峰顶当已知|缺双肩、过宽截断、未知量程；C0可保留受限信息|

用途不等于真实性认证；多标签重叠须按Reference_ID及坐标并集去重。25区拒作普通参考，45区待证，所有批准Pending。每炉七框是有偏择样，不能推全谱误差。

检测单列：TP/FP/FN/TN只在可评估支持上计算，同时报告全点数、已知注入阳性总量、不可评估阳性和阴性、可评估阳性召回、全域阳性检出率及覆盖。不可评估阳性不计TN，不因缩分母掩盖漏检。点/时间段/波长段/二维块匹配：点精确坐标；段按预注册IoU阈值（待定）匹配，一对一；块内与外边界分层，不以边缘检出冒充整块召回。持续峰及瞬变峰保护区作为未注入阴性单列误标。D0仅全谱弱基准，需标明全炉离线依赖。

重构独立遮蔽，原真值仅进入评价端。MAE=mean|e|、RMSE=sqrt(mean(e²))；同时逐炉/逐窗给中位、P95、最大值及失败数，不只平均误差。显式传入以nm定义的固定目标峰窗、肩窗、背景（独立测量/训练拟合来源），不能按估计或被遮真值重新挑峰。峰位采用窗内唯一离散最大节点nm；峰高扣固定背景；FWHM取该峰连通半高两侧线性过零距离，缺交点/最大值并列/边界峰返回不可计算。多峰重叠需预注册分峰协议，本原型不自动分解。面积为固定峰窗背景扣除后梯形积分，未覆盖物理窗端点时不冒充完整连续面积。肩部只用独立肩窗，局部梯度只用受影响边。点/峰/肩/梯度的请求及可评估分母各自报告。

异常注入同一已审核输入比较D0/D1/D2；正负幅度用训练炉独立噪声尺度，保存原值/注入值/标签/种子和输入哈希。随机点与结构化时间/波长/二维块分别报告。0比例必须0点，未知kind/越域尺寸报错。削顶宽1/2/4/8/16节点，各记录真实nm宽度、阈值C、实际截断长度与恰等点，不能暗示所有阈值可得到任意目标宽。先独立合成，再待批准的未截断代理，最后仅局部证据审核真实受限观测；本轮只进行了前者的功能构造。

R0两次序分开，保存估计源mask及无支撑NaN；C2必须核对有限输入、递增坐标、非负参数，优化预算与收敛验收不是一回事。C2后续候选扫描alpha,beta∈{0.01,0.1,1}、预算{200,1000}，记录目标单调性、投影梯度残差、约束、峰窗/肩窗误差和先验解差异；收敛容差需训练侧校准并冻结，目前未实施，真实禁用。真实量程无证据时优先C0，不估计未知顶。

跨炉：10个外层留一炉，每外层9炉中逐一留1作内层验证，其余8炉拟合；不再固定最后一炉。配置保存90个内层划分，所有拟合子集含A/B网格；工况覆盖未知，单列Pending，不伪造分层。阈值、尺度底、噪声、峰窗及重构超参数只在外训练/内验证确定，测试炉不反馈选型。全十炉曾被EDA查看须披露，不能称完全盲测。先按炉、用途、网格报告，另给按点微平均和逐炉等权宏平均，峰窗重叠去重。

Q1为离线双向支撑，记录每输出最早/最晚输入时刻。Q3另行记录采样、到达、处理完成、available_time、参数拟合炉、是否用未来气体标签、延迟标签何时可得；未知到达时间阻断实时可部署性主张。此处不训练模型，不把离线全炉统计直接交给实时特征。

失败阈值尚未数字化：建议按测量分辨率/训练噪声和实际目标制定容限；不得看测试误差倒推阈值。签署配置与固定参考清单哈希后才可讨论执行，结构校验本身不是签名验证或真实授权。
''')
write('Q1_待共同决策事项.md','''# 待共同决定与未完成工作

全部Pending，Agent未代签，也没有区域Approved。

1. D1/D2每轴至少2个可用点、名义2r比例0.5和污染轴禁评是否采纳；半径节点数转每炉实际s/nm窗口；是否允许仅一轴的独立备用D1及如何单列其覆盖。
2. 70区用途与逐区证据，25困难区不作普通真值、45待证。REF-6C02057-F和REF-6C02107-F须核对半径4污染；其他原Accept需峰双肩及逐帧证据。原值和历史建议不改。
3. 峰窗/肩窗/背景来源、FWHM及多峰规则、误差容限/失败阈值、普通参考授权。当前普通真值获批数0，不能启动真实遮蔽。
4. R1暂缓实现是否认可；若重启须冻结两轴次序、缺节点与最大支持跨度，实施二维与非采样坐标验收。当前R1无代码无性能。
5. C2保留为非辨识压力候选，真实禁用；设备量程、收敛/步长/先验扫描仍未完成。C0保留信息基准优先级待确认。
6. LOHO内层轮换、工况覆盖、训练侧参数来源与Q3到达时钟。当前配置仅验证集合和A/B覆盖，未核实真实工况或可用时间。
7. 真实执行须两名队员明确批准编号/身份、配置版本和哈希、逐用途参考清单及哈希，显式execution_allowed=True。软件结构检查不能认证签署身份；本轮不生成有效真实批准记录。
8. Q2复核13条回应、70区修订与新旧模拟结果，再由队员共同决定是否关闭问题。Accepted指Q1接受意见，不等于Q2复审通过。

本轮到此停止：未正式清洗，未正式真实验证，不推进共同标准或main。需要Q2独立复审后再发下一阶段明确授权。
''')
counts=Counter(r['当前状态'] for r in matrix);cont={r:sum(int(a[f'Radius{r}_Upper_Neighbor_Centers'])>0 for a in revised) for r in (1,2,4)}
write('Q1_整改总报告.md',f'''# Q1交叉审核整改交付导航 v2

Task A-Q1-CR-002，2026-11-27；仅q1-spectral本线；统一标准v2。已基于完整审核报告、13条问题、70区意见、关键复算MD/JSON及独立复算代码读取后整改，输入六文件快照/哈希附后。

注意版本：被审Q1真实提交为`{BASE}`，用户摘要尾部写作`...ba69e`与实际Git对象不同。Q2审核材料取自固定`q2-gas-oxygen@{REVIEW}`，其目录/报告原ID是`CR-A-Q1-3172d08-v01`，用户使用`CR-A-Q1-3172d088-v01`；这里保留原报告ID并记录别名，不能把被审Q1基线当成Q2报告提交。

## 交付入口

1. [13项逐条回应](Q1_13项交叉审核整改矩阵.csv)：{dict(counts)}；接受意见与实施关闭分列，Q2复审与共同批准全Pending。
2. [70区修订](Q1_70区修订审核表.csv)：70唯一ID、十炉各7；25 Reject Candidate保留困难用途，45 Needs More Evidence逐条缺证；0个普通真值授权。旧70区保留未覆盖。
3. [D1/D2修复](Q1_D1_D2邻居不足修复报告.md)：有限支持、比例、污染、四状态与模拟边界。
4. [R1决定及R0审计](Q1_R1实现与验收报告.md)：R1仍未实现，R0两序及估计源可追溯。
5. [回归](Q1_回归测试报告.md)：旧61+12隔离重跑；新增{N}/{N}合成检查通过。风险重现不等于算法成功。
6. [验证基准](Q1_验证基准v2草案.md)与[配置](Q1_正式验证配置v2草案.json)：六类分层、检测/重构独立、显式峰窗/肩窗/FWHM/覆盖、按炉隔离；未冻结未执行真实验证。
7. [待决](Q1_待共同决策事项.md)：C2收敛/敏感性、R1、真实参考、工况与时钟等未完成事项。
8. [来源](审核输入来源清单.csv)、[方向邻域复算](70区_方向邻域复算.csv)、[S06语义补充](S06_形态与解释分列补充表_v2.csv)、[版本与哈希](版本变更与SHA256清单.csv)。

## 证据及边界

本轮70区污染分析仅使用冻结S04全量65535位置和S03原波长坐标，与Q2的半径2/4计数逐区完全匹配；按半径1/2/4方向邻居污染框数分别{cont[1]}/70、{cont[2]}/70、{cont[4]}/70。方向半径1与原矩形一节点环不是同一集合，不能直接当同口径。两新增区仍Needs More Evidence，半径4源位置、中心分母和实际nm展开范围均可查，不将14,805个上限位置当70个参考区。

本轮未重新读取XLSB或重复泛化EDA；引用Q2核验10附件及70统计结论，其原JSON已保存，不能冒充本轮再次直接核验附件。未在真实数据运行新版检测/重构、注入、遮蔽、削顶、性能评估或模型训练。合成测试未读取工作簿。

R0补点顺序依赖确认；峰指标新增固定物理窗和半高宽；真实执行开关现在为必须条件并绑定结构化批准/清单，但当前不存在真实签署。C2未收敛验收，不具备真实峰顶辨识证明；R1未实现且配置禁用。算法代码在../../代码/validation_modules_v2.py，新测试在../../代码/test_validation_v2.py；原三文件及历史结果不修改。

## 历史计数与发布说明

旧完整性JSON的243为生成旧文件清单前的文件数；旧文件清单实际244条，包含完整性JSON但排除自身；加清单自身为245文件，Q2已核验244条Git LF字节。旧Q1进度“不推送”属于早期阶段；3172d08已发布为本次审核基线。此轮全部新增在Q1专属目录，未修改共同进度、main或Q2内容；本轮未推送。新清单采用当前磁盘原字节SHA256，明确排除清单自身和末次验收JSON；不与Git LF哈希混淆。

停止状态：代码与合成回归交付完成；待Q2独立复审及两名队员共同确认。13条的Accepted不是Resolved，75类设计/超参数提案不是正式验证结果。
'''.replace('75类设计','各类设计'))
# Freeze all preexisting files: byte hashes, not inferred modification timestamps.
assert all(sha((R/p).read_bytes())==digest for p,digest in historical.items())
dump('历史文件保护核验.json',dict(historical_file_count=len(historical),all_unchanged=True,hashes=historical,scope='运行前已有Q1历史文件；排除本轮新文件与缓存'))
# Manifest includes own generating code and new module/tests; excludes self and final receipt.
newfiles=[p for p in O.rglob('*') if p.is_file()]+[P/'代码'/n for n in ('validation_modules_v2.py','test_validation_v2.py','build_crossreview_remediation_v2.py')]
entries=[]
for p in sorted(newfiles):
    b=p.read_bytes();entries.append(dict(File=p.relative_to(R).as_posix(),Bytes=len(b),SHA256=sha(b),Version='A-Q1-CR-002-v2',Original_Version=BASE,Reason='响应Q2十三条审核；新版本不覆盖证据',Parameters='详见v2配置；默认仅合成',Tests=f'旧61/61、旧12/12、新{N}/{N}',Hash_Policy='磁盘LF原字节；清单自身和本轮验收.json不在本表'))
csvout('版本变更与SHA256清单.csv',entries)
assert all(sha((R/e['File']).read_bytes())==e['SHA256'] for e in entries)
dump('本轮验收.json',dict(task='A-Q1-CR-002',review_commit=REVIEW,baseline=BASE,issues=len(matrix),response_statuses=dict(counts),references=70,unique_ids=len(byid),reference_statuses=dict(Counter(r['Review_Status'] for r in revised)),ordinary_truth_approved=0,radius_contaminated_regions=cont,legacy_functional_checks=61,legacy_risk_checks=12,new_synthetic_checks=N,all_tests_pass=True,manifest_entries=len(entries),manifest_hashes_match=True,manifest_sha256=sha((O/'版本变更与SHA256清单.csv').read_bytes()),historical_unchanged=True,R1_implemented=False,C2_convergence_certified=False,real_workbooks_read=False,real_cleaning=False,real_validation=False,joint_approval='Pending',pushed=False))
print(json.dumps(dict(output=str(O),issues=len(matrix),references=len(revised),new_checks=N,files=len(entries)+2),ensure_ascii=False))
