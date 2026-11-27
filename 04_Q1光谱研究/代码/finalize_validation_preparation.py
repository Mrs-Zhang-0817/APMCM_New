"""Audit artifact integrity and scope, append explicit stage update, preserve S-round artifacts."""
from pathlib import Path
import json,csv,hashlib,re,subprocess
P=Path(__file__).resolve().parents[1];R=P.parent;V=P/'实验验证';D=V/'V04_实验程序准备'
def read(p):
    with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
tests=json.loads((D/'V04_模拟功能测试结果.json').read_text(encoding='utf-8'));refs=read(V/'V02_可信参考区/V02_候选参考区域登记表.csv');checks=read(V/'V01_成果自审/V01_关键结果复算表.csv')
assert len(refs)==70 and len(set(r['Heat_ID'] for r in refs))==10 and all(r['Status']=='Pending Review' for r in refs)
assert len(set(r['Class'] for r in refs))==7 and all(r['Selected_By_S05_Score']=='False' for r in refs)
assert all(c['Passed'] for c in tests['checks']) and not tests['real_workbooks_read'];assert all(c['Consistent']=='True' for c in checks)
config=json.loads((D/'V04_待共同确认实验配置.json').read_text(encoding='utf-8'));assert config['status']=='Pending' and config['frozen'] is False and config['real_validation_allowed'] is False
costs=read(D/'V04_真实实验成本粗估.csv')
summary=f'''# V01–V04本轮成果与验收

完成真实十炉只读自审（{len(checks)}条复算记录）、70个Pending Review参考框、少量候选模型数学细化及独立模拟实验原型。61项功能测试通过；R1/R2/D3尚未实现，正式真实参考实验未执行。主要统计无矛盾，解释修正见V01_问题与修正建议.csv，不覆盖旧结果。
优先读[交叉审核摘要](V01_V04交叉审核摘要.md)、[12图精选图册](Q1交叉审核精选图册.md)及[V01报告](V01_成果自审/V01_Q1成果自审报告.md)，再审核V02参考清单、V03数学模型和V04配置。原有S01–S07统计与图像保留。
成本说明：模拟96×192基准按点数线性外推十炉，每参数一次D2约{float(costs[0]['Linear_Point_Extrapolation_Seconds']):.1f}秒、R0约{float(costs[1]['Linear_Point_Extrapolation_Seconds']):.1f}秒、C2固定200迭代约{float(costs[2]['Linear_Point_Extrapolation_Seconds']):.1f}秒。仅粗估，不含读取、搜索/折数及真实收敛；不能称真实十炉实测。优先区域小规模冻结试运行，避免直接跑所有参数笛卡尔积。
当前停止等待两名队员审核：参考区通过条件、污染邻域处理、物理窗和尺度参数、模型/指标、按炉划分及失败规则。无最终模型、无真实清洗数据、无推送。
'''
(V/'V01_V04成果总览.md').write_text(summary,encoding='utf-8',newline='\n')
updates={'README.md':'\n\n## V01–V04后续准备成果\n\n已完成十炉独立自审、70个Pending Review参考候选、候选模型数学定义及61项独立模拟功能测试。入口：[本轮总览](实验验证/V01_V04成果总览.md)、[12图精选](实验验证/Q1交叉审核精选图册.md)。原S轮成果保持，不将候选当已认证正常数据；真实参考实验未执行，等待交叉审核，不推送。\n',
'Q1当前研究进度.md':'\n\n## 2026-11-27 V01–V04阶段更新\n\n主要计数和网格经137条复算核对一致；解释修正另列V01问题表，不覆盖旧结论。70个候选框覆盖十炉七类、全部Pending Review；17框邻域有上限值、14框含旧分数候选，尚无正式可信真值清单。D0/D1/D2、R0及C1/C2原型仅在独立模拟谱运行，61项功能测试通过，R1/R2/D3未实现。当前停止于交叉审核与配置冻结准备，不执行真实参考验证、清洗或最终模型，不推送。详见实验验证/V01_V04成果总览.md。\n',
'Q1交叉审核交接说明.md':'\n\n## V01–V04新增审核入口\n\n请优先读实验验证/V01_V04交叉审核摘要.md及Q1交叉审核精选图册.md（12张既有/新增图，未复制旧图）。审核70个参考框的可信程度与风险，不把Pending当正常。复算表给每炉两个代表高分Excel位置；V03定义实际坐标二维函数、分方向检测及删失约束，V04给独立模拟测试和未冻结配置。待共同确认后才能启动真实验证，Agent自审不能代替交叉审核。\n'}
for name,note in updates.items():
    p=P/name;t=p.read_text(encoding='utf-8')
    if note.strip() not in t:p.write_text(t+note,encoding='utf-8',newline='\n')
# Check all tracked old artifacts except the three explicitly appended current entry documents.
baseline='fac16bc7e63894480a3ae778489bc247329b8223';old=subprocess.check_output(['git','ls-tree','-r','-z',baseline,'04_Q1光谱研究'],cwd=R).split(b'\0')
allowed={str((P/n).relative_to(R)).replace('\\','/') for n in updates}
for line in old:
    if not line:continue
    meta,path=line.split(b'\t',1);name=path.decode('utf-8')
    if name in allowed:continue
    expected=meta.decode().split()[2];actual=subprocess.check_output(['git','hash-object','--no-filters',name],cwd=R,text=True).strip();assert expected==actual,('Old artifact changed',name)
for branch in ['main','q2-gas-oxygen']:assert subprocess.check_output(['git','rev-parse',branch],cwd=R,text=True).strip()=='d7a5db947a3692e379f48eda6592e877803e054e'
files=[p for p in V.rglob('*') if p.is_file() and p.parent.name!='S07_候选方法与验证设计']+list((P/'代码').glob('*validation*.py'))
for path in files:
    if path.suffix=='.py':compile(path.read_text(encoding='utf-8'),str(path),'exec')
    if path.suffix=='.md':
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if not link.startswith(('http://','https://','#')):assert (path.parent/link.split('#')[0]).exists(),(path,link)
    if path.suffix in ['.md','.csv','.json','.py']:
        raw=path.read_bytes()
        if b'\r\n' in raw:path.write_bytes(raw.replace(b'\r\n',b'\n'))
result=dict(real_raw_audit_records=len(checks),candidate_reference_regions=70,reference_status='Pending Review',functional_tests=len(tests['checks']),all_tests_pass=True,formal_real_validation=False,original_S_round_files_preserved=True,main_and_q2_unchanged=True,public_push=False,selected_review_images=12)
(V/'V01_V04最终验收.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
with (V/'V01_V04交付清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
    out=csv.DictWriter(f,fieldnames=['File','Bytes','SHA256'],lineterminator='\n');out.writeheader()
    for p in sorted(set(files+[V/'V01_V04最终验收.json'])):
        if p.name!='V01_V04交付清单.csv':out.writerow(dict(File=p.relative_to(P).as_posix(),Bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest()))
print(json.dumps(result,ensure_ascii=False,indent=2))
