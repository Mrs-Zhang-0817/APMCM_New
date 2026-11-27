"""Read-only repository audit. Writes only new files beside this script.
No checkout, branch changes, push, merge, study execution, or workbook reading.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict,Counter
import subprocess,hashlib,json,csv,io
O=Path(__file__).resolve().parent;R=O.parents[2]
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def txt(*args):return git(*args).decode('utf-8').strip()
def sha(b):return hashlib.sha256(b).hexdigest()
def write(name,s):
    with (O/name).open('x',encoding='utf-8',newline='') as f:f.write(s)
def dump(name,a):write(name,json.dumps(a,ensure_ascii=False,indent=2))
def csvout(name,rows):
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows);write(name,'\ufeff'+s.getvalue())
assert (R/'.git').is_dir()
assert Path(txt('rev-parse','--show-toplevel')).resolve()==R.resolve()
assert txt('remote','get-url','origin')=='https://github.com/Mrs-Zhang-0817/APMCM_New.git'
assert txt('branch','--show-current')=='q1-spectral'
stamp=datetime.now(timezone.utc).isoformat()
refs=['main','q1-spectral','q2-gas-oxygen','origin/main','origin/q1-spectral','origin/q2-gas-oxygen']
heads={ref:txt('rev-parse',ref) for ref in refs}
remote_raw=txt('-c','http.proxy=','ls-remote','origin','refs/heads/main','refs/heads/q1-spectral','refs/heads/q2-gas-oxygen')
remote={line.split()[1].removeprefix('refs/heads/'):line.split()[0] for line in remote_raw.splitlines()}
assert all(remote[h]==heads['origin/'+h] for h in ('main','q1-spectral','q2-gas-oxygen'))
baseline=txt('rev-parse','346c64e^{commit}');assert baseline==heads['q1-spectral']
def relation(a,b):
    left,right=map(int,txt('rev-list','--left-right','--count',a+'...'+b).split())
    return left,right
branches=[]
for h in ('q1-spectral','q2-gas-oxygen','main'):
    left,right=relation(h,'origin/'+h)
    branches.append(dict(Branch=h,Local_SHA=heads[h],Remote_SHA=remote[h],Local_Only_Commits=left,Remote_Only_Commits=right,Relation='相同' if left==right==0 else '本地领先' if right==0 else '本地落后' if left==0 else '双方分叉',Checked_Out=h=='q1-spectral',Remote_Verification='fetch后ls-remote再次一致',Audit_UTC=stamp))
csvout('本地与远程分支状态表.csv',branches)
tree={};byoid={};working_before={}
for ref in refs:
    entries=[]
    for raw in git('ls-tree','-r','-l','-z',ref).split(b'\0'):
        if not raw:continue
        head,path=raw.split(b'\t',1);mode,kind,oid,size=head.decode().split();path=path.decode('utf-8')
        if kind!='blob':continue
        e=dict(Ref=ref,Commit=heads[ref],Path=path,Bytes=int(size),Git_Blob_SHA1=oid)
        entries.append(e);byoid[oid]=int(size)
        if ref=='q1-spectral':working_before[path]=sha((R/path).read_bytes())
    tree[ref]=entries
# SHA256 every actual Git blob once, batching binary records without line-based data assumptions.
hashes={};oids=list(byoid)
for start in range(0,len(oids),32):
    batch=oids[start:start+32];raw=subprocess.check_output(['git','cat-file','--batch'],cwd=R,input=('\n'.join(batch)+'\n').encode());offset=0
    for requested in batch:
        end=raw.index(b'\n',offset);header=raw[offset:end].decode().split();length=int(header[2]);offset=end+1
        b=raw[offset:offset+length];offset+=length+1;assert header[0]==requested and len(b)==byoid[requested]
        hashes[requested]=sha(b)
inventory=[]
for ref in refs:
    for e in tree[ref]:
        row=dict(e);row.update(Git_Content_SHA256=hashes[e['Git_Blob_SHA1']],In_Current_Branch=e['Path'] in working_before,Workspace_Raw_SHA256=working_before.get(e['Path'],''),Hash_Note='Git内容固定字节；工作区原字节可能CRLF；不同版本逐ref保留',Scope='仓库全部受控文件；排除.git对象与忽略缓存；不表示逐图/逐表科研验收')
        inventory.append(row)
csvout('当前研究文件完整清单.csv',inventory)
changed=txt('-c','core.quotepath=false','diff-tree','--no-commit-id','--name-status','-r',baseline)
assert all(line.split('\t',1)[0]=='A' and line.split('\t',1)[1].startswith('04_Q1光谱研究/') for line in changed.splitlines())
assert len(changed.splitlines())==27
P=R/'04_Q1光谱研究/实验验证/交叉审核整改_v2'
manifest=list(csv.DictReader((P/'版本变更与SHA256清单.csv').open(encoding='utf-8-sig')))
checks=[]
for a in manifest:
    b=git('show',baseline+':'+a['File']);disk=(R/a['File']).read_bytes()
    checks.append(dict(File=a['File'],Expected_SHA256=a['SHA256'],Commit_SHA256=sha(b),Workspace_SHA256=sha(disk),Git_Match=sha(b)==a['SHA256'],Workspace_Match=sha(disk)==a['SHA256']))
assert len(checks)==25 and all(a['Git_Match'] and a['Workspace_Match'] for a in checks)
csvout('Q1整改25项SHA256复核.csv',checks)
old=json.loads((P/'历史文件保护核验.json').read_text(encoding='utf-8'))
old_bad=[p for p,digest in old['hashes'].items() if sha((R/p).read_bytes())!=digest]
assert not old_bad
refs70=list(csv.DictReader((P/'Q1_70区修订审核表.csv').open(encoding='utf-8-sig')))
assert len(refs70)==len({a['Reference_ID'] for a in refs70})==70
assert all(a['Joint_Approval']=='Pending' and a['Ordinary_Truth_Allowed']=='False' for a in refs70)
matrix=list(csv.DictReader((P/'Q1_13项交叉审核整改矩阵.csv').open(encoding='utf-8-sig')))
assert len(matrix)==13
config=json.loads((P/'Q1_正式验证配置v2草案.json').read_text(encoding='utf-8'))
assert config['real_data_execution_allowed'] is False and config['frozen'] is False
logs=txt('log','-5','--format=%H %s')
cross=[dict(Left=a,Right=b,Left_Only=relation(a,b)[0],Right_Only=relation(a,b)[1],Merge_Base=txt('merge-base',a,b)) for a,b in [('q1-spectral','origin/main'),('q1-spectral','origin/q2-gas-oxygen'),('origin/q1-spectral','origin/main'),('origin/q2-gas-oxygen','origin/main')]]
dump('审计原始证据.json',dict(task='A-Q1-GIT-AUDIT-001',audit_utc=stamp,root=str(R),git_directory_is_real=True,origin=txt('remote','-v'),initial_branch='q1-spectral',status_at_audit=txt('status','--short','--branch'),heads=heads,remote_ls_remote=remote,branch_relations=branches,cross_relations=cross,last_five=logs.splitlines(),remediation_commit=baseline,commit_27_additions=changed.splitlines(),manifest_count=25,manifest_hash_match=True,historical_count=len(old['hashes']),historical_changes=old_bad,refs70=Counter(a['Review_Status'] for a in refs70),ordinary_truth_approved=0,issue_responses=Counter(a['当前状态'] for a in matrix),test_results_read_only='旧61、旧12、新62测试记录已读取；本轮未重跑',tree_counts={k:len(v) for k,v in tree.items()},inventory_rows=len(inventory),unique_git_blobs=len(hashes),fetched=True,pushed=False,merged=False,research_executed=False))
# Record exact primary documents actually read; keep Q2 on its fixed branch without checkout.
readpaths=['README.md','AGENTS.md','00_项目管理/项目主文档.md','00_项目管理/当前项目进度.md','00_项目管理/完整研究SOP.md','00_项目管理/共同决策日志.md','02_统一研究规范/双Agent协作规范.md','02_统一研究规范/Git协作规范.md','02_统一研究规范/统一数据质量标准.md']
readpaths += ['04_Q1光谱研究/实验验证/交叉审核整改_v2/'+a for a in ('Q1_整改总报告.md','Q1_D1_D2邻居不足修复报告.md','Q1_R1实现与验收报告.md','Q1_回归测试报告.md','Q1_验证基准v2草案.md','Q1_待共同决策事项.md','本轮验收.json')]
readpaths += ['04_Q1光谱研究/实验验证/队友成果综合审核/'+a for a in ('Q1_Q2综合审核报告.md','交叉审核意见.csv')]
q2paths=['05_Q2供氧与烟气研究/'+a for a in ('Q2_专项调查总报告.md','Q2当前研究进度.md','Q2交叉审核交接说明.md','专项分析/S01_数据基线.md','专项分析/S02_零值与常量段.md','专项分析/S03_数值更新.md','专项分析/S04_附件5.md','专项分析/S05_突变上下文.md','专项分析/S06_供氧烟气关系.md','专项分析/S07_候选方法与验证.md','交叉审核/CR-A-Q1-3172d08-v01/审核报告.md','交叉审核/CR-A-Q1-3172d08-v01/逐条问题清单.csv')]
sources=[]
for ref,paths in [('q1-spectral',readpaths),('origin/q2-gas-oxygen',q2paths)]:
    for path in paths:
        b=git('show',heads[ref]+':'+path);b.decode('utf-8-sig');sources.append(dict(Ref=ref,Commit=heads[ref],Path=path,Bytes=len(b),SHA256=sha(b),Reading='实际文档读取；本轮不重新证明其中研究结论'))
csvout('已读关键材料来源.csv',sources)
write('Git仓库连接审计报告.md',f'''# Git工作区连接审计

Task A-Q1-GIT-AUDIT-001；审计UTC {stamp}。本轮为连接、版本与研究流程恢复审计；不开展研究任务。

仓库身份通过。实际绝对路径：`{R}`；`.git`为真实目录；`git rev-parse --show-toplevel`与该路径一致。origin获取/推送均为`https://github.com/Mrs-Zhang-0817/APMCM_New.git`。当前分支q1-spectral。审计新增文件前工作区干净（无受控变更，也无其他未跟踪文件）；本报告生成后仅新增本文件夹。

成功fetch origin并再次ls-remote校验三条远程分支，Git读取连接可用；未测试推送写权限，不能由fetch成功推断推送一定成功。GitHub Desktop界面本轮未操作，不能据本审计宣称桌面应用选中了哪个项目。

本地Q1整改存在但尚未同步，远程Q1仍为{remote['q1-spectral']}。Q1本地相对远程领先1、落后0；当前为可快进关系，没有发现远程独有提交。若后续授权同步，先重取远程和检查工作区，再普通推送q1-spectral；此结论仅限审计时刻，不保证未来仍成立。本轮按“审计后停止”边界不推送、不创建PR或合并。

本地main与q2-gas-oxygen各落后对应远程2个提交，没有本地独有提交。Q1本地与远程main各有7和2个独有提交；Q1本地与远程Q2各有7和2个独有提交。不能将这些跨分支差异当同一分支同步失败，也不能直接拉取合并main覆盖线内证据。

最新五条本地提交：
```
{logs}
```

完整分支SHA和关系见本地与远程分支状态表.csv、审计原始证据.json。本轮未切分支、未改origin、未创建第二仓库、未改原始附件/历史成果/共同规范、未改main或Q2分支。允许fetch更新远程跟踪引用，但未移动本地分支头。
''')
write('Q1整改提交核验报告.md',f'''# Q1整改提交核验

完整SHA：`{baseline}`。当前q1-spectral的HEAD，父提交为`{txt('rev-parse',baseline+'^')}`。该提交确实在目标仓库本地对象库及Q1历史中；不凭短SHA或旧对话判断。

实际变更27个新增文件，均在04_Q1光谱研究，不修改历史文件。含3个新增程序和24个整改目录文件；8项指定交付全部存在。固定提交与当前工作区的25项清单SHA256逐项匹配；另核对245份历史文件原字节哈希，无差异。详见Q1整改25项SHA256复核.csv。

70条记录且70唯一ID，十炉各7；修订状态25 Reject Candidate、45 Needs More Evidence，普通真值获批0，全部共同审批Pending。13条回应10 Accepted、3 Partially Accepted，不等同复审关闭。真实执行开关False、配置未冻结；R1仍未实现，C2收敛验收仍未完成。

档案记录为61项功能、12项风险、62项新版合成检查通过。本轮仅读取记录并核验版本完整性，未重跑测试，更不是Q2独立验收或真实数据验证。

远程固定Q1仍为`{remote['q1-spectral']}`，不是本次整改SHA。该远程提交为346c64e的祖先；当前领先1、落后0，尚未上传。本轮保留未同步状态等待用户确认后续操作，禁止强推或自动合并。

八项交付位置：`04_Q1光谱研究/实验验证/交叉审核整改_v2/`。算法及新测试：`04_Q1光谱研究/代码/validation_modules_v2.py`、`test_validation_v2.py`。校验不等于认可算法适用性或批准参考真值。
''')
q1count=len(tree['q1-spectral']);q2files=[e for e in tree['origin/q2-gas-oxygen'] if e['Path'].startswith('05_Q2供氧与烟气研究/')]
write('当前项目阶段与阻塞事项.md',f'''# 项目阶段恢复与阻塞事项

阶段：专项调查后的交叉审核整改/验证准备；尚未进入第一批正式真实验证或正式预处理。标准v2（18条）仍适用。共同文件未更新；本报告是Q1本线审计记录，不代替共同主文档。

已存在的证据：十炉共同EDA及整体质量审查；Q1 S01–S07、V01–V04、70区前置及修订审核、D1/D2修复、R0支撑追踪、模拟结果；远程Q2 S01–S07及Q2→Q1审核；Q1的13项整改回应。文件清单含六个固定本地/远程引用的全部受控版本，共{len(inventory)}行；当前Q1分支{q1count}文件，远程Q2专属目录{len(q2files)}文件。清单按引用保存同路径冲突版本，不将六个快照行数当独立成果数。

重要状态修正：已有`04_Q1光谱研究/实验验证/队友成果综合审核/`，其报告审核旧Test仓库q2分支b35ac738d01642efe11b6e1a759572cace8b0885，含146条复算及逐条意见。因此不能说“从未做Q1→Q2审核”。目前缺的是对正式仓库固定新版Q2的版本对应核查、作者回应与复审闭环；下一轮先复用历史审核，确认文件差异，不重新做泛化EDA。正式Q2最新7652b32相对59b1b9f仅增加六份Q2→Q1审核材料；本轮未把旧Test与正式库所有研究结果逐字节等价认证。

阻塞与范围：

1. 交接阻塞：346c64e仅本地，Q2从远程Q1无法取得整改文件。待确认普通推送；推送本身不等于共同科学批准。
2. 分支可见性：当前Q1工作树的Q2目录仅README；最新Q2成果在origin/q2-gas-oxygen，本轮直接读取Git对象，没有复制或合并到Q1。读到远程跟踪引用不等于当前目录已有这些文件。
3. Q1验收：缺Q2对346c64e的独立复验与13项问题关闭意见；已读Q2审核仍针对3172d08。
4. 参考真值：25困难区、45待证区；普通真值批准0。峰窗、肩窗、背景、物理窗口、缺邻策略、覆盖底线及失败阈值未冻结。
5. Q2验证及连续性：S07仍为候选方法和验证设计；在本次检查的远程树中未发现独立连续模型/模拟验证验收交付。不能推断队友机器没有未上传工作。需单调累计氧与非负流率、CO/CO2非负连续模型、积分与边界的可复现模拟验收。零阶保持不应直接称最终连续函数。
6. 科学证据：零编码/持值机制、附件5工况、真实时钟、65535量程和峰顶、Q3 available_time仍无独立确定证据。探索滞后不能确认真实运输延迟。
7. 文档滞后：README、共同主文档、共同进度仍叙述专项未启动；最新工作线报告已到调查/整改。不可按旧进度抹去已存在成果。共同入口更新须由指定整合人按proposal流程办理，本轮未覆盖。

第一批真实验证、正式预处理、正式Q1/Q2连续模型及Q3训练均未获本轮执行授权。下一步应先复审、最小方案和共同门槛，而非立即清洗。
''')
write('下一轮双线任务计划.md','''# 下一轮双线任务计划（待用户确认，未执行）

Task A-Q1-GIT-AUDIT-001；所有科学决策Pending。不自动启动其他Agent，不代队员签署。

|顺序|负责人|具体任务|输入与交付|验收门槛|
|---|---|---|---|---|
|0|Q1维护者|重新fetch、确认干净与快进关系后，将346c64e普通推送到q1-spectral；不合并main/Q2|固定远程完整SHA及文件入口；先处理本次审计新增文件，不能让其混入未经核验提交|远端固定SHA可读取且清单哈希匹配；若远端有新提交先比较，不强推|
|1A|Q2/B线|独立复验Q1新版|以346c64e和13项矩阵为基线，隔离重跑新版模拟及有针对性的旧反例，核对70区方向污染和资格状态|每条解决/未解决及复算证据；独立测试不等于参考批准；产物仅写Q2自己的新目录|
|1B|Q1/A线|准备最小可行验证方案|冻结候选最小算法D0弱基准、D1/D2、R0两序与C0保留信息；R1和真实C2继续禁用；记录峰/肩窗、支持与覆盖|提供可执行草案和未决项，不运行真实验证；算法最终选择由双方确认|
|1C|Q1/A线|正式版本Q2反向审核闭环|先比较旧Test b35ac738审核与正式Q2 7652b32的源文件版本，复用已审核证据；重点附件1端点、附件2表头/零值、附件5 Excel753→754、附件8内部零段、n/n−1、滞后符号与连续性|逐条坐标/依据/回复及新旧版本差异；不把历史审核误记全新独立复算|
|1D|Q2/B线|补齐Q2模拟与连续候选|已知非负q及积分O、气体事件、保持/量化/零编码/突变/边界，检测与重构分别评价；定义O和q的C0/C1性质及无支撑规则|导数/积分守恒、非负性、峰和事件时刻、误差分布与覆盖；按炉防泄漏设计；仅独立合成|
|2|两名队员|逐用途审批第一批小规模参考窗|从70区中经补证的普通背景/完整峰窗挑选；另保留变化、边界及削顶困难层，Q2提出自己的参考窗|明确ID/坐标/用途/理由/签署人/批准号；未批准不得当真值，困难层不因难而删除|
|3|两名队员及指定整合人|冻结最小验证配置|阈值来源、实际s/nm窗、随机种子、遮蔽/注入/削顶、峰窗背景、评价分母、覆盖底线、失败条件、按炉划分及参数来源|固定配置与清单哈希、双方真实批准及执行开关；共同文件走proposal而非各线直接改|
|4|获明确授权后的两线|开展第一批真实数据验证|只对已批准用途/窗口执行，先验证后讨论正式处理|逐炉/分层报告失败和不确定性；真实验证不得自动扩为全十炉清洗；完成后再独立审核|

最小方案不要求同时扩展全部候选算法；必须包含普通背景、峰保护及困难场景的覆盖约束。当前0个获批普通真值阻断真实遮蔽，但不阻断独立合成、证据整理和版本复审。Q3仅保留信息可用时间设计，不开展训练。

本轮仅提交此计划，完成审计后停止，等待用户确认下一轮范围。
''')
assert all(sha((R/p).read_bytes())==s for p,s in working_before.items())
assert all(txt('rev-parse',ref)==s for ref,s in heads.items())
assert not txt('diff','--name-only')
dump('审计验收.json',dict(task='A-Q1-GIT-AUDIT-001',repository_identity=True,all_six_branch_heads_unchanged=True,tracked_worktree_unchanged=True,report_folder=O.relative_to(R).as_posix(),inventory_rows=len(inventory),distinct_paths=len({r['Path'] for r in inventory}),unique_git_blobs=len(hashes),Q1_commit=baseline,Q1_remote=remote['q1-spectral'],Q1_synced=False,Q1_25_hashes_match=True,historical_245_unchanged=True,push_executed=False,merge_executed=False,research_or_tests_executed=False,approval_status='Pending'))
print(json.dumps(dict(output=str(O),refs=heads,inventory_rows=len(inventory),unique_paths=len({e['Path'] for e in inventory}),branch_table=branches,sha_checks=25,tracked_unchanged=True),ensure_ascii=False,indent=2))
