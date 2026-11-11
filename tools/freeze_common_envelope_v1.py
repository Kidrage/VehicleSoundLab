"""Freeze common/colour measurements with exact execution sources and input IDs."""
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
summary=json.loads((repo/'research/common_envelope_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='pass' and not summary['runtime_changes'] and not summary['new_human_acceptance']
root=args.workspace/'references/analysis/common_envelope_v1'
assert str(root)==summary['evidence_root']
for name,digest in summary['source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
for name,digest in summary['input_metadata_sha256'].items():assert sha(args.workspace/name)==digest,name
assert sha(repo/'handoff/C文件索引.csv')==summary['c_index_sha256']
out=args.workspace/'baselines/common_envelope_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/共同响度与声线变化V1.md','research/common_envelope_v1_summary.json',
    'research/common_envelope_v1_plan.json','handoff/研究续接.md','handoff/C模块与接口.md',
    'handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
for name in summary['input_metadata_sha256']:
    target=out/'input_metadata'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(args.workspace/name,target)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('共同响度与声线变化V1，提交：'+revision+'\n'
    '10组观察、8组控制；1707组分段／去趋势配置用独立多项式、带间log比例及直接DFT核验。\n'
    '大幅动态录音主要有共同包络，固定参考仍有较强慢声线变化；不能据此识别负载、音轨编辑或源AM。\n'
    '仅测量，不拟合／生成新音色。认可固定DNA与相干LF保留；C、模型库、驾驶、UI和行程接口未修改。\n'
    '源录音与既有试听仍引用input_metadata与此前冻结包；后续听评另记。\n',encoding='utf-8')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
       for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.common-envelope-freeze/1',source_commit=revision,
    runtime_changes=False,new_human_acceptance=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(r['bytes'] for r in files))))
