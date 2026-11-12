"""Freeze exact density-experiment evidence, executed binaries and committed source."""
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
summary=json.loads((repo/'research/residual_dense_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='isolated_C_experiment_only' and not summary['human_accepted']
root=args.workspace/'references/analysis/residual_dense_v1'
for name,digest in summary['current_source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
for name,digest in summary['input_sha256'].items():assert sha(name)==digest,name
assert sha(repo/'handoff/C文件索引.csv')==summary['c_index_sha256']
out=args.workspace/'baselines/residual_dense_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/可变载波密度V1.md','research/residual_dense_v1_summary.json','research/residual_dense_v1_plan.json',
    'handoff/算法说明.md','handoff/C模块与接口.md','handoff/研究续接.md','handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('可变载波密度V1，源码提交：'+revision+'\n'
    '独立residual_dense C模块；旧32样本／活动状态兼容，新逐带数量不改旧契约。\n'
    '40项既有CTest＋独立构建1项通过；四密度／三种子、已知stereo和独立直接三角和控制保留。\n'
    '固定上轮50percent工程DNA与认可相干LF，不逐密度重拟合／补偿增益。\n'
    '增加密度有谱线分散收益，也改变平稳拍频，不能解释成真实燃烧AM。\n'
    '30组交替离线计时，不等于整车／设备实时资格。9条共增益试听仅HTTP／解码验证，未新听评。\n'
    '442C/H索引包含6份新文件；旧436份哈希和职责、认可DNA／LF、驾驶默认及旧播放器保持。\n'
    'evidence保存全部原始运行、源码、二进制与报告；source.zip为可交接源码。\n',encoding='utf-8',newline='\n')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.residual-dense-freeze/1',source_commit=revision,
    new_C_H_count=6,prior436_C_unchanged=True,default_models_changed=False,human_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(row['bytes'] for row in files))))
