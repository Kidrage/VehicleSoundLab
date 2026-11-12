"""Freeze failed and completed allocation diagnostics with exact executed sources."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=json.loads((repo/'research/harmonic_allocation_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='diagnostics_only' and not summary['controls']['shape_extraction_qualified']
root=args.workspace/'references/analysis/harmonic_allocation_v1'
assert str(root)==summary['evidence_root']
for name,digest in summary['current_source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
for name,digest in summary['input_sha256'].items():assert sha(name)==digest,name
assert sha(repo/'handoff/C文件索引.csv')==summary['c_index_sha256']
out=args.workspace/'baselines/harmonic_allocation_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/慢声线与谐波分配V1.md','research/harmonic_allocation_v1_summary.json',
    'research/harmonic_allocation_v1_plan.json','handoff/算法说明.md','handoff/研究续接.md',
    'handoff/C模块与接口.md','handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('慢声线与谐波分配V1，提交：'+revision+'\n'
    '12组观察／144窗口配置／12纯音相位反例；analysis1早停失败、analysis2完整复核、analysis3补原始声道溯源。\n'
    '保留原阈值，rect1共同增益声线泄漏4项仍失败，不能称为全项通过。\n'
    'A慢变化跨窗口保留；纯净失谐音也能得到接近零的平均相位占比，禁止按该占比自动移走DNA能量。\n'
    'A原始该段已近双mono；没有C／模型／默认驾驶／新试听改动，436份C/H与认可DNA/LF保持原值。\n'
    '各阶段exact_sources是执行字节，source.zip是交接版本，输入按summary及原冻结manifest恢复。\n',encoding='utf-8',newline='\n')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.harmonic-allocation-freeze/1',
    source_commit=revision,runtime_changes=False,models_changed=False,shape_extraction_qualified=False,
    human_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(row['bytes'] for row in files))))
