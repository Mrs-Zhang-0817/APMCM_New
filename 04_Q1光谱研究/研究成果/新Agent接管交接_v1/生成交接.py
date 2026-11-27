"""Publish a single-repository handover; inspect frozen Git objects, no study run."""
from pathlib import Path
from datetime import datetime,timezone
import json,csv,io,subprocess,hashlib,re
O=Path(__file__).resolve().parent;R=O.parents[2]
Q1='025b3307f4fa6f98412ae2080a0c3bc883bc3900';Q2='059075dc9678d2aac73bd3b5be1888d3f7b06e78';MAIN='f7b919233182bbeb14734cd1fe6a8a922db79c11'
MODEL='61dc006987a7c7260998aabb8bcd13c826c4cd97'
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def sha(b):return hashlib.sha256(b).hexdigest()
def blob(c,p):return git('show',c+':'+p)
def text(c,p):return blob(c,p).decode('utf-8-sig')
def write(p,s):
    p=O/p;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='') as f:f.write(s)
def dump(p,x):write(p,json.dumps(x,ensure_ascii=False,indent=2))
def csvout(p,rows):
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);write(p,'\ufeff'+s.getvalue())
assert git('rev-parse','HEAD').decode().strip()==Q1
assert git('branch','--show-current').decode().strip()=='q1-spectral'
assert not git('diff','--name-only').strip()
tracked_before={p:sha((R/p).read_bytes()) for p in git('ls-files','-z').decode().split('\0') if p}
# Preserve and publish all 44 prior local-only research/audit files as labelled history.
archives=[]
folders=[R/'04_Q1光谱研究/实验验证/Q2独立交叉验收_v1',R/'04_Q1光谱研究/研究成果/工作区连接审计_v1',R/'04_Q1光谱研究/研究成果/双线同步与验收准备_v1']
redactions=[]
for root in (str(R),str(R).replace('\\','/'),str(R.parent),str(R.parent).replace('\\','/')):
    redactions.extend([root,json.dumps(root,ensure_ascii=False)[1:-1]])
for folder in folders:
    for p in sorted(folder.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        original=p.read_bytes();s=original.decode('utf-8-sig');changed=s
        for pattern in sorted(set(redactions),key=len,reverse=True):changed=changed.replace(pattern,'<本机项目目录>')
        # Public snapshot LF bytes; original local files are never rewritten.
        changed=changed.replace('\r\n','\n');dest='历史本机交付快照/'+folder.name+'/'+p.relative_to(folder).as_posix()
        write(dest,changed)
        archives.append(dict(Original_Relative_Path=p.relative_to(R).as_posix(),Published_Snapshot=O.relative_to(R).as_posix()+'/'+dest,Original_Bytes=len(original),Original_SHA256=sha(original),Snapshot_SHA256=sha(changed.encode('utf-8')),Absolute_Path_Redacted=changed!=s.replace('\r\n','\n'),Status='历史快照；不代表当前阶段；内层清单对应原文件，外层交接清单验证本快照'))
assert len(archives)==44
csvout('历史本机文件同步清单.csv',archives)
# Latest Q1-authored review was committed on the Q2 branch; copy exact key text, keep provenance.
cross=[]
for name in ('增量独立验收报告.txt','新增问题与答复表.csv'):
    path='04_Q1光谱研究/实验验证/Q2新增模型增量验收_v1/'+name;b=blob(Q2,path)
    p=O/'跨分支关键证据'/name;p.parent.mkdir(exist_ok=True)
    with p.open('xb') as f:f.write(b)
    cross.append(dict(Original_Commit=Q2,Original_Path=path,Snapshot='跨分支关键证据/'+name,SHA256=sha(b)))
csvout('跨分支证据来源.csv',cross)
P='04_Q1光谱研究/实验验证/R0点遮蔽审批准备_v1/'
cfg=json.loads(text(Q1,P+'config_pending.json'));manifest=json.loads(text(Q1,P+'reference_manifest_pending.json'));bindings=json.loads(text(Q1,P+'input_bindings.json'));r0checks=json.loads(text(Q1,P+'checks_and_hashes.json'))
def canonical(x):return sha(json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode())
assert canonical(cfg)==r0checks['config_sha256'] and canonical(manifest)==r0checks['reference_manifest_sha256']
assert cfg['real_data_execution_allowed'] is False and not cfg['approvers']
code_checks=[]
for name,digest in r0checks['code_sha256'].items():
    actual=sha(blob(Q1,'04_Q1光谱研究/代码/'+name));code_checks.append(dict(Path=name,Expected=digest,Actual=actual,Match=actual==digest));assert actual==digest
window_checks=[]
for b in bindings:
    rows=list(csv.DictReader(io.StringIO(text(Q1,P+b['reference_id']+'_raw_support.csv'))))
    ts=sorted(set(float(r['time_s']) for r in rows));ws=sorted(set(float(r['wavelength_nm']) for r in rows));values={(float(r['time_s']),float(r['wavelength_nm'])):float(r['raw_intensity']) for r in rows}
    payload=dict(values=[[values[(t,w)] for w in ws] for t in ts],time=ts,wavelength=ws)
    actual=canonical(payload);assert actual==b['window_sha256'];assert b['config_sha256']==canonical(cfg) and b['reference_manifest_sha256']==canonical(manifest)
    window_checks.append(dict(Reference_ID=b['reference_id'],Saved_Window_SHA256=actual,Match=True,Scope='保存支持窗与绑定一致，不代表本轮原始附件核验或真实遮蔽'))
Q2P='05_Q2供氧与烟气研究/研究成果/B-Q2-SIM-001_v01/'
q2configs={name:json.loads(text(Q2,Q2P+name)) for name in ('连续重构_冻结审批配置.json','延迟识别_冻结审批配置.json')}
q2filehash=[]
for name,c in q2configs.items():
    assert c['real_data_execution_allowed'] is False and c['approval_status']=='Pending'
    for module,digest in c['code_sha256'].items():
        actual=sha(blob(Q2,'05_Q2供氧与烟气研究/代码/'+module));assert actual==digest;q2filehash.append(dict(Path=module,Expected=digest,Actual=actual,Match=True))
    assert sha(blob(Q2,Q2P+'模拟结果.json'))==c['simulation_result_sha256']
dump('关键审批输入完整性核验.json',dict(task='J-HANDOVER-001',utc=datetime.now(timezone.utc).isoformat(),Q1=Q1,Q2=Q2,main=MAIN,R0_config_canonical=canonical(cfg),R0_manifest_canonical=canonical(manifest),R0_code_checks=code_checks,R0_saved_window_checks=window_checks,Q2_code_checks=q2filehash,Q2_configuration_raw_hashes={n:sha(blob(Q2,Q2P+n)) for n in q2configs},R0_status='Pending',Q2_status='Pending',real_experiments_run=False,synthetic_tests_rerun=False,original_workbooks_read=False))
# Inventory every tracked file across the three frozen branches. No raw data/cache is copied.
inventory=[]
for ref,commit in [('q1-spectral',Q1),('q2-gas-oxygen',Q2),('main',MAIN)]:
    for raw in git('ls-tree','-r','-l','-z',commit).split(b'\0'):
        if not raw:continue
        head,path=raw.split(b'\t',1);mode,kind,oid,size=head.decode().split()
        if kind!='blob':continue
        path=path.decode();inventory.append(dict(Branch=ref,Fixed_Commit=commit,Path=path,Bytes=int(size),Git_Blob_SHA1=oid,Note='同一仓库不同分支的版本；不要求所有文件出现在main或当前工作树'))
csvout('三分支受控文件目录.csv',inventory)
write('00_从这里接管.md',f'''# 新Agent接管入口

Task J-HANDOVER-001，2026-11-27。唯一共享仓库：https://github.com/Mrs-Zhang-0817/APMCM_New 。后续不得把Test或其他旧项目副本作为当前研究源；历史文档中的其他仓库链接仅解释当时证据出处，不要求取得它们。

先读本目录[01_资料同步与当前状态](01_资料同步与当前状态.md)、[02_工作SOP](02_工作SOP.md)、[03_缺失与补充](03_缺失资料与补充要求.md)、[04_任务表](04_任务与放行条件.csv)、[05_接管Prompt](05_新对话接管Prompt.md)。旧根README/共同进度尚未追上工作线，不能照其“专项未开始”否定已有成果；也不擅自覆盖共同文件。本入口是最新接管说明和证据索引，不是双方科学批准。

本次审计冻结的原研究版本：Q1 `{Q1}`；Q2 `{Q2}`；main `{MAIN}`。Q1整改旧基线346c64e继续保留；新增Q2模型实际在`{MODEL}`引入，不能只固定旧配置内的7652b32。后续交接发布提交会在原Q1版本之上增加本目录，原研究文件不变。

已将本机44份未跟踪交付保存为带来源SHA的历史快照；原始本机文件未覆盖。它们是此前连接/同步/旧Q2审核记录，不是当前状态。特别是旧Q2报告的“连续模型未实现”已被本仓库较新模型与增量验收取代。不要重做其95条/146条、不要重复十炉EDA。快照中的本机绝对目录已脱敏，内层旧清单适用于原件；快照用本目录外层交接SHA256清单验字节，勿运行快照内旧生成脚本。

Q1作者的最新Q2增量验收报告/答复表目前位于Q2分支的04目录。已把两份关键文件原字节复制在“跨分支关键证据”供单入口阅读，并保存固定源路径/哈希；完整算例代码/JSON在Q1分支已有。不应因为当前分支没有某报告而认定研究未做，也不要为阅读合并两条分支。

目前没有明确证据显示任何真实子实验已经获双方批准并执行。R0为1背景候选+4动态困难对照；Q2两项申请分别为观测重构压力试验与统计响应时移试运行。三项可分别批准，不互设无关前置条件。首要动作是资料审计、复述SOP、提出具体缺件，再按独立任务推进，不是直接清洗或训练。
''')
write('01_资料同步与当前状态.md',f'''# 资料同步审计与当前事实

唯一仓库APMCM_New。审计时本地Q1落后其远程2提交，无本地独有提交、无受控修改；44个未跟踪文件与33个入站路径无冲突。已仅快进同一Q1分支至025b330，未创建合并提交、未合并Q2/main、未改其他分支头。历史本机44文件原件保留，在本包另有公开历史快照；本次将仅发布Q1交接提交。

|成果|实际位置/固定版本|状态与限制|
|---|---|---|
|共同十炉EDA、整体审查、18条标准v2|03_共同数据分析、02_统一研究规范|已有；无需重复；根进度文字滞后|
|Q1 S01–S07、V01–V04、70区与13项整改|q1-spectral：04目录；旧346c64e|已存在；61/12/62为相应历史合成检查，不是当前真实处理性能|
|Unknown三态接口|q1：代码/detection_metrics_v3.py、test_detection_metrics_v3.py；研究成果/全局评估_20261127/Q1三态评价修复与R0放行条件.txt|已修复、10项针对性检查有记录；评价未知不计正常，不能继续说接口未找到|
|R0首批审批准备|q1：实验验证/R0点遮蔽审批准备_v1，代码/r0_preparation.py等|已补5区支持窗、限定跨度、输入绑定；10+5=15项方法检查有记录，5个保存支持窗绑定本轮复核通过；未做真实遮蔽|
|Q2对346c64e独立验收|q2：05目录/交叉审核/CR-A-Q1-346c64e-v03最终验收|5 Verified Fixed、8 Partially Fixed；不代表已审最新R0包或三态v3|
|Q2连续/延迟候选及模拟|q2：代码/q2_continuous.py、q2_delay.py、q2_synthetic.py；研究成果/B-Q2-SIM-001_v01|66项合成检查记录；实际模型已实现，不再列为未实现；未验证真实物理精度|
|Q1对新增Q2模型增量审核|q2：04目录/实验验证/Q2新增模型增量验收_v1/增量独立验收报告.txt、问题表；代码/JSON在q1|15组新针对性独立算例有记录；意见A=可提交有限实验审批，不是已批准|
|Q1 R0与Q2两申请|R0 config_pending.json；Q2连续/延迟冻结审批配置|三个执行开关均false，批准为空/Pending；不能称已冻结批准版|

R0确切约定：REF-6B03205-F、REF-6B03206-F、REF-6B03271-F、REF-6C02058-F、REF-6C02107-A；每核心7×17=119点、支持窗15×25=375点。前四为动态困难对照，最后一个B网格低变化背景候选；跨A/B网格不等于跨两网格都具有平稳背景真值。保存窗无65535不能认证无误差。种子20261127/28/29，每区k=1/2嵌套遮蔽，两顺序共用位置；最大双侧总跨度1秒/1.6nm，禁外推，二次估计源单列。60结果行，90次恢复请求不是90独立原点。覆盖门槛提案100%，本次不设已验证的物理准确性通过阈值，误差作基线报告。

R0配置规范内容摘要：`{canonical(cfg)}`；参考清单规范内容摘要：`{canonical(manifest)}`。代码/原始附件为原字节SHA；JSON配置/清单和窗口使用代码digest规范摘要，不能混用文件排版字节SHA。

Q2连续模型：O为单调C1分段三次，q=O′为非负C0分段二次Bernstein；气体为非负C0线性段，其积分C1。保持反例说明守恒不等于瞬时正确。延迟输出identified仅为统计规则接受的时移，不是物理运输已辨识。已知真值模拟中高供氧较短延迟是人为设定，不能作为真实关系结论。

Q2连续申请B-Q2-REAL-REC-001：附件5 372–380秒、附件8 0–46秒，单点观测压力测试。延迟申请B-Q2-REAL-LAG-001：附件5 97–194秒、附件8 171.5–343秒，统计响应时移探索；两窗不同炉，不能拟合τ(q)。两申请可分别签署。配置source_branch_commit=7652b32过旧：批准时必须连同增量报告锁定61dc006或当前059075d及完整依赖，后者只补审核文件。延迟间接依赖q2_continuous.samples，不能只验q2_delay。

本轮仅做Git/文件与保存支持窗完整性审计，未重新执行10/15/66项检查、未打开XLSB、未实施真实遮蔽或任何训练。旧报告中的“未提交/未推送”等是生成时状态；判断发布以Git固定对象与本包索引为准。
''')
write('02_工作SOP.md','''# 两人共同项目工作SOP：接管后依门槛推进

这份SOP恢复已有流程，不替用户选择未讨论的最终算法。优先级：最新用户授权＞有效共同标准/实际双方决定＞按固定版本核验的当前成果＞旧阶段描述。若新证据要求改流程，先记录差异、依据和最小变更提案，不默默改阈值或追认批准。

## 0. 新对话先接管审计，不能直接跑实验

确认绝对目录、真实.git或合法worktree指针、rev-parse、唯一origin、当前分支、状态、三条分支完整SHA；fetch读取，禁止强推、重置和自动合并。先保护本地改动。没有现有仓库则要求用户指定，不自动创建第二项目。只在APMCM_New中定位，main没有某文件时继续查q1/q2固定对象，不去Test找当前成果。

依次读README、AGENTS、00主文档/进度/SOP/共同决定、02标准v2/双Agent/Git规范、本交接入口、Q1最新R0包及v3、Q2新增模块/模拟/配置、最新双方增量审核。返回：版本表、资料完整/缺失/不一致清单、当前阶段、已完成/未完成及下一步最小任务。不得因为旧进度滞后重做十炉EDA，不按文件数量或单一百分比宣称论文完成度。

先向用户一次性提出具体缺件：文件/版本/用途/缺失影响/最小补件方式。证据不足保留Pending；可以继续不依赖缺件的静态审核、合成检查和执行器准备，不得编造缺失结果。尤其要确认原始附件合法本地位置、修正版附件1、最新R0对方独立意见和真实两人签署；详见03。审核已有结果不等于重新执行结果。

## 1. 只完成影响小实验的增量闭环

Q2身份审核最新R0-point-pilot-v1-review和三态v3接口差异：复用10项与新增5项记录，必要时只补针对新增风险的独立合成反例，不重复61/62/十炉EDA。核对5窗、用途、最大跨度、禁外推、二次估计、实际源/坐标/值/配置/清单/代码绑定及Unknown分母；给明确已解决/待补和独立证据。现有v03只审346c64e，不能冒称本包已被对方验收。

Q1身份接收已存在的Q2连续/延迟增量审核与作者答复，只处理source_branch_commit、间接依赖和执行侧0.5秒网格/窗口校验等最小来源缺口。不把当前已实现模型再说成仅设计；不重跑全部66项。不把R1/C2、所有70区或事件物理机理作为这两窗条件探索前置。

接管Agent可按本次移交承担Q1剩余实现并衔接Q2任务，但要保留分支/角色和作者来源。一个Agent自行写代码后自测不能冒充独立审核；如其曾参与待审实现，要披露并请求另一未参与审核者/队员复核。已有独立审核者的证据可复用，不能代写其答复或签字。

## 2. 三个子实验分别准备和申请

|子实验|已经备妥的输入|批准范围|本阶段不得附加的前置|
|---|---|---|---|
|Q1 R0点遮蔽|最新5窗、待审配置/参考清单、输入绑定、两序限跨度代码|1背景+4动态的原记录条件恢复基准；可选缩减但必须重建配置/绑定|D1/D2真实检测、R1实现、C2收敛、全70区认证|
|Q2连续观测重构|B-Q2-REAL-REC-001及增量来源附录|附件5/8指定两窗、逐变量单点压力测试，q真实误差仍未知|真实物理延迟、Q1所有实验完成|
|Q2统计时移试运行|B-Q2-REAL-LAG-001及完整模块依赖|指定两窗、主difference与冻结敏感性/拒答诊断|证明物理因果、拟合τ(q)、Q3训练|

两名队员确认确切ID/窗口/用途、配置及清单/代码摘要、覆盖/失败和允许动作，记录姓名/批准号/日期；Agent不代签。使用Pending文件准备，不在原文件直接改成已批准，产生新的签署版并保留旧版。来源JSON摘要口径与代码一致。批准一个子实验不放行另两个。

## 3. 获该具体批准后，先有限真实验证

先实现或核查对应真实runner：源文件只读；按清单校验附件/源SHA、实际Sequence和原波长/0.5秒网格；load_window后验证实际值/坐标与所有绑定，再在副本上生成已批准掩码。原目标值仅送评价端，不能参与补点支持/调参。依赖代码与配置版本变动则新版本重审；不得用保存CSV偷偷替代原源核验，除非双方另外批准以导出窗为输入的独立协议。

R0严格执行3种子×k1/2×两序，同位置，核心请求总量和恢复覆盖全报；未解值NA并保留失败位置，不事后扩跨度。背景/动态分别报告请求、恢复、覆盖、MAE/RMSE/p95/max、估计源和两序差。没有物理误差容限就报告探索误差，不宣称准确性验收通过。零掩码、空分母、NaN不作正常或零误差。检测注入另行申请，不混入R0。

Q2连续试验只评原记录代理恢复与模型不变量，不能用累计氧遮蔽得分代替真实q精度；同模型积分一致只是构造性质。延迟必须保留主诊断null、边界/激励不足/歧义和敏感性分歧；不能挑敏感性成功值替主诊断，不要求得到期望正延迟。完成各自有限试验就交独立复核，不自动扩到全炉。

## 4. 小试复核后，共同设计正式预处理并验证

冻结按用途的异常分类、保留/掩码/处理规则；检测与连续重构分别评价。少量条件性点基准不足以证明尖峰、成片异常、整行缺失或真实65535恢复能力；需要处理哪类再为哪类补经批准的注入/随机及结构遮蔽/人工削顶及峰保护压力。疑似与确认问题分别存，不因统计极端删值；零/持值/真实变化保留竞争解释。R1仅在R0暴露具体收益缺口时评估；C2无量程/收敛/先验敏感性与可辨识证据时保持C0信息，不强造未知峰顶。

按炉隔离训练侧参数拟合、验证侧选型、测试侧冻结评估；两网格不按同列直接融合，不用测试炉真值选区/选阈值。已有全十炉EDA必须披露，不能称盲测。实验证据和独立复核后，由两人批准正式处理方案，才能执行全十炉正式预处理；原值、标签、清洗值、重建值分别保存，历史永不覆盖。

## 5. 完成正式Q1与Q2连续交付

Q1：在验证支持的方法范围内构建每炉实际(t,λ)上的I(t,λ)连续表示，明确C0/C1、节点/边界/无支撑区域、峰保护和不确定性，完成十炉连续三维光谱图。原始结构图不能替代连续重构图；补点矩阵也不能冒充完整二维函数。

Q2：完成每炉q(t)、O(t)、CO2/CO流率及两累计排放六类连续曲线；区分构造守恒和真实流率精度。研究累计氧与烟气瞬时/累计关系、按供氧区间的统计响应时移及可辨识/不可辨识情况；物理运输解释、τ(q)和工况比较仅在证据充分时提出。不能为迎合题意硬拟合“供氧高必延迟短”。

每项保存源/配置/代码/输出哈希、实际运行入口、逐炉误差分布/覆盖/失败及独立审核，不用合成通过替代真实性能。

## 6. Q3在单独目标与实时门槛后开展

两人先选预测探头当前/未来读数还是炉内状态代理，冻结预测时刻与标签时刻；区分物理、仪器记录、到达和处理完成/available_time。特征仅允许available_time≤预测时刻；离线双向重构、全炉统计、测试炉未来气体和用测试标签选延迟不能直接成为实时输入。延迟标签可离线作监督目标，不得反向进入实时输入。

在训练炉内选择物理波长区间/因果特征、网格组合和候选模型，按炉验证泛化；最终模型由证据决定，不在SOP中预指定。报告十炉逐炉/按网格与工况的预测误差、宏/微汇总、失败炉和少炉外推限制。若没有真实available_time证据，只能限定为离线代理研究，不能宣称实时部署已验收。

## 7. 论文与整合

唯一整合人维护共同入口、决定和变更日志；分线成果通过PR审核、具体科学结论由两队员确认，未经授权不合并main。整合题意覆盖矩阵、数学定义、可复现结果、局限与图表，核对“已实现/合成支持/真实验证/共同批准”四种事实，不以文件数量替代研究完成度。最终题意与格式须由合法官方PDF复核，仓库没有PDF时请求补充。

所有后续步骤以实际证据及具体授权为门槛，可继续独立准备但不可越级。发现新问题只补影响该子实验的最小证据，避免把项目重新拖回泛化EDA或无限审核。
''')
write('03_缺失资料与补充要求.md','''# 需要新Agent首先核对并向用户提出的资料

这是一份待核验清单，不假装已拿到接收方机器上的文件。仅有Git仓库时，不会自动拥有原始附件、Python环境或真实签署。先查同一仓库全部相关固定分支，再把确实缺少的内容一次列出。

|项|当前证据/缺口|请用户最少补什么|缺失时可继续/不可继续|
|---|---|---|---|
|原始XLSB与附件1修正版|仓库故意不含完整XLSB；只有哈希清单与5个支持窗导出|合法原文件在接收电脑的绝对目录，或约定合法传递方式；核对01数据结构清单SHA，附件1必须中文修正版|可做静态/合成与保存窗完整性核验；不得冒称源核验通过或运行真实输入实验|
|原始文件具体集合|R0涉及附件1/2/4/6/9，Q2两申请涉及5/8；正式十炉任务最终需1–10|先提供拟执行子实验需要的最小集合；不要要求为了一个窗口先传所有资料|按依赖分开，缺R0源不必阻塞Q2独立合成|
|官方题目PDF/完整题意|仓库主文档有摘要，原官方PDF未入库|论文/最终题意复核前给合法本地PDF或官方题目全文，不传无关资料|可推进已有明确任务；不能假装已独立核对原题全部细则|
|最新R0独立意见|Q2 v03只审346c64e；当前未定位到针对R0配置f29544…及v3新增接口的独立复核闭环|若已由其他对话完成，给APMCM_New分支/完整SHA/路径；若未做，由未参与实现的Q2审核者按最小增量执行|可准备，不能伪造已审/已答复；无需重审70区或R1/C2|
|三个真实子实验的批准|R0与Q2两配置均Pending、执行开关false，未发现两人真实签署|每项明确窗口/用途/允许动作、签署两人身份/批准号/日期及配置清单代码摘要；如已有批准请给原记录|不能以“同意推进/同步仓库”替代具体真实执行授权|
|Q2配置来源修正或附录确认|source_branch_commit仍为7652b32，模型在61dc006；延迟依赖q2_continuous|作者回复/来源附录连同实际新代码固定版本一起批准；可新版本配置，不重做模型|可复用已有独立算例；真实执行不可只验旧SHA或单个直接模块|
|接管职责与独立性|新Agent承接本次Q1移交并衔接队友Q2，但人员姓名/唯一整合人未写实|确认队员A/B是谁、谁审批、谁整合；Agent曾参与哪些实现如实披露|可技术准备；不得一人/同一作者自审冒充双人独立闭环|
|环境与运行入口|仓库requirements是旧直接依赖，接收机没有.analysis_deps属正常；保存结果标Python3.12.14/NumPy2.5.5等|Agent先按源码核实依赖和可用环境；只有安装/运行确实受阻才向用户提供最小需求|不能用缺本机缓存断言研究缺失，也不把安装环境当研究结果|
|Q3设备时钟/目标/标签|记录Sequence有定义，可用时间/绝对时钟与真实τ尚缺|后续Q3前补采集/到达/处理日志、目标定义和可用工艺旁证；没有就限定研究主张|不阻塞离线R0/Q2有限小试；阻断实时部署验收与无依据物理延迟声明|

建议向用户提问格式：缺件编号；预期仓库路径/版本；已经查过哪些分支；为什么影响当前子任务；最小补件（路径/提交/具体记录）；不依赖它仍可做的事。不要笼统要求“上传全部资料”，不要从旧聊天猜正文，不自行重新编造模拟或审核。

本机历史44份交付已入本包公开历史快照，仅绝对根目录脱敏并统一LF，原件及原SHA清单留存。当前研究代码/图/支持窗仍在正式工作线目录；没有第二个当前项目或另一活动仓库。
''')
tasks=[('H00','接收Agent','身份/三分支/文件与哈希接管审计','本入口、目录、关键核验JSON','首次回复给完整/缺失/不一致表，复述当前阶段','可立即只读','不需要真实数据即可核对Git材料'),('H01','未参与实现的Q2审核者','R0/v3新增接口最小独立复核','025b330内R0包、v3接口、10+5记录','针对f29544配置出具意见及问题答复','Pending','不是346c64e旧审核，不重跑全历史'),('H02','Q2作者/Q1审核者','Q2增量来源及依赖闭环','059075d增量审核、61dc006模型','修正或以附录固定代码与samples依赖','Pending','不重做66项或重复事件EDA'),('H03','两名队员','分别批准R0、REC、LAG','三个具体配置及用途','两人实签、允许动作、固定摘要','Pending','互不以无关模型为前置'),('H04','对应工作线Agent','获批子实验真实runner与有限执行','合法源、具体批准、实际值/坐标/代码绑定','仅获批窗口与动作，合成接线检查后报告失败','Blocked until corresponding approval','保存原始数据，只在副本操作'),('H05','对方审核者/两队员','小试审阅与正式处理方案','分层误差/覆盖/失败和证据','方法及处理范围另获共同确认','Not Started','不因小试完成自动全炉清洗'),('H06','Q1/Q2','正式预处理及连续模型全十炉交付','经验证已批准方案','Q1连续I(t,λ)与10炉3D；Q2六类连续曲线','Not Started','每炉真实坐标，保留原值/掩码/不确定性'),('H07','两队员/Q3执行者','Q3因果接口与按炉预测','目标/可用时间/训练侧参数来源','独立按炉评估及泄漏审计','Not Started','当前无训练授权，具体模型未选'),('H08','指定整合人','共同文档、论文与main整合','稳定交付/PR/真实决定','明确整合人与版本；原题格式复核','Pending','不自动合并main')]
csvout('04_任务与放行条件.csv',[dict(Task_ID=i,负责人=owner,任务=n,输入=inputs,验收=criteria,当前状态=state,限制=limit) for i,owner,n,inputs,criteria,state,limit in tasks])
prompt='''你现在接管APMCM B题两人项目。唯一活动仓库为 https://github.com/Mrs-Zhang-0817/APMCM_New ，不使用Test或其他副本作为当前源，也不新建第二份项目。请先在q1-spectral中读 `04_Q1光谱研究/研究成果/新Agent接管交接_v1/00_从这里接管.md`，再依入口完整读取资料审计、SOP、缺件清单、任务表及固定分支材料。

先完成只读接管：检查实际目录/.git/origin/分支/状态，fetch后记录q1-spectral、q2-gas-oxygen、main完整SHA；保护本地改动，不强推/重置/自动合并。main或当前工作树没有文件时查同一仓库其他固定分支，不能据此断言研究没做。核对关键配置/代码/支持窗哈希，逐项判断资料完整、缺失和相互不一致；向我一次提出具体文件路径或提交/批准记录需求，说明影响和仍可独立推进的事项。不要从旧对话或文件名猜内容、补造缺失结果。

首次回复必须给：实际版本表、缺件表、已完成/未完成的证据状态、对既定SOP的复述、下一步最小任务和相应放行门槛。接收方只有Git仓库，不应假设已拥有完整原始XLSB、修正版附件1、官方PDF、本机依赖或两名队员签署；源数据需要先按清单核验。资料足够的静态/合成准备可继续，依赖缺件或具体审批的动作等待补充。

当前事实：Q1已有S01–S07/V01–V04/70区/13项整改；Unknown三态v3及10项检查已完成，R0最新包新增5项检查和5窗补证/跨度/绑定。R0是1背景候选+4动态困难对照，不是5个正常真值。Q2已实现连续模型与时移模块，有66项作者合成记录和15组针对性独立增量算例；旧“未实现”报告是历史。Q2 v03只审346c64e，不自动覆盖最新R0包；当前缺针对R0配置f29544…的明确独立意见。Q2增量完整报告在q2分支的04目录，入口有原字节快照与来源。旧本机44份交付仅为历史快照，不能继续用其旧阶段结论否定新材料。

按SOP接续本次移交的Q1剩余技术工作并衔接Q2，不擅改两队员职责和共同规范；曾参与实现者不能把自测称作独立审核。首要工作为R0/v3最小独立复核、Q2来源/依赖最小闭环，以及三个子实验分别提交两队员审批。R0点遮蔽不以D1/D2真实检测、R1实现、C2收敛、全部70区或真实τ机理为前提。Q2连续小试和时移小试也可独立放行，不能把统计identified解释成物理运输已证实。

真实执行只在我提供相应两人具体批准后进行：锁定确切窗口/用途、配置/清单/源及代码/间接依赖摘要、覆盖和失败处理、允许动作；先装载原值并绑定实际值和坐标，在副本遮蔽，原目标只用于评价。不得因“交接/推进项目”自动批准参考或开启开关，不事后扩支持窗、挑最好顺序/诊断或隐去失败。检测注入另行申请。

之后依顺序：有限验证及交叉复核→共同正式预处理方案与验证→获批全十炉正式处理→Q1二维连续光谱及十炉3D、Q2六类连续曲线与有证据的分工况关系/时移→Q3目标/时间/因果特征和按炉验证→论文及指定整合人合并。未讨论的最终算法/阈值由实际证据提出方案，不把SOP当已选型。原始数据只读、历史不覆盖、疑似不当确认、两网格不按列硬融合、检测/重构分开评价、合成/真实/共同批准分开记录。

你可以判断并提出更优的最小执行细节；若要改已约定流程或扩大范围，明确新证据、变更理由与受影响门槛，提交我和队友确认，不默默偏离。每轮交付保存Task ID、源/代码/配置/输出哈希、实际执行与未执行范围、局限和待决事项。不要重复十炉EDA、已有统计图或无关历史测试。'''
write('05_新对话接管Prompt.md',prompt)
assert all(sha((R/p).read_bytes())==s for p,s in tracked_before.items())
for row in archives:
    assert sha((R/row['Original_Relative_Path']).read_bytes())==row['Original_SHA256']
dump('交接审计验收.json',dict(task='J-HANDOVER-001',base_q1=Q1,fixed_q2=Q2,fixed_main=MAIN,single_active_repository='Mrs-Zhang-0817/APMCM_New',historical_local_files_archived=44,original_local_files_unchanged=True,existing_tracked_files_unchanged=len(tracked_before),all_config_code_saved_window_checks_pass=True,original_XLSB_included=False,original_PDF_included=False,study_or_test_rerun=False,real_masking_executed=False,approvals='Pending',repository_file_inventory_rows=len(inventory),snapshots_do_not_rewrite_history=True))
files=sorted(p for p in O.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
write('交接文件SHA256.txt','\n'.join(sha(p.read_bytes())+'  '+p.relative_to(O).as_posix() for p in files)+'\n')
print(json.dumps(dict(directory=O.relative_to(R).as_posix(),files=len(files)+1,local_history_archived=len(archives),branch_inventory=len(inventory),R0_config=canonical(cfg),original_files_unchanged=True),ensure_ascii=False))
