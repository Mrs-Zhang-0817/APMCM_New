"""Refresh final artifact hashes after visual QA; does not read or process spectra."""
from pathlib import Path
import json,csv,hashlib,re
P=Path(__file__).resolve().parents[1]
for name in ['Q1当前研究进度.md','专项分析/S06_谱峰与异常反例研究/S06_谱峰与异常反例研究.md','代码/运行说明.md']:
    p=P/name;t=p.read_text(encoding='utf-8')
    note='图形QA补充：对附件1/5/6的低点H案例新增明确标色轴范围的局部放大图，原全上限背景图保留以供比较；所有点均为原值，未插值或平滑。实际命令：python APMCM_New/04_Q1光谱研究/代码/zoom_low_cases.py --source-root .。验收时修复了Git中文路径在Windows默认编码下的解析问题，UTF-8复核通过，未改变统计结果。'
    if note not in t:p.write_text(t+'\n\n'+note+'\n',encoding='utf-8',newline='\n')
result=json.loads((P/'研究成果/最终验收.json').read_text(encoding='utf-8'));result['images']=len(list(P.rglob('*.png')));result['visual_QA']='抽查全平台双肩、持续峰、高分点、低点和低点放大图；补足统一色轴下弱信号可读性';(P/'研究成果/最终验收.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
files=[p for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='交付清单.csv']
for path in files:
    if path.suffix in ['.md','.csv','.json','.py','.txt']:
        data=path.read_bytes()
        if b'\r\n' in data:path.write_bytes(data.replace(b'\r\n',b'\n'))
for path in files:
    if path.suffix=='.py':compile(path.read_text(encoding='utf-8'),str(path),'exec')
    if path.suffix=='.md':
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if not link.startswith(('http://','https://','#')):assert (path.parent/link.split('#')[0]).exists(),link
with (P/'研究成果/交付清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['Relative_Path','Bytes','SHA256'],lineterminator='\n');w.writeheader()
    for path in sorted(files):w.writerow(dict(Relative_Path=path.relative_to(P).as_posix(),Bytes=path.stat().st_size,SHA256=hashlib.sha256(path.read_bytes()).hexdigest()))
print(json.dumps(result,ensure_ascii=False,indent=2));print('Deliverables excluding ignored caches:',len(files)+1)
