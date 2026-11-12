"""Freeze stereo covariance families, additive budgets and executed source bytes."""
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
summary=json.loads((repo/'research/stereo_field_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='diagnostic_only_no_runtime_promotion' and not summary['models_changed']
root=args.workspace/'references/analysis/stereo_field_v1'
for name,digest in summary['current_source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
for name,digest in summary['input_sha256'].items():assert sha(name)==digest,name
assert sha(repo/'handoff/C文件索引.csv')==summary['c_index_sha256']
for name,digest in summary['accepted_model_sha256'].items():assert sha(repo/name)==digest,name
out=args.workspace/'baselines/stereo_field_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/左右声纹与叠加预算V1.md','research/stereo_field_v1_summary.json','research/stereo_field_v1_plan.json',
    'research/stereo_budget_v1_plan.json','research/stereo_components_v1_plan.json',
    'handoff/算法说明.md','handoff/C模块与接口.md','handoff/研究续接.md','handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('左右声纹与叠加预算V1，源码提交：'+revision+'\n'
    '原joint模型、分量细分的新候选族、两组十二已知控制、六矩阵预算控制及96误差分解全部保留。\n'
    '原始观察复用reference_audit_v1已冻结Welch块，不把此前研究过的录音称未见录音。\n'
    'aggregate joint的D3/E2通过不能覆盖能量平衡回退；新分量家族最终仅D2通过。\n'
    'A驻车/E车内的独立叠加差额存在非PSD；alpha只是条件边界，不能自动用作增益。\n'
    '无新音频、正式模型、C、驾驶、设备、行程或听评晋级；442C/H和认可DNA/LF保持。\n'
    'source.zip为源码交接，evidence/exact_sources保留每次实际执行字节。\n',encoding='utf-8',newline='\n')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.stereo-field-freeze/1',source_commit=revision,
    C_changes=False,models_changed=False,human_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(row['bytes'] for row in files))))
