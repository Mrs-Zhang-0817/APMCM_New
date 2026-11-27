"""Preflight and fixed-version handover only. No push/merge or study execution."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import subprocess,json,csv,io,hashlib,re,sys
O=Path(__file__).resolve().parent;R=O.parents[2]
Q1='346c64ebe864e7f09fa2de227e7b72709fbb8670'
OLD='3172d088feb9da0fed3a784e5071fcb9905b6a9e'
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def text(*a):return git(*a).decode('utf-8').strip()
def sha(b):return hashlib.sha256(b).hexdigest()
def write(name,s):
    with (O/name).open('x',encoding='utf-8',newline='') as f:f.write(s)
def dump(name,x):write(name,json.dumps(x,ensure_ascii=False,indent=2))
def csvout(name,rows):
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);write(name,'\ufeff'+s.getvalue())
def refs():return {h:text('rev-parse','origin/'+h) for h in ('q1-spectral','q2-gas-oxygen','main')}
def diff(a,b):return text('-c','core.quotepath=false','diff','--no-renames','--name-status',a,b)
def relation(a,b):return list(map(int,text('rev-list','--left-right','--count',a+'...'+b).split()))
assert (R/'.git').is_dir() and text('remote','get-url','origin')=='https://github.com/Mrs-Zhang-0817/APMCM_New.git'
assert text('branch','--show-current')=='q1-spectral' and text('rev-parse','q1-spectral')==Q1
if sys.argv[1]=='preflight':
    heads=refs();assert heads['q1-spectral']==OLD
    assert relation('q1-spectral','origin/q1-spectral')==[1,0]
    assert not text('diff','--name-only') and not text('diff','--cached','--name-only')
    localheads={h:text('rev-parse',h) for h in ('q1-spectral','q2-gas-oxygen','main')}
    commits=text('log','--format=%H',OLD+'..'+Q1).splitlines();assert commits==[Q1]
    names=text('-c','core.quotepath=false','diff-tree','--no-commit-id','--name-status','-r',Q1).splitlines()
    assert len(names)==27 and all(s.startswith('A\t04_Q1光谱研究/') for s in names)
    inspected=[];alerts=[]
    secret=re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{24,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|(?im:^\s*(?:password|api_key|access_token|client_secret)\s*[:=]\s*[\"\x27][^\"\x27]{8,})')
    for s in names:
        path=s.split('\t',1)[1];p=Path(path)
        assert p.suffix.lower() in ('.md','.csv','.json','.py')
        assert not any(part.lower() in ('.aws','.ssh','.env','credentials') for part in p.parts)
        b=git('show',Q1+':'+path);content=b.decode('utf-8-sig')
        if secret.search(content) or re.search(r'[A-Za-z]:[\\/]',content):alerts.append(path)
        inspected.append(dict(Path=path,Bytes=len(b),SHA256=sha(b),Text_Type=p.suffix,Raw_Workbook_Or_PDF=False))
    assert not alerts,alerts
    manifest='04_Q1光谱研究/实验验证/交叉审核整改_v2/版本变更与SHA256清单.csv'
    rows=list(csv.DictReader(io.StringIO(git('show',Q1+':'+manifest).decode('utf-8-sig'))))
    assert len(rows)==25 and all(sha(git('show',Q1+':'+r['File']))==r['SHA256'] for r in rows)
    assert relation('q2-gas-oxygen','origin/q2-gas-oxygen')==[0,2]
    q2commits=text('rev-list','--reverse','q2-gas-oxygen..origin/q2-gas-oxygen').splitlines()
    q2diffs=[]
    for c in q2commits:
        d=diff(c+'^',c);q2diffs.append(dict(SHA=c,Subject=text('show','-s','--format=%s',c),Files=d.splitlines(),Counts=dict(Counter(x.split('\t')[0] for x in d.splitlines()))))
    # Inspect the actual fixed progress/design and source implementation without running it.
    evidence={}
    for p in ('Q2当前研究进度.md','专项分析/S07_候选方法与验证.md','代码/q2_run.py','代码/q2_load.py'):
        b=git('show',heads['q2-gas-oxygen']+':05_Q2供氧与烟气研究/'+p);evidence[p]=dict(SHA256=sha(b),Bytes=len(b));b.decode('utf-8')
    assert '尚未开始' in git('show',heads['q2-gas-oxygen']+':05_Q2供氧与烟气研究/Q2当前研究进度.md').decode()
    pre=dict(task='A-Q1-SYNC-001',utc=datetime.now(timezone.utc).isoformat(),root=str(R),local_heads=localheads,remote_heads_before=heads,push_commits=commits,push_files=inspected,sensitive_pattern_alerts=alerts,scan_limit='文本类型、原始附件扩展名、常见凭据模式和本地绝对路径检查；不等同通用保密审计',manifest25_match=True,tracked_clean=True,untracked_status=text('status','--porcelain=v1'),q2_commits=q2diffs,q2_evidence=evidence)
    dump('推送前检查与Q2差异证据.json',pre)
    csvout('待推送27项文件及SHA256.csv',inspected)
    sections=[]
    for c in q2diffs:sections.append('## '+c['SHA']+'\n\n'+c['Subject']+'\n\n变更计数：'+str(c['Counts'])+'\n\n```text\n'+'\n'.join(c['Files'])+'\n```\n')
    write('Q2远程最新提交差异报告.md',f'''# Q2远程最新提交差异报告

Task A-Q1-SYNC-001。已fetch读取远程，未移动本地Q2分支、未重置或合并。检查时本地Q2为`{localheads['q2-gas-oxygen']}`，远程固定为`{heads['q2-gas-oxygen']}`；本地独有0、远程独有2。工作区仅有已知Q1审计/本轮交付目录的未跟踪文件，无受控未提交修改；这些文件未加入任何推送。

{''.join(sections)}

## 内容判断与验收范围

第一个提交迁入68个新增文件，覆盖Q2十炉S01–S07、统计/事件/积分/探索滞后结果、代码和三炉运行检查；不涉及本轮新运行。第二个提交仅新增6份Q2→Q1旧基线3172d08的独立审核材料，未修改专项算法。两提交累计74新增、0修改、0删除。

已实际读取Q2进度、S07候选设计、q2_run.py和q2_load.py。q2_run实现只读数据统计、常量/零段、事件窗、离散累计积分与滞后扫描；不是连续重构或独立模拟验证模块。S07明确注入/遮蔽/拟合尚未执行，进度明确连续模型未开始。本次固定远程树未见新的连续模型/模拟验收交付，不能推断队友机器不存在未上传工作。连续候选定义已存在，但实现与验收必须另核实。

下一轮重点：附件5 Excel753→754（375.5→376s）三变量事件及109.82m³/s差商解释；附件8 CO/CO2内部零段及点数/跨度；累计氧、流率、气体C0/C1/非负性；三种离散积分的窗口/端点；滞后符号、边界峰、负相关及运输机制不确定性。当前仅准备任务，不重算原始附件或运行模型。
''')
    print(json.dumps(dict(preflight='PASS',push_files=len(inspected),sensitive_alerts=alerts,q2_new_commits=[c['SHA'] for c in q2diffs],q2_report_written=True),ensure_ascii=False))
elif sys.argv[1]=='finish':
    pre=json.loads((O/'推送前检查与Q2差异证据.json').read_text(encoding='utf-8'));heads=refs()
    remote=text('-c','http.proxy=','ls-remote','origin','refs/heads/q1-spectral','refs/heads/q2-gas-oxygen','refs/heads/main')
    actual={line.split()[1].split('/')[-1]:line.split()[0] for line in remote.splitlines()}
    assert heads==actual and heads['q1-spectral']==Q1
    assert heads['q2-gas-oxygen']==pre['remote_heads_before']['q2-gas-oxygen'] and heads['main']==pre['remote_heads_before']['main']
    assert all(text('rev-parse',h)==s for h,s in pre['local_heads'].items())
    assert relation('q1-spectral','origin/q1-spectral')==[0,0]
    comparisons=[]
    for a,b in [('main','q1-spectral'),('main','q2-gas-oxygen'),('q1-spectral','q2-gas-oxygen')]:
        lines=diff(heads[a],heads[b]).splitlines()
        for line in lines:
            parts=line.split('\t');comparisons.append(dict(From_Branch=a,From_SHA=heads[a],To_Branch=b,To_SHA=heads[b],Status=parts[0],Path=parts[1],Meaning='方向为From树到To树；不是双方合并提案'))
    csvout('三分支逐文件差异.csv',comparisons)
    write('Q1推送与远程核验报告.md',f'''# Q1推送与远程核验报告

Task A-Q1-SYNC-001。推送前已fetch，Q1本地领先1/落后0；唯一待推送提交为`{Q1}`。前远端`{pre['remote_heads_before']['q1-spectral']}`为该提交父版本，未发现远程独有提交。origin为指定Mrs-Zhang-0817/APMCM_New，工作分支q1-spectral。

实际检查27个新增文件，均为Q1目录内的.md/.csv/.json/.py。25项原清单SHA256复核匹配；无XLSB、PDF、原始矩阵或凭据文件，常见凭据/私钥/本地绝对路径文本检查无命中。此为定向发布检查，不代表对一切未知敏感信息的绝对保证。文件及哈希见待推送27项文件及SHA256.csv。

工作区受控文件及暂存区无修改；上一轮连接审计目录和本轮交付目录为已知未跟踪产物。未暂存、未提交或打包这些文件，不影响仅推送既有提交。未删除或覆盖这些审计资料。

执行普通推送`git push origin q1-spectral:refs/heads/q1-spectral`，成功后重新fetch，并以ls-remote再次核验：远程q1-spectral=`{heads['q1-spectral']}`，本地/远程差异0/0。未使用force或修改其他分支。Q2与main远端完整SHA前后均未改变；本地三条分支头也保持不变。

整改浏览入口：[固定版本整改总报告](https://github.com/Mrs-Zhang-0817/APMCM_New/blob/{Q1}/04_Q1光谱研究/实验验证/交叉审核整改_v2/Q1_整改总报告.md)。原报告中的“未推送”是该报告生成时的历史状态，本次同步以本报告为准，不覆盖旧报告。

推送成功仅表示交接版本可取，不等于Q2独立复验通过或双方批准参考区域。本轮未跑研究/模拟测试、清洗、拟合、训练或分支合并。本轮5项交付保存在本地新目录，未包含于此次仅346c64e的推送。
''')
    summaries=[]
    for a,b in [('main','q1-spectral'),('main','q2-gas-oxygen'),('q1-spectral','q2-gas-oxygen')]:
        rows=[e for e in comparisons if e['From_Branch']==a and e['To_Branch']==b];summaries.append(f"|{a} → {b}|{dict(Counter(e['Status'] for e in rows))}|{relation(heads[a],heads[b])}|")
    write('双线固定版本清单.md',f'''# 双线固定交叉验收版本

Task A-Q1-SYNC-001；固定时刻UTC {datetime.now(timezone.utc).isoformat()}。远端fetch与ls-remote一致；后续审核引用完整SHA，避免活动分支更新造成漂移。

|分支|固定远程完整SHA|本地关系|
|---|---|---|
|q1-spectral|`{heads['q1-spectral']}`|本地相同，0/0|
|q2-gas-oxygen|`{heads['q2-gas-oxygen']}`|本地仍落后2，未移动本地分支|
|main|`{heads['main']}`|本地仍落后2，未合并|

|比较方向|逐文件变更状态计数|前者独有/后者独有提交数|
|---|---|---|
{chr(10).join(summaries)}

三组逐文件差异见三分支逐文件差异.csv，A/M/D均指前者树转为后者树，不代表建议删除或合并。各分支共享基线不等于最新main已合入研究分支。

Q1固定入口：`04_Q1光谱研究/实验验证/交叉审核整改_v2/`与`04_Q1光谱研究/代码/validation_modules_v2.py`、`test_validation_v2.py`。Q2固定入口：`05_Q2供氧与烟气研究/`，专项结果`研究成果/S01-S07/`，旧基线审核`交叉审核/CR-A-Q1-3172d08-v01/`。

当前Q1工作树不会因fetch自动出现完整Q2目录；可直接读取固定提交对象，或后续在隔离目录导出特定成果，禁止为阅读直接合并分支。本轮未新建第二仓库或额外分支。
''')
    write('双方最终交叉验收任务书.md',f'''# 双方独立交叉验收任务书（待下一轮执行）

Task A-Q1-SYNC-001。当前仅固定输入与任务，不代表已开展验收。双方共同审批全部Pending，不以模拟通过替代真实验证。本轮到交付后停止。

## A线Q1负责人：审核固定Q2

固定Q2=`{heads['q2-gas-oxygen']}`。从Q2总报告、当前进度、S01–S07、实际来源、局部原值、描述关系、探索滞后曲线和两份代码读取。先复核正式库与旧Test b35ac738审核的版本关系，复用`04_Q1光谱研究/实验验证/队友成果综合审核/`中已有146条证据；不能将已有审核说成从未开展，也不能将旧版本证据直接认定覆盖全部新版本。

1. 附件5：Excel753→754，375.5→376s；累计氧3393.75→3448.66、CO2 13.32→0.63、CO30.37→0.51。独立核实原始坐标与上下文、109.82差商而非已验证瞬时峰值；工艺/持值/时钟解释分列，不自动删点。
2. 附件8：CO内部2–31.5s（60点）、33–44.5s（24点）；CO2内部零段及同步上下文；核查n/n−1、首末跨度与物理持续时间，不将零自动判缺失。
3. 连续模型：区分S07候选定义、实际实现、模拟验收。检查O与q各自连续阶、非负性、导数与积分一致性、非均匀/边界/缺支持。当前进度和代码没有新正式连续模型，若仍缺实现就明确缺失，不虚构测试性能。
4. 积分：记录窗初值、左右矩形/梯形、可加性与端点差；近似规则接近不等于测量误差小。延迟：正k索引、max(r)与max(abs(r))、负相关、边界峰、激励不足和附件5敏感性；不能由探索峰断言真实运输延迟或因果。

交付Q1新目录中的逐项意见、固定输入SHA/源码哈希、已复用/新复算范围、证据坐标及待回复事项；不写Q2源文件、不改共同规范。任何下一轮原始只读复算或独立模拟执行均须按用户确认的任务范围，当前未执行。

## B线Q2负责人：复验Q1整改

固定Q1=`{Q1}`，旧基线3172d08，旧审核CR-A-Q1-3172d08-v01。Git固定入口见双线固定版本清单；不得只读历史简版前置审核目录。

1. 核验25项清单及27个新增文件，逐条回应13项整改矩阵，分别记录“意见接受”“代码完成”“独立验证”“共同批准”，不能把Accepted视为Resolved。
2. 70个唯一ID及十炉各7；25困难案例、45待证；原始建议不覆盖。复算半径1/2/4方向污染，尤其REF-6C02057-F、REF-6C02107-F；核对用途和真值资格，全部Pending保持。
3. D1/D2：每轴可用数≥2、名义2r比例0.5、65535污染规则、中心不可评估、单轴fallback、MAD0和强度尺度。对每轴1/2点、单/双轴不足、边界、污染、真实持续/瞬变窄峰、连续块构造独立反例；报告覆盖，不能将NaN当正常或只报成功窗。
4. R0：双顺序6与5反例、原点/第一步/第二步/未解决标记、估计支撑依赖、边界无支撑NaN。R1仍未实现、C2收敛/先验扫描未完成，不要求伪造实现。
5. 在隔离目录复现新增62项及必要旧61/12项，输出新验收记录，不覆盖原脚本默认输出目录；检查固定峰窗/肩窗、FWHM覆盖、零比例遮蔽、真实执行开关和哈希绑定。风险重现为预期结果，不等于方法准确。

交付Q2新目录中的独立验收报告、13条关闭/未关闭结论、70区意见、可复现测试记录与代码哈希。测试不依赖Q1作者的“通过”声明替代独立检查。

## 共同门槛

完成双方回复/复审后，两名队员逐用途批准首批参考窗，冻结输入版本、窗口、阈值来源、失败条件、评价分母和按炉隔离。真实执行须另有明确授权与已签署配置；本任务书不批准真实清洗、正式预处理、模型训练或合并main。任何共同文件更新交指定整合人。
''')
    decisions=[
        ('SYNC-J01','Q1新版独立验收与13条闭环','Q2复验Q1固定346c64e','13项独立结论及复算/测试；作者答复；未解决事项不能强关','Q1真实验证'),
        ('SYNC-J02','Q2正式版本反向审核闭环','Q1复核Q2固定7652b32及旧审核版本对应','附件5/8、积分、延迟与连续性逐条意见及作者回复','Q2真实验证'),
        ('SYNC-J03','首批参考区域逐用途批准','两队员逐区审阅','ID/坐标/证据/用途/批准人；25困难与45待证不得自动变真值','所有真实遮蔽'),
        ('SYNC-J04','D1/D2支持、污染和备用方法规则','两队员及两线Agent提供证据','最少2点、名义比例、实际s/nm窗、NaN/fallback及覆盖','Q1配置冻结'),
        ('SYNC-J05','峰窗/肩窗/背景和失败门槛','两队员','峰位/高/宽/面积与各覆盖；不能用测试误差倒推门槛','Q1重构验证'),
        ('SYNC-J06','Q2连续函数与模拟验收','Q2提交，Q1复核','O/q/气体连续阶、非负、守恒、边界及已知函数模拟','Q2正式连续建模'),
        ('SYNC-J07','R1暂缓与C2保守范围','两队员','R1未实现，C2尚未收敛验收；C0保留信息优先级','删失峰顶恢复'),
        ('SYNC-J08','跨炉划分、参数来源及实时信息边界','两队员','训练/验证/测试隔离、网格工况覆盖、available_time、时钟/延迟证据','泛化与Q3'),
        ('SYNC-J09','冻结配置及第一批真实验证授权','两队员签署、指定整合人发布','批准号/身份、固定配置及参考清单哈希、真实执行开关明确True','第一批真实验证')]
    csvout('待共同审批事项.csv',[dict(Decision_ID=i,事项=n,负责方=owner,所需证据=ev,阻塞范围=block,Status='Pending',Q1_Fixed_SHA=heads['q1-spectral'],Q2_Fixed_SHA=heads['q2-gas-oxygen'],确认队员A='',确认队员B='',批准编号='',说明='推送/模拟通过不等于共同批准') for i,n,owner,ev,block in decisions])
    dump('同步后远程核验证据.json',dict(task='A-Q1-SYNC-001',utc=datetime.now(timezone.utc).isoformat(),remote_heads=heads,ls_remote=actual,Q1_relation=[0,0],Q2_relation=relation('q2-gas-oxygen','origin/q2-gas-oxygen'),main_relation=relation('main','origin/main'),only_Q1_remote_changed=True,local_heads_unchanged=True,tracked_changes=text('diff','--name-only'),untracked_status=text('status','--porcelain=v1'),raw_data_read=False,research_tests_run=False,branch_merge=False,pending_decisions=len(decisions)))
    files=sorted(p for p in O.iterdir() if p.is_file());write('交付文件SHA256.txt','\n'.join(sha(p.read_bytes())+'  '+p.name for p in files)+'\n')
    print(json.dumps(dict(finished=True,fixed_remote=heads,files=len(files)+1,pending_decisions=len(decisions)),ensure_ascii=False))
else:raise ValueError('preflight or finish required')
