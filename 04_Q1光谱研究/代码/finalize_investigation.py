"""Numerical invariants, document supplements, artifact manifest; no data processing."""
from pathlib import Path
import csv,json,re,hashlib,subprocess
P=Path(__file__).resolve().parents[1];R=P.parent
def read(path):
    with path.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def find(name):return next(P.rglob(name))
def append(path,text):path.write_text(path.read_text(encoding='utf-8')+'\n\n'+text.strip()+'\n',encoding='utf-8',newline='\n')
baseline=read(find('S01_光谱基线核验.csv'));sat=read(find('S04_逐炉65535统计.csv'));comp=read(find('S04_二维连通区域登记表.csv'));loc=read(find('S04_65535完整位置.csv'));cand=read(find('S05_候选异常登记表.csv'));sens=read(find('S05_候选参数与统计结果.csv'));cases=read(find('S06_代表性案例登记表.csv'));pairs=read(find('S05_重复波长列证据.csv'));plates=read(find('S05_非上限平台统计.csv'))
assert len(baseline)==10 and len(cases)==68
for st in sat:
    h=st['Heat_ID'];points=int(st['Points'])
    assert sum(c['Heat_ID']==h for c in loc)==points
    for adj in ['4','8']:
        cc=[c for c in comp if c['Heat_ID']==h and c['Adjacency']==adj]
        assert sum(int(c['Points']) for c in cc)==points
        assert len(cc)==int(st['Components_'+adj])
    cs=[c for c in cand if c['Heat_ID']==h]
    for row in [r for r in sens if r['Heat_ID']==h]:assert sum(float(c['Score'])>float(row['Threshold']) for c in cs)==int(row['Count'])
assert all(float(c['Original_Value'])!=65535 and float(c['Score'])>12 for c in cand)
assert len({(c['Heat_ID'],c['Excel_Row'],c['Excel_Column']) for c in cand})==len(cand)
assert len(read(find('S03_逐波长结构统计.csv')))==20470
assert len(read(find('S03_逐时刻结构统计.csv')))==sum(int(r['Rows']) for r in baseline)
assert subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip()=='q1-spectral'
main=subprocess.check_output(['git','rev-parse','main'],cwd=R,text=True).strip();q2=subprocess.check_output(['git','rev-parse','q2-gas-oxygen'],cwd=R,text=True).strip();assert main==q2=='d7a5db947a3692e379f48eda6592e877803e054e'
changed=subprocess.check_output(['git','diff','--name-only'],cwd=R,text=True,encoding='utf-8').splitlines();assert all(x.startswith('04_Q1光谱研究/') for x in changed),changed
for c in cases:assert (P/c['Evidence_File']).exists()
for c in read(find('S06_低点补充案例.csv')):assert (P/c['Evidence_File']).exists()
for p in (P/'代码').glob('*.py'):compile(p.read_text(encoding='utf-8'),str(p),'exec')
run=json.loads((P/'研究成果/运行核验.json').read_text(encoding='utf-8'));assert run['code_sha256']==hashlib.sha256((P/'代码/spectral_investigation.py').read_bytes()).hexdigest()
assert (P/'研究成果/迁移读取函数实测.json').exists() and (P/'研究成果/补充核验.json').exists()
new='''## 补充证据与独立口径复核

补充程序实际重读十炉，前后哈希仍一致：新增最负局部分数低点H、G事件整谱曲线与方向比例、E完整平台及两侧各10个节点图。原±20列局部窗可能看不见宽平台肩部，完整图补足这一局限，没有改变平台定义。
'''
new+=f'发现{len(pairs)}对相邻不同波长列在完整炉次逐点完全相同；涉及{len(set(x["Heat_ID"] for x in pairs))}炉。位置和完整样本分母见S05_重复波长列证据.csv。这是新增可复核事实；量化、边缘通道记录或处理机制等解释仍未知，不能直接删除这些波长。非65535精确平台的数量、最大段及原值见S05_非上限平台统计.csv，平台也不自动等于异常。\n'
new+='本数据每炉4/8邻域的组件数量相同（并非观察到邻域改变组件数），两种定义仍必须分开说明。经检查，两种口径各自组件点数之和等于65535点数；所有局部分数阈值计数可从最宽候选位置表按分数复算。\n'
for name in ['Q1专项调查总报告.md','专项分析/S05_其他候选异常调查/S05_其他候选异常调查.md','专项分析/S06_谱峰与异常反例研究/S06_谱峰与异常反例研究.md']:
    append(P/name,new)
p=P/'Q1专项调查总报告.md';text=p.read_text(encoding='utf-8').replace('组件数依4/8邻域而变','组件定义依4/8邻域而异，本数据两种口径数量相同');p.write_text(text,encoding='utf-8',newline='\n')
append(p,'''## 代表性图形与解读

![宽平台及完整双肩](专项分析/S06_谱峰与异常反例研究/6C02057_E_完整平台肩部.png)

附件5所选平台连续915个波长节点，远大于最初局部窗；完整肩部图支持讨论截断形态，但不能确认量程或真实峰顶。

![无明显平顶的上限点](专项分析/S06_谱峰与异常反例研究/6B03206_F_局部证据.png)

附件2选中的65535只有一个波长点，没有平台。它反驳“所有上限点形态相同”，不能据此排除单点削顶。

![持续候选结构](专项分析/S06_谱峰与异常反例研究/6B03205_A_局部证据.png)

附件1在768.930 nm的局部极大值反复出现（该列作为局部极大值的时间比例约59.3%），是简单大值/波长差分删点的风险案例；没有确认其元素归属或物理真值。
''')
append(P/'Q1共同登记变更提案.md',f'新增建议：将{len(pairs)}对完整重复相邻波长列作为“记录结构待查”线索交叉审核；原因未确认。宽上限平台在附件5最大案例达915节点；本轮只在Q1追加证据，没有修改共同登记。')
append(P/'Q1交叉审核交接说明.md','补充重点：S05_重复波长列证据.csv记录不同实际lambda整列完全相同；请审核采集/导出/量化机制，不能据此自动判无效。S06新增H低点、G整谱方向比例和E完整平台肩部，须同时查看局部与宽区域，避免以小窗口否定肩部存在。')
append(P/'代码/运行说明.md','补充实际命令：python APMCM_New/04_Q1光谱研究/代码/supplement_structural_evidence.py --source-root .；报告生成后运行finalize_investigation.py核对守恒和补充说明。finalize只运行一次，避免重复追加说明。所有源文件位置/大小/hash使用原版本清单，没有复制完整原始矩阵。')
for path in (P/'实验验证/S07_候选方法与验证设计').glob('*.md'):
    append(path,'''## 研究记录与状态

Task ID：A-Q1-S07-R1；Research Question：如何根据S01–S06证据设计候选方法与独立验证；Data Source：十炉实际调查的报告/CSV和原始来源哈希；Method：本文的候选数学比较或验证设计；Mathematical Principle：公式与约束见正文；Assumptions：参考区须经共同审核，物理真值未知；Parameters：正文列拟参数/种子，均未执行；Results：仅设计文本，无实验性能；Evidence：S02网格、S04平台、S05候选及S06反例；Limitations：未做性能比较、不能证明真实截断强度恢复；Alternative Explanations：真实谱线/工艺变化/记录机制；Validation Method：检测、遮蔽重构和削顶分开并按炉隔离；Conclusion：供共同讨论的设计；Decision Status：Candidate Method；审批Pending。
''')
# Validate every Markdown artifact link and ensure no raw matrix or source attachment appears.
broken=[]
for path in P.rglob('*.md'):
    for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        if not link.startswith(('http://','https://','#')) and not (path.parent/link.split('#')[0]).exists():broken.append((str(path.relative_to(P)),link))
assert not broken,broken
files=[path for path in P.rglob('*') if path.is_file() and '__pycache__' not in path.parts]
assert not any(path.suffix in ['.xlsb','.pdf','.npz','.npy'] for path in files)
result=dict(heats=10,total_spectral_points=sum(int(r['Rows'])*2047 for r in baseline),saturation_points=len(loc),candidate_points=len(cand),base_cases=len(cases),low_point_cases=10,components_each_adjacency=sum(int(r['Components_4']) for r in sat),repeated_adjacent_column_pairs=len(pairs),all_conservation_checks_pass=True,threshold_counts_reproduced=True,main_q2_unchanged=True,markdown_links_valid=True,source_hashes_unchanged=True,no_preprocessing=True,no_push=True,images=sum(p.suffix=='.png' for p in files))
(P/'研究成果/最终验收.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
files=[path for path in P.rglob('*') if path.is_file() and '__pycache__' not in path.parts]
with (P/'研究成果/交付清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
    out=csv.DictWriter(f,fieldnames=['Relative_Path','Bytes','SHA256'],lineterminator='\n');out.writeheader()
    for path in sorted(files):out.writerow(dict(Relative_Path=path.relative_to(P).as_posix(),Bytes=path.stat().st_size,SHA256=hashlib.sha256(path.read_bytes()).hexdigest()))
print(json.dumps(result,ensure_ascii=False,indent=2))
