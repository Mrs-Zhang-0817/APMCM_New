from pathlib import Path
import json,csv,hashlib,re
P=Path(__file__).resolve().parents[1];V=P/'实验验证';A=V/'V01_成果自审';B=V/'V02_可信参考区';C=V/'V03_数学模型细化';D=V/'V04_实验程序准备';C.mkdir(exist_ok=True)
def read(path):
    with path.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def put(path,text):path.write_text(text.strip()+'\n',encoding='utf-8',newline='\n')
def out(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
refs=read(B/'V02_候选参考区域登记表.csv');checks=read(A/'V01_关键结果复算表.csv');tests=json.loads((D/'V04_模拟功能测试结果.json').read_text(encoding='utf-8'));assert all(x['Passed'] for x in tests['checks'])
issues=[('V01-01','评分只排除中心65535','四邻域仍包含65535；可能改变median和MAD','保留旧结果，后续加入“邻域受上限污染”标签并比较排除/不排除策略','Observed Fact'),('V01-02','1.4826MAD4+1被用于评分','四邻域样本小；MAD=0时分母=1，单位随原强度；缩放强度会改变分数','不将系数视为噪声校准；验证floor/窗口敏感性','Observed Fact'),('V01-03','案例Evidence_Class统一讨论削顶','部分非65535案例也被填入“无明显平台不能否定削顶”，语义不适用于普通点','只对真实上限E/F使用削顶证据分类；普通A/B/C/D/H逐项说明形态','Observed Fact'),('V01-04','各案例标注Observed Fact或Hypothesis','几何事实与削顶解释有时放在同一状态字段','拆分形态事实、解释假设、审批Pending，不静默回写原CSV','Observed Fact'),('V01-05','候选峰宽使用局部最小值','±20列可能截断宽峰或仍含上限；不是仪器校正FWHM','维持离散候选宽度名称；可信参考区另审核背景和两侧边界','Observed Fact'),('V01-06','代表案例由极值选取','不能用极端案例或候选低分区估计总体误判率','分层参考候选，纳入困难/边缘/快速变化，记录偏差','Observed Fact'),('V01-07','4/8邻域均332组件','数值一致，不能泛化为任意数据的两种邻接等价','保留两种定义与独立核验，不虚构差异','Observed Fact')]
out(A/'V01_问题与修正建议.csv',[dict(Issue_ID=i,Old_Statement=old,New_Evidence=e,Suggestion=s,Conclusion_Status=st,Approval_Status='Pending',Original_Artifacts_Modified=False) for i,old,e,s,st in issues])
put(A/'V01_Q1成果自审报告.md',f'''# V01 Q1成果独立自审

Task ID：A-Q1-V01；研究问题：旧结论能否用独立实现复核。输入为S01–S07报告/CSV/运行记录及十炉原始XLSB；逐份大小、版本、列头、前后SHA256核验。原文档哈希清单在V01_复核运行记录.json，旧成果未覆盖。

实际复算{len(checks)}条记录，十炉通过。光谱总点27,816,683，65535总点14,805，合并比例14,805/27,816,683×100%=0.05322346%左右（精确值以CSV算式为准）。各炉点数分母n×2047，与旧表一致；时间为Sequence首值起算0.5秒，lambda严格单调但步长不均匀。
波长A附件1–4、B附件5–10组内逐点一致；同列差1.145–4.712nm，MAE3.52306595017nm、RMSE3.69228205581nm，覆盖交集340.535–1023.303nm。差异范围不为零，不支持固定平移。优先保留每炉真实网格建函数，减少前置重采样误差；但跨炉特征、重叠波段、峰位/面积可比性仍须验证，未共同决定最终策略。
26对是不同lambda坐标上的强度全列相同，不是波长重复：每炉前三通道形成两对，B组末两通道再一对；集中于边缘。可能影响局部MAD、边界曲率及特征重复计权，不能直接删除。

连通性改用并查集独立实现，与旧BFS的每炉4/8组件数和点数守恒一致；每种邻接合计332，均覆盖14,805点。附件5代表平台915个连续波长节点，左右肩低于65535；支持削顶形态，不证明16位设备或真峰高度。单点上限没有平台也不能否定削顶。

评分复核：四值排序取中间二值平均，绝对偏差同样排序；代表高分位置另用Python statistics.median标量复算。|z|>12/20/30仍为56,269/17,074/6,309，分子仅内部非65535中心，可评估分母也排除该类中心；全矩阵比例另报，边界不参与。正负残差均在|z|中，MAD=0时分母为1。1.4826是常用稳健尺度因子，不表示这里四点噪声服从正态；常数1有原强度单位，非尺度无关。

发现的修正重点是解释和验证口径，而非上述主计数错误：邻域仍可包含上限、普通点削顶分类不适用、状态应拆分、候选峰宽/极端样本选择局限。逐项旧陈述、新证据和建议见V01_问题与修正建议.csv，不静默改旧表。
缺少真实异常标签和仪器参数；没有把独立复算成功解释成物理机制已确认。局部最大差和图中折线只连接原采样点，不能证明已构造最终连续函数。本轮只读复核，未调用真实谱重构。

结论：主要数值结果得到复核（Observed Fact）；物理解释Hypothesis，方案Candidate Method，共同审批Pending。后续先审核参考区与模型定义，再冻结真实实验条件。
''')
put(B/'V02_可信参考区筛选原则.md','''# V02 可信参考区域候选原则

Task A-Q1-V02，目标是提出待审观测区域而非真值正常集。每炉七类：背景A、持续尖锐候选峰B、较宽高强度波段C、快速变化D、未达上限高值E、时间平缓F、边缘G。共70个矩形候选，按真实Sequence与lambda定位，保留两套网格和原值。
每框中心选择规则见登记Reason：背景按低波段列标准差、峰用既有中位谱局部对比、快速变化用整谱L1、高值取非上限极大、平缓按相邻L1、边缘交替低/高。窗口中心±3时点和±8列，边界截断；不是共同确认的最终实验块大小。
不是按待评估S05低分筛选。S05候选数量只作为风险标注，另列窗口内/邻域65535和重复通道覆盖。含风险者保留供审查，不自动成为实验参考区；即使没有风险也不能认证正常。
两名队员逐框审核原值、时空邻域、上限、谱形、重复边缘及替代解释。允许通过、缩小、拒绝或继续Pending Review，记录理由与确认人。正式验证只接受双方已确认的冻结清单，不能从本70区直接启动。
''')
risk=sum(int(r['Saturation_In_Halo'])>0 for r in refs);candidate_risk=sum(int(r['Prior_Score_Candidates'])>0 for r in refs)
put(B/'V02_参考区选择偏差说明.md',f'''# 候选参考区偏差与覆盖

70候选覆盖10炉、A组28框/B组42框、七类各10框，状态全部Pending Review。{risk}框的邻域有65535，{candidate_risk}框含既有局部评分候选；这是审核风险，不是自动剔除或认可。时间阶段与炉次分布见覆盖CSV；窗口可重叠，70不等于70个独立实验对象。
稳定/平缓候选天然偏向容易重构，峰/高值/快速/边缘分层用于抵消单一偏差，但固定极值选择仍不代表随机总体。框的列宽相同却nm跨度不同，后续实验应同时报告节点数与物理宽度。
不得用D0/D1/D2自身不触发的区域定义全部正常参考，也不得据参考集可重构性反复删除困难样本。当前C只是较宽高强度波段候选，未认证为真实宽峰；B有时处于上限，需先审查或另找未截断对照。G刻意包含重复边缘以暴露失败情形，不保证可靠真值。
人工审核图册为附件1和5各七图（共14图），其他炉候选仍有精确坐标可按需补图。交叉审核精选索引只要求先看12图，不要求重看全部120图。没有在任何框上实际注入、遮蔽或拟合。
''')
put(C/'V03_异常检测候选数学模型.md','''# V03 检测模型细化（Candidate Method，Pending）

输入为每炉原始坐标(t_i,lambda_j)、I_ij与独立质量标记；输出分方向有符号分数、可评估mask和候选mask，不直接修改观测。65535中心及其污染邻域须单独标记；候选比较按同一份注入输入。

D0：全矩阵基准m=median(I)，a=median|I-m|，z=(I-m)/(1.4826a+epsilon)，|z|>k。当前代码epsilon=1原强度单位、k=6只为模拟功能默认值，不是最终阈值。输入全谱统计不适合直接解释不同lambda背景，可能大量误伤真峰。复杂度O(N)量级、O(N)内存；NaN排除，若无可评估观测必须报不可评估。

D1：分别定义不含中心的时间窗N_t和波长窗N_lambda，z_d=(I-med(N_d))/(1.4826MAD(N_d)+epsilon)。候选P1=(|z_t|>k)或(|z_lambda|>k)，高/低均检。原型半径2为节点数，分别对应约1秒及局部两节点的nm跨度；真实验证需比较物理时间/nm窗，不能假称两网格同列窗物理等宽。边界截短，方向少于2个邻居得NaN，调用者必须保存有效方向和评价分母。逐窗朴素成本O(N·window)，原型按行/列循环，分数O(N)内存。持续真谱线可能波长方向偏离却时间一致，OR易误伤；连续块内部可漏检。

D2：P2=(|z_t|>k)且(|z_lambda|>k)且sign(z_t)=sign(z_lambda)。这是二维方向共识，不等于对完整二维异常形状建模。持续峰若时间方向正常可被保护，但真实瞬时峰两方向均高也会触发；持续段/大片平台内部可能低分。任一方向不可评估时共识不可得，不把NaN当正常真值。成本与D1同级。

D3低秩稀疏仅保留备选：min ||L||_*+gamma||E||_1，I=L+E。假定异常稀疏且正常近低秩，宽截断/工艺变换可能违背假设；反复SVD成本高，窄谱线可能被分进E。未实现、不列首轮必跑。

首轮优先D0作可解释弱基准，D1/D2揭示方向证据差异，不凭模拟F1选真实最终算法。谱峰保护必须由独立审核的峰区触发率和反例评估，不能宣称共识一定保峰。k、窗、epsilon都待冻结。输入真实数据会包含离线未来邻居，不能直接充当Q3实时检测。
''')
put(C/'V03_二维连续重构候选数学模型.md','''# V03 二维连续重构候选模型

优先每炉保留实际非均匀lambda与t。定义域D_h=[t0,tN]×[lambda0,lambdaP]，域外默认不外推。普通错误和缺失需经审核mask才能隐藏，真实上限不自动变普通缺失。本轮仅在独立模拟谱实现以下R0。

R0先在可支持的缺口上作分方向线性补点：按每列实际t，用目标两侧可靠点线性权重；剩余缺口按每行lambda处理。没有双侧支持的边界仍NaN，不能用np.interp默认端值填充冒充外推。完整网格后，在任一单元[t_i,t_(i+1)]×[lambda_j,lambda_(j+1)]定义F=(1-u)(1-v)X_ij+u(1-v)X_(i+1,j)+(1-u)vX_(i,j+1)+uvX_(i+1,j+1)，u=(t-t_i)/dt，v=(lambda-lambda_j)/dlambda。共享边界节点保证C0连续，导数可不连续。GridSurface提供任意查询网格求值，支持非原采样坐标；不完整网格拒绝创建函数。先时间后lambda会影响缺口结果，需与反向顺序比较；复杂度补点约O(N)，分数/补全O(N)内存，查询原型按列插值，非最优实现。

R1候选：对每个原lambda_j构建时间PCHIP f_j(t)，再对固定查询t，在原lambda节点值f_j(t)上构建波长PCHIP H_lambda，F(t,lambda)=H_lambda({lambda_j,f_j(t)})(lambda)。这才明确二维任意求值，不把单条一维PCHIP称完整二维模型。PCHIP各轴形状保持及C1不保证整个二维曲面全局C1或物理真实性；非线性顺序不交换，必须比较t→lambda与lambda→t。输入需处理经审核缺口及双侧支持，边界不外推。原型尚未实现，SciPy未安装，不能报告性能。峰未被采样则任何保形算法也不能凭空知道真峰。

R2备选张量样条F=Σ_ab c_ab B_a(t)B_b(lambda)，用可靠点损失与分方向曲率罚项选参数。定义域、边界条件和节点显式固定；少点边界/大片缺失不具充分约束。可提供连续任意求值，但过冲/负值、过平滑窄峰风险需遮蔽验证。成本取决于基数K和稀疏求解器，密集最坏O(K³)、内存O(K²)，未实现，非首轮必跑。

R0优先功能与误差基准；R1待共同确认与依赖准备后实现；R2仅在前两者暴露系统性局限时再考虑。全炉离线两侧观测可以用于Q1，Q3必须另作因果实现。Q3共同特征候选在真实交集340.535–1023.303nm定义固定物理区间或对函数作固定lambda求值，仍须验证重采样/峰保真且仅用训练炉拟合参数；本轮不对真实谱统一网格。

数学性质参考：[SciPy PCHIP官方文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html)。这里只细化候选结构，非方法已选定。
''')
put(C/'V03_削顶观测与约束重构模型.md','''# V03 削顶观测与约束模型

仅在假设y=min(x,C)成立时，y=C给出x≥C而不提供上界。C=65535仍是待验证设备解释。普通异常、缺失与删失不同，保持独立mask。
C0：保留y和上限标签，不估计未知峰顶，输出状态为受限观测；它是保守信息基准，不声称恢复精度。
C1：把假定截断位置从输入隐藏，以R0普通线性恢复作对照。可能估计<C，违反下界，因此必须报告违反点数/可评估截断点数；不能因为曲线好看就接受。
C2原型：min_X 0.5Σ_(非截断)(X-y)² + alpha/2 ||D_lambda² X||² + beta/2 ||D_t X||²，s.t. X_ij≥C on clipped。非均匀波长三点二阶导算子系数为(2/[hL(hL+hR)], -2/[hLhR], 2/[hR(hL+hR)])，时间用真实dt一阶差分。alpha/beta平衡强度平方与导数平方，数值随nm/s尺度变化；默认.1/.1只模拟测试，不是数据校准。没有高斯峰假设。
实现投影梯度X^(r+1)=Pi_K[X^r-eta∇J]，仅截断点投影max(X,C)。eta=.9/L，L界取1+alpha||D2||_1||D2||_inf+4beta/min(dt)²。默认200迭代只是固定预算，不是收敛证明；函数用可靠非截断点损失而不将截断y=C当等式真值。边界使用内部二阶项和自然的缺少外节点，不外推。一次迭代O(N)，内存O(N)，后续需目标下降/停机与参数敏感性验证。
宽平台可有无穷多满足下界的峰，正则只是选先验偏好的解，不能把该解当真实强度。需要多组alpha/beta/边界/先验解的包络并注明不是统计置信区间；原型尚未实现可信区间或证明唯一可辨识。肩部误差和下界违反分别报告，满足约束不等于峰高恢复。
对于缺乏完整肩部、过宽截断、邻域也不可信或优化不收敛的区域，优先C0，不强行给出未知峰顶。人工削顶可用已知模拟真值评价，却不能证明真实65535的真峰已恢复。本轮所有C1/C2执行仅针对独立模拟数据。
''')
priorities=[('D0','全局median/MAD','低','O(N)','孤立极值弱基准','低','全局背景差异误报','P/R/F1/FPR及峰区触发','P1','已实现，仅模拟'),('D1','分方向稳健OR','中','O(Nw)','孤立及方向异常','中','窄峰误判、块内部漏检','同上+方向分数','P1','已实现，仅模拟'),('D2','分方向AND同号','中','O(Nw)','双方向局部孤立','中','连续块漏检、瞬时真峰误判','同上+块召回','P1','已实现，仅模拟'),('D3','低秩稀疏','高','多次SVD','稀疏异常','待证','窄谱线/工况近低秩假设不成立','峰形+跨炉','P3','未实现'),('R0','原坐标双线性连续面','低','补点O(N)','普通缺失对照','有限','峰高压低、边界无支持','MAE/RMSE、峰位/面积','P1','已实现，仅模拟'),('R1','分轴组合PCHIP','中','约O(N)预构造；查询依轴长','小范围普通缺失','待证','组合顺序、二维光滑性','峰保真和边界','P2','未实现'),('R2','张量样条','高','依稀疏求解；密集O(K³)','较连续面','待证','过冲/平滑','遮蔽与峰反例','P3','未实现'),('C0','保留受限观测','低','O(N)','截断','不估峰顶','信息不完整','标签一致性','P1','已保留策略'),('C1','普通插值对照','低','O(N)','模拟削顶对照','低','违反下界','截断区误差/违反率','P1','已实现，仅模拟'),('C2','曲率正则与下界投影','中','O(iter*N)','候选截断','依先验','不可辨识、正则偏差','峰高、肩部、下界','P2','已实现原型，仅模拟')]
out(C/'V03_候选方法优先级比较.csv',[dict(Method=x,Principle=p,Difficulty=d,Cost=c,Applicable=a,Peak_Preservation=pp,Risk=r,Metrics=m,Priority=pr,Implementation=im,Status='Pending') for x,p,d,c,a,pp,r,m,pr,im in priorities])
config=dict(status='Pending',frozen=False,reference_file='../V02_可信参考区/V02_候选参考区域登记表.csv',reference_status_required='both teammates approved; currently none',seed=20261127,injection=dict(types=['high','low','time','wavelength','block'],fractions=[.0001,.0005,.001],amplitudes_local_scale=[5,10,20],sizes=[[3,3],[9,7],[21,15]],nonoverlap=True),masking=dict(types=['points','time','wavelength','block','peak'],same_fractions=True,boundary_stratum=True),clipping=dict(severity_quantiles=[.8,.9,.95],shapes=['single','narrow','wide','platform']),candidate_models=['D0','D1','D2','R0','R1_pending_implementation','C0','C1','C2'],search=dict(threshold=[6,12,20],epsilon_original_units=[1,5],time_radius_nodes=[2,4],wave_radius_nodes=[2,4],alpha=[.01,.1,1],beta=[.01,.1,1],C2_iterations=[200,1000]),split='proposed LOHO with inner validation heat; not approved',selection='train/internal validation only; prioritize peak preservation and coverage with accuracy; no single F1 ranking',failure='report NaN/unsupported coverage/nonconvergence; no silent removal or test retuning',real_validation_allowed=False)
(D/'V04_待共同确认实验配置.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
bench=[x for x in tests['timings'] if x['Operation'].endswith('benchmark') and x['Shape']=='(96, 192)'];costs=[]
for r in bench:
    ratio=27816683/(96*192);costs.append(dict(Operation=r['Operation'],Measured_Seconds=r['Seconds'],Measured_Shape=r['Shape'],Ten_Heat_N=27816683,Linear_Point_Extrapolation_Seconds=r['Seconds']*ratio,Limit='只作粗点数外推；不含XLSB读取、多参数/折数、缓存、真实窗口差异及收敛；非真实验证实测'))
out(D/'V04_真实实验成本粗估.csv',costs)
put(D/'V04_实验程序说明.md',f'''# V04 实验模块与模拟功能测试

独立模拟谱：非均匀lambda背景、随时间变化的Lorentzian窄峰和三角宽峰；并未假设所有真实峰为高斯。生成器只使用人工公式，不读取XLSB。实际{len(tests['checks'])}项功能断言通过，检查注入/标签一致、同种子复现、五类遮蔽、参考不变、尺寸、已知混淆矩阵和MAE/RMSE、单点/窄/宽削顶、下界、分炉隔离及非节点连续求值。
模块validation_modules.py提供注入、遮蔽、削顶、D0/D1/D2、R0、GridSurface、C2及评价/划分。R1/R2/D3未实现，不冒充已跑候选。不同检测器传入同一observed副本并记录输入SHA；注入JSON含位置、原值、修改值和种子；隐藏mask和评价真值单独记录，不传给重构函数。重构签名仅(observed,t,w)，obs中被遮蔽值为NaN。
R0对无双侧支持的边界留NaN，报告可评估覆盖；全缺失测试应不可恢复，不能默默填0。GridSurface在有限完整网格上提供非节点bilinear求值，解析平面F=2t+3lambda+1在中点精确匹配，域外报错。此为程序逻辑，不证明真实谱重构准确。

指标：P=TP/(TP+FP)，R=TP/(TP+FN)，F1=2TP/(2TP+FP+FN)，FPR=FP/(FP+TN)；分母0为None。峰区误伤率=预测触发的审核峰区点/可评估审核峰区点。模拟峰区接口不等于已有真实可信峰标签。
MAE=Σ|e|/M，RMSE=sqrt(Σe²/M)，M仅实际被遮蔽且估计有限的点；同时报Requested/Evaluated与Coverage，避免丢失败点提高精度。峰高/峰位在预先固定窗口每个受影响完整行的max和argmax比较，峰位单位nm，面积用实际lambda梯形积分（原强度含背景，未扣基线），不是未定义峰区的精确谱线面积。
局部形态误差采用涉及隐藏点的相邻波长边上的梯度RMSE：sqrt(mean[((e_(j+1)-e_j)/Δlambda)²])，单位原强度/nm；与点RMSE区分。峰指标不保证亚节点峰位精度。近零参考不默认MAPE。
削顶误差只在真实模拟截断mask上算，肩部另报MAE；下界违反=可评估截断位置估计<C的数量/对应可评估数量。C0保留观测不宣称恢复，C1为普通插值对照，C2投影确保约束但不证明真峰。V04_模拟功能测试结果.json的synthetic_metrics只用于测试，不是十炉性能或最终选型依据。

LOHO接口将外层test、内层validation和train列出，训练拟合仅train，参数选择仅内层validation，test标签不可选型。当前测试用10个sim对象检验集合不交。真实划分需兼顾两套网格并冻结，既有十炉EDA不能叫完全盲测。Q1炉内离线遮蔽可用两侧未隐藏观测，需与跨炉学参隔离；Q3另需实际可用时间和因果输入，两者不机械同分割。
实际命令：在已配置PYTHONPATH的独立依赖环境运行python APMCM_New/04_Q1光谱研究/代码/test_validation_modules.py。种子20261127，Python/numpy沿用S轮环境。成本实测见CSV；真实十炉成本只能粗估，未执行正式真实验证。
''')
selected=[]
for i,typ in enumerate('ABCDEFG'):
    h='6B03205' if i%2==0 else '6C02057';selected.append((B/f'REF-{h}-{typ}.png',f'V02 {typ}参考候选，Pending Review'))
old=P/'专项分析/S06_谱峰与异常反例研究'
for filename,reason in [('6C02057_E_完整平台肩部.png','915节点宽平台双肩'),('6B03206_F_局部证据.png','单点上限反例'),('6B03205_A_局部证据.png','持续候选谱峰'),('6B03205_H_低点局部放大.png','低值局部候选，不等于错误'),('6C02058_G_整谱变化.png','快速整谱变化候选')]:selected.append((old/filename,reason))
packet=['# Q1交叉审核精选图册与索引','\n先看以下12图，不复制旧图文件、不要求重读120图。所有参考区Pending Review，原120图证据保留。']
for i,(path,reason) in enumerate(selected,1):
    assert path.exists();rel=__import__('os').path.relpath(path,V).replace('\\','/');packet.append(f'\n## {i}. {reason}\n\n![{reason}]({rel})\n')
put(V/'Q1交叉审核精选图册.md','\n'.join(packet))
put(B/'V02_人工审核图册.md','''# 人工审核入口

本目录REF-6B03205-A至G和REF-6C02057-A至G为14张原值局部图，标题标Pending Review，局部色轴线性自动范围，无平滑/插值。为快速审核，优先读[12图精选索引](../Q1交叉审核精选图册.md)。全部70框坐标在登记表，非图中14框也未获认证。
每框需队员分别记录：原值是否可作为真值代理、削顶/候选/重复通道风险、是否同意通过/缩小/拒绝、理由、姓名日期及尚未解决分歧。本轮状态全部Pending Review。
''')
put(V/'V01_V04交叉审核摘要.md',f'''# V01–V04交叉审核摘要

主要计数和坐标独立复算一致，发现的解释修正见V01问题表：上限污染邻域、floor尺度、小样本MAD、非上限案例误用削顶分类、峰宽与极值案例偏差。旧结果保留，新报告不冒充双方确认。
V02共70框覆盖十炉两网格七类，均Pending Review，{risk}框上限邻域风险；不是可信真值清单。先看Q1交叉审核精选图册的12图，再核查对应坐标。
V03优先D0/D1/D2、R0、C0/C1，C2作为独立删失原型，R1待实现；D3/R2暂缓。为什么：先用便宜可解释方法暴露真峰误伤、块漏检与边界失败，而不是用复杂度掩盖未知真值。所有选型Pending。
V04独立模拟的{len(tests['checks'])}项功能测试通过；不能作为真实十炉性能。共同决定参考区通过条件、污染邻域处理、参数搜索范围、LOHO/炉内遮蔽目标、峰区面积定义及冻结后失败处理。配置JSON全部Pending、frozen=false、real_validation_allowed=false。
建议复算：V01关键表的每炉两个最高分位置（Excel行列写在Metric）、26对边缘通道、附件5原915平台及4/8组件守恒。模型接口与最大输入时刻继续遵守Q3信息边界。交叉审核由队友提交独立意见，Agent自审不代替双方确认。当前停止，未清洗/重构真实谱、未训练、未推送。
''')
put(V/'V01_V04运行说明.md','''# 本轮命令与复现顺序

在原研究工作区根目录，使用已有独立.analysis_deps（PYTHONPATH），MPLCONFIGDIR指向可写缓存，PYTHONIOENCODING=utf-8。
```
python APMCM_New/04_Q1光谱研究/代码/validation_preparation_audit.py --source-root .
python APMCM_New/04_Q1光谱研究/代码/test_validation_modules.py
python APMCM_New/04_Q1光谱研究/代码/write_validation_preparation.py
```
第一条只读原始十炉作复算和参考提案；第二条不读取任何真实工作簿；第三条从输出生成报告。既有S轮文件不覆盖。重复运行V阶段脚本会重建本轮草稿，应在版本化工作副本复现，不覆盖共同已发布成果。没有调用真实参考区注入或重构。
''')
print(json.dumps(dict(real_checks=len(checks),reference_proposals=len(refs),saturation_halo_risk=risk,prior_candidate_risk=candidate_risk,simulation_tests=len(tests['checks']),all_reference_status='Pending Review'),ensure_ascii=False,indent=2))
