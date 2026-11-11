"""Freeze temporal research, offline oscillator candidate and listening assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=json.loads((repo/'research/temporal_texture_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='pass' and not summary['runtime_changes'] and not summary['human_accepted']
root=args.workspace/'references/analysis/temporal_texture_v1';assert str(root)==summary['evidence_root']
for name,digest in summary['source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
for name,digest in summary['input_metadata_sha256'].items():assert sha(args.workspace/name)==digest,name
assert sha(repo/'handoff/C文件索引.csv')==summary['c_index_sha256']
assert sha(args.workspace/'baselines/residual_motion_v1/manifest.json')==summary['prior_manifest_sha256']
out=args.workspace/'baselines/temporal_texture_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/高频时间细节V1.md','research/temporal_texture_v1_summary.json',
    'research/temporal_texture_v1_plan.json','handoff/C模块与接口.md','handoff/研究续接.md',
    'handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
for name in summary['input_metadata_sha256']:
    target=out/'input_metadata'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(args.workspace/name,target)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('高频时间细节V1，提交：'+revision+'\n'
    '29组录音／冻结C分轨／频谱保持代理观察，6组已知包络控制；新离线高次谐波幅度候选6条。\n'
    '旧配方独立重建与冻结C误差约5.52e-8；已知功率、stereo相位、mono和实际WAV检查通过。\n'
    '候选同短参考的协方差距离下降，但慢包络未对齐，50%有平均谱差，不能称为音色通过。\n'
    '听评待反馈；没有C/H、正式模型库、驾驶、设备UI或行程协议变化。436份C/H与认可DNA/LF保持原值。\n'
    '原始素材及旧C分轨按prior manifest、input metadata与既有Release恢复。\n',encoding='utf-8')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
       for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.temporal-texture-freeze/1',
    source_commit=revision,runtime_changes=False,human_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(r['bytes'] for r in files))))
