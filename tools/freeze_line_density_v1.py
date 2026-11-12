"""Freeze the local-support controls, C trials and all executed source versions."""
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
summary=json.loads((repo/'research/line_density_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='experimental_C_render_only' and not summary['human_accepted'] and not summary['C_changes']
root=args.workspace/'references/analysis/line_density_v1'
for name,digest in summary['current_source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
for name,digest in summary['input_sha256'].items():assert sha(name)==digest,name
for entry in summary['authored_experimental_profiles']:
    for kind in ('dna','residual'):assert sha(repo/entry[kind])==entry[kind+'_sha256']
assert sha(repo/'handoff/C文件索引.csv')==summary['c_index_sha256']
out=args.workspace/'baselines/line_density_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/局部谱线与高频密度V1.md','research/line_density_v1_summary.json',
    'research/line_density_v1_plan.json','research/line_density_render_v1_plan.json',
    'handoff/研究续接.md','handoff/C模块与接口.md','handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
shutil.copytree(repo/'voices/line_density_v1',out/'models')
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('局部谱线与高频密度V1，提交：'+revision+'\n'
    'analysis1直接DFT空频点精度失败保留；analysis2整数模相位修复，同阈值并以已知信号复现。\n'
    '12组观察／两种局部窗口／3与5bin移动支持；仅支持独立有界C候选，不是物理噪声比例。\n'
    '既有C核生成0／25／50工程高频密度，各三种子；保留固定相位、低谐波与独立相干LF。\n'
    '7条共同增益试听通过HTTP／解码，未做浏览器交互／新听评；不接驾驶默认。\n'
    '436份C/H与认可DNA/LF保持原值，source.zip为交接源码，exact_sources保存各实际执行版本。\n',encoding='utf-8',newline='\n')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.line-density-freeze/1',source_commit=revision,
    C_changes=False,default_models_changed=False,human_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(row['bytes'] for row in files))))
