"""Freeze negative cap/clock evidence and both AR8 verification attempts."""
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
summary=json.loads((repo/'research/magnitude_timescale_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='diagnostics_pass_candidate_not_qualified'
assert summary['candidate']['qualification']=='not_passed' and not summary['runtime_changes']
root=args.workspace/'references/analysis/magnitude_timescale_v1';assert str(root)==summary['evidence_root']
for name,digest in summary['current_source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
for name,digest in summary['input_sha256'].items():assert sha(name)==digest,name
assert sha(repo/'handoff/C文件索引.csv')==summary['c_index_sha256']
out=args.workspace/'baselines/magnitude_timescale_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/幅度时间模型与时钟敏感度V1.md','research/magnitude_timescale_v1_summary.json',
    'research/magnitude_timescale_v1_plan.json','research/factor_ar8_v1_plan.json','handoff/研究续接.md',
    'handoff/C模块与接口.md','handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('幅度时间模型与时钟敏感度V1，提交：'+revision+'\n'
    'AR上限对当前模型不生效，三个新旧FLOAT解码完全一致；已知时钟误差可制造谐波幅度变化。\n'
    '独立8滞后因子候选提高同目标慢声线量，但16秒功率门槛未通过。\n'
    '保留factor8_verification1早停失败与verification2完整检查／原阈值未通过，不作绿色验收。\n'
    '没有新试听页、C、正式模型、驾驶、UI或空间变更；旧试听和认可DNA／LF保留。\n'
    'exact_sources保留各次实际执行代码；input_sha256绑定此前冻结输入，不复制全部素材。\n',encoding='utf-8')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
       for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.magnitude-timescale-freeze/1',source_commit=revision,
    candidate_qualified=False,runtime_changes=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(r['bytes'] for r in files))))
