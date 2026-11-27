from pathlib import Path
import json,csv,hashlib,collections,subprocess
P=Path(__file__).resolve().parents[1];R=P.parent;O=P/'实验验证/正式清洗前置审核'
with (O/'Q1参考区域审核表.csv').open(encoding='utf-8-sig') as f:refs=list(csv.DictReader(f))
tests=json.loads((O/'独立模拟风险测试.json').read_text(encoding='utf-8'));counts=dict(collections.Counter(r['Recommendation'] for r in refs))
def put(n,t):(O/n).write_text(t.strip()+'\n',encoding='utf-8',newline='\n')
put('Q1异常分类与处理建议.md',f'''# Q1异常分类与处理建议：正式清洗前置审核

本轮仅审核既有70框，不新增泛化EDA；审核表保留每框炉号、原网格、Sequence/Excel边界、波长、强度统计、上限分布、局部峰/变化、支持与反对证据。真实源只读，旧V02登记及S/V历史文件不修改。
审核建议数量：{json.dumps(counts,ensure_ascii=False)}。状态为审核者建议，非正常真值认证，全部Joint_Approval=Pending，Normal_Truth_Certified=false。

## 建议口径（待双方复核）

- Reject Candidate：本框/一节点环邻域含65535，或与整列重复边缘通道重合时，拒绝作为本轮普通“未截断、独立测量”参考真值。拒绝此用途不表示观测无效；仍可保留作删失/边界困难案例。
- Accept Candidate：仅对无上限环邻域、无重复通道、无旧S05候选重合的背景A/平缓F框，建议进入人工确认名单，不授权真实验证。不凭低分认证正常。
- Needs More Evidence：峰、高强度、快速变化、既有候选或其他不能解释的形态，需要原始邻域与工艺证据。
- Pending：必要证据缺失或尚未完成审查的保留状态；本轮70框均有数据可核查，不为凑齐状态而强行分配。

这些规则只是本次参考用途的透明审核口径，不是最终异常阈值。保留稳定/困难分层，不能因为背景易通过而把最终验证集缩成全部平滑区。原S05候选只作风险提示；本轮未运行D0/D1/D2在真实参考区计算性能。
统计口径：Halo_65535/Halo_Points指候选框加一节点环的整个扩展窗口，包含框内，不是单独外环；Within_65535是框内子集，不将两者相加。Neighbor_Evaluable_Centers仅指几何上可取完整四邻域的中心数量，包含65535中心，不等于最终检测器可评估点数；四邻域污染和MAD=0计数用这一几何集合，不冒充错误率或检测性能。

## 分类与后续处理建议

|观察类别|当前可说什么|后续候选行动|当前禁止|
|---|---|---|---|
|65535中心及平台|受限观测候选，峰顶未知|独立suspected_censor标签，先核查设备与完整双肩|直接换NaN或恢复未知峰顶|
|上限邻域污染|median/MAD与残差可能改变|分别记录中心上限、四邻域上限和更大窗污染；比较排除/保留策略及可评估覆盖|排除邻居后悄悄用不同分母比较|
|持续窄峰|时间重复支持、物理归属仍未知|独立峰保护审核；统计触发而非直接删峰|按全局高值或波长残差自动删除|
|瞬时尖峰/低点|真实事件和错误都可能|时间/波长双向证据、反例与共同审阅|仅凭D2共识认错|
|宽平台/连续块|小窗内部可能没有残差|多尺度、边界和共同事件描述候选；单独块验证|把低分当全部正常|
|重复边缘通道|不同lambda有相同整列强度|保留原坐标和值，调查采集；独立边界/重复压力测试|删除或合并通道|
|快速大范围变化|工艺候选，非已确认工艺时刻|困难层单列，联系Q2同步事件及可用时间|用平滑性替代真实性|

若双方通过参考框，也只是接受为特定实验的观测真值代理，不意味着证明无测量误差。当前未正式清洗任何真实光谱。
''')
put('Q1算法风险及改进报告.md','''# Q1算法风险及改进报告

输入依据：S01–S07、V01–V04及70框原值邻域；真实数据只做框级描述和四邻域MAD/污染计数。另运行12项独立模拟压力检查，结果JSON明确非真实性能。“检查通过”意味着复现了预期风险或边界行为，并非算法检测准确。

## D0/D1/D2的实际适用边界

分数z=(I-med)/(1.4826MAD+epsilon)。原epsilon=1在MAD=0时成为全部尺度，必须有单位和来源。模拟同一微小偏离在强度乘100而epsilon不变后从不触发变触发；epsilon同步乘100后结果复原。三种检测器都出现该现象，不能宣称阈值尺度无关。改进提案是记录MAD=0/不足邻居、使用经训练或独立标定的尺度底并报告floor敏感性，未知仪器噪声底不得伪造。

65535污染不仅是中心：模拟清洁邻域[100,100,102,104]与中心140得z≈15.709；含两个上限邻居[100,102,65535,65535]时z≈−0.674，正偏离可被掩盖甚至改符号。提出独立邻域污染mask和窗口有效样本数；排除上限后样本过少则不可评估，不能自动判正常。当前D0/D1/D2原型没有内置完整污染屏蔽层，正式实验前需实现并单独功能测试。

D0仅弱基准：全谱背景异质、真谱线和全局尺度可主导MAD。D1为时间或波长任一方向触发（OR），模拟持续窄峰15/15点被标，存在明显误伤风险。D2为两方向且同号（AND），该持续窄峰0/15点被标，但一个独立真实瞬时峰仍被触发，不能把D2当真峰保护保证。两者对21×31均匀异常块的内部都漏检，本模拟在块内甚至0/651点触发；需多尺度/块边界证据，不能仅提高或降低单一阈值解决。

上述均为构造反例而非真实误判率。正式比较须同一注入输入、独立审核峰区、按异常形状与污染/边界分层，分开报告正负候选和不可评估覆盖。边界截短及邻居不足要形成eligible mask，不能让NaN比较为False后计成正确负例。

## R0、R1与C2

R0在完整矩形单元是非负权重和为1的双线性组合，域内不会超过所用节点包络；测试亦如此。其风险是压低未采到/遮蔽的尖峰和顺序依赖，而不是必然过冲。模拟前三整行缺失无两侧支持时288点保持NaN，没有虚构边界值；须报告失败覆盖，不能只在恢复成功点报低RMSE。真实观测若输入含错误，上述包络保证也不保证正确。

R1在V03仅有分方向PCHIP组合定义，尚未实现，未测试其边界或峰宽性能。一维PCHIP形状保持不等于二维全局C1或未知峰恢复；两轴顺序、缺口支持与域外行为必须实现和验证。不得用R0通过测试替代R1验收；当前正式配置将R1禁用，待独立实现后再批准启用。

C2原型以非截断损失、非均匀lambda二阶曲率和时间正则，投影保证上限位置X≥C。独立模拟中违反数0，但真峰约34.665、固定200步输出最高30，未恢复峰高。该例不能区分收敛预算、正则偏差与信息不足，也不推广为任何参数都失败；它足以否定“下界满足即恢复正确”。还缺收敛诊断、可靠肩部保持、非负性与边界约束测试，不能投入真实削顶修复。

不可辨识的直接反例：[1,3,5,3,1]与[1,3,9,3,1]在C=3时产生相同截断观测，峰顶可不同。宽平台应默认保留标签与下界；需要先验时明确先验，并对不同可行解给敏感性包络，不能称已验证置信区间或为图形完整而补峰。

## 验证配置改进

1. 审核参考框用途，分普通重构、峰保护、变化困难、删失观察/边界压力，避免一个名单同时冒充所有真值。
2. 定义点/时间段/波长段/块和峰附近遮蔽，真实参考点隐藏后不进入模型输入；模拟注入与削顶共用冻结样本，不随算法改变样本难度。
3. 峰指标在固定物理波段、预先记录基线与两侧支持内计算。新增峰宽评价设计，不能把旧局部节点宽度当精确真值；无双侧交点或削顶时峰宽不可计算，报告覆盖。
4. 按炉隔离拟合、选型和最终评价；十炉已有EDA不叫完全盲测。Q1离线两侧重构和Q3因果输入是不同信息条件。
5. 本轮只复现独立模拟风险，未对真实参考框注入、遮蔽、插值或削顶。
''')
config=dict(schema='Q1-preclean-review-v1',status='Pending',frozen=False,real_data_execution_allowed=False,reference_table='Q1参考区域审核表.csv',reference_sha256=hashlib.sha256((O/'Q1参考区域审核表.csv').read_bytes()).hexdigest(),review_recommendations=counts,approved_reference_ids=[],required_approvals=['队员A实际确认待填写','队员B实际确认待填写'],reference_rules=dict(recommendation_not_truth=True,Accept_Candidate_not_execution_approval=True,rejected_for_ordinary_truth_retained_as_stress=True,contamination_halo='至少覆盖算法实际窗口；当前表只核查一节点环，半径2/4还需扩窗审核',normal_truth_certified=False),scope='独立模拟可运行；真实实验待共同批准',seed=20261127,models=dict(detection=['D0','D1','D2'],R0='已有模拟原型；真实执行禁用',R1='disabled: implementation and acceptance pending',C2='disabled for real: convergence/shoulder/uncertainty checks pending',C0='保留上限标签，不估峰顶'),search=dict(k=[6,12,20],floor_original_intensity_units=[1,5],time_radius_nodes=[2,4],wave_radius_nodes=[2,4],physical_nm_window='Pending; 两网格不可假定等列宽等nm',saturated_neighbor_policy=['独立标记保留作对照','剔除污染邻居且不足样本标不可评估，功能待实现']),injection=dict(types=['isolated_high','isolated_low','time_segment','wavelength_segment','block'],fractions=[.0001,.0005,.001],amplitude_local_scale=[5,10,20],block_shapes_nodes=[[3,3],[9,7],[21,15]],no_overlap=True,report_actual_fraction_and_denominator=True),masking=dict(types=['random_points','time_segments','wavelength_segments','2D_blocks','near_peaks'],preserve_hidden_values_only_for_evaluation=True,unsupported_boundary='NaN and coverage; no silent extrapolation'),clipping=dict(widths=['single_point','narrow','wide','long_platform'],thresholds='训练参考区分位0.8/0.9/0.95，具体值与参考区审批后冻结',test_truth_not_used_to_choose_threshold=True,real_65535_truth_unknown=True),metrics=dict(detection=['TP','FP','FN','TN','Precision','Recall','F1','FPR','approved_peak_flag_rate','eligible_coverage'],reconstruction=['MAE','RMSE','peak_position_nm','peak_height','peak_width_nm','peak_area','gradient_RMSE','coverage'],clipping=['masked_error','peak_height_error','shoulder_MAE','lower_bound_violation_count_and_rate','width_stratification'],peak_window='预注册物理区间，跨网格以nm计',peak_baseline='冻结端部基线定义，不按结果选择',peak_width='半高两侧交点nm差；模拟可用已知连续函数，真实参考用明确节点线性测量规则；缺交点不可计算',near_zero_relative_error='不默认MAPE；绝对误差主报'),split=dict(candidate='outer LOHO with inner held-out heat',all_heats=[r['Heat_ID'] for r in refs if r['Class'].startswith('A_')],train_only='拟合尺度/模型参数',validation_only='参数和方法选择',test='冻结后单次评价，不回传调参',group_coverage=['A','B'],existing_EDA_not_blind=True,Q1_offline_distinct_from_Q3_causal=True),failure_policy=['不可评估和不收敛单列，不删失败样本抬分','R1尚未实现不得输出性能','C2只满足下界不视作恢复通过','测试条件不得看测试误差后反复改'],release_gate=['两人确认逐框用途/真实参考名单','邻域污染与MAD0策略实现并验证','峰宽与边界指标功能测试','冻结参数、样本、划分和代码SHA256'])
(O/'Q1正式验证配置草案.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
put('Q1待共同决策事项.md','''# Q1待共同决策事项

全部Pending，本文件不改共同决策日志。

1. 逐框确认普通参考/峰保护/快速变化/边缘压力/删失案例用途。Accept Candidate只是本次审核建议，不能代替两人认可；Reject Candidate仅拒绝当前真值用途，不判原值无效。
2. 决定65535真实机制需要的设备证据；窗口污染半径至少覆盖实际算法窗。当前表只一节点环，不能保证D1/D2半径2或4不受污染。
3. MAD为0/邻居不足的eligible mask、floor尺度与标定来源；固定阈值不能跨任意强度尺度机械使用。
4. 确认持续/瞬时峰保护要求和连续块压力测试；不可用D2一致性直接认证错误或正常。
5. 明确R0边界未支持的拒绝策略；R1要先实现验收，不能把数学定义当代码；C2要补收敛、肩部和先验不确定性检查。
6. 冻结峰物理区间、基线、峰位/高/半高宽/面积测量规则和不可计算口径，按实际nm比较。
7. 共同批准参考区与注入/遮蔽/削顶的比例、尺度、随机种子、按炉划分及失败规则。既有EDA不作为盲测，测试结果不能反复用来改冻结配置。
8. 审核通过后只进入获授权的小规模真实验证，不自动进入正式清洗或Q3训练。保留原值、标签、试验副本和重构结果分离。

本轮没有最终算法、真实正常数据认证、正式真实验证或清洗成果；完成后停止等待共同审核。
''')
assert len(refs)==70 and all(r['Joint_Approval']=='Pending' for r in refs)
assert all(c['Check_Passed'] for c in tests['checks'])
baseline='f24b1292629bf8a46d4e00e4a80a429327789094'
# Confirm all previously tracked artifacts are byte-identical to their committed form.
entries=subprocess.check_output(['git','ls-tree','-r','-z',baseline,'04_Q1光谱研究'],cwd=R).split(b'\0')
for entry in entries:
    if not entry:continue
    meta,name=entry.split(b'\t',1);actual=subprocess.check_output(['git','hash-object','--no-filters',name.decode('utf-8')],cwd=R,text=True).strip();assert actual==meta.decode().split()[2],name
result=dict(reviewed_regions=70,recommendations=counts,simulation_checks=len(tests['checks']),historical_tracked_files_unchanged=True,real_preprocessing=False,real_validation=False,joint_approval='Pending',raw_hashes_unchanged=True)
put('本轮验收.json',json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
