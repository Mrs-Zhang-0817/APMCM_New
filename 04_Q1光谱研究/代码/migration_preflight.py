"""Exercise the migrated reader function only, without executing its historical document generator."""
from pathlib import Path
import ast,argparse,json,hashlib
import numpy as np
from pyxlsb import open_workbook
P=Path(__file__).resolve().parents[1];R=P.parent
parser=argparse.ArgumentParser();parser.add_argument('--corrected',type=Path,required=True);args=parser.parse_args()
source=R/'03_共同数据分析/分析代码/takeover_audit.py'
tree=ast.parse(source.read_text(encoding='utf-8'));function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load')
namespace={'np':np,'open_workbook':open_workbook};exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
before=hashlib.sha256(args.corrected.read_bytes()).hexdigest();header,data,sheets,nonnum=namespace['load'](args.corrected)
assert data.shape==(1479,2051) and len(header)==2051 and sheets==['6B03205'] and nonnum==0
assert int((data[:,-2]==0).sum())==0 and int((data[:,-1]==0).sum())==95
assert before==hashlib.sha256(args.corrected.read_bytes()).hexdigest()
(P/'研究成果').mkdir(exist_ok=True)
(P/'研究成果/迁移读取函数实测.json').write_text(json.dumps(dict(reader=str(source.relative_to(R)),source_hash=hashlib.sha256(source.read_bytes()).hexdigest(),method='AST提取原迁移load函数并实际读取修正版完整工作簿，避免运行历史顶层生成器',shape=list(data.shape),nonnumeric=nonnum,source_unchanged=True,legacy_top_level_generator_executed=False),ensure_ascii=False,indent=2),encoding='utf-8')
print('Migrated loader actually executed: 1479 x 2051, corrected gas counts verified.')
