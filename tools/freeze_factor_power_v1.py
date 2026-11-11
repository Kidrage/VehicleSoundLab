"""Freeze finite-power diagnosis and all window controls, retaining old failure."""
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
summary=json.loads((repo/'research/factor_power_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='diagnostics_pass_only' and not summary['runtime_changes']
root=args.workspace/'references/analysis/factor_power_v1';assert str(root)==summary['evidence_root']
for name,digest in summary['current_source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
for name,digest in summary['input_sha256'].items():assert sha(name)==digest,name
prior=args.workspace/'baselines/magnitude_timescale_v1'
assert sha(prior/'manifest.json')==summary['prior_manifest_sha256']
assert sha(repo/'handoff/C文件索引.csv')==summary['c_index_sha256']
out=args.workspace/'baselines/factor_power_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/因子功率与窗口复核V1.md','research/factor_power_v1_summary.json',
    'research/factor_power_v1_plan.json','research/factor_window_v1_plan.json',
    'handoff/研究续接.md','handoff/C模块与接口.md','handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
shutil.copy2(prior/'manifest.json',out/'prior_manifest.json')
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('因子功率与窗口复核V1，提交：'+revision+'\n'
    '准确高斯矩、有限片段方差、512独立模拟和旧Welch功率重建；原16秒失败未删除或改阈值。\n'
    '7个情境／84个窗口配置说明固定失谐也可产生四步相关，不能认作已测发动机AM。\n'
    '没有新合成模型、试听或C／正式模型／驾驶／空间接入；436份C/H与认可DNA／LF保留。\n'
    '每阶段exact_sources保存实际执行字节；输入按各report和prior manifest恢复。\n',encoding='utf-8',newline='\n')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
       for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.factor-power-freeze/1',source_commit=revision,
    prior_16s_result='not_passed',new_model_qualified=False,runtime_changes=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(r['bytes'] for r in files))))
