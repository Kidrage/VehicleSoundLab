"""Freeze an independently runnable layered DNA driver and all development evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip(),'Commit final sources first'
summary=repo/'research/residual_atlas_v1_summary.json'
r=json.loads(summary.read_text(encoding='utf-8'))
assert r['result']=='pass' and r['tests']==33 and not r['human_accepted']
root=args.workspace/'references/analysis/residual_atlas_v1'
assert str(root)==r['evidence_root']
for name,expected in r['source_sha256'].items():assert sha(repo/name)==expected,name
for name,expected in r['evidence_sha256'].items():assert sha(root/name)==expected,name
for name,expected in r['binaries_sha256'].items():assert sha(repo/'handoff-build/bin/Release'/name)==expected,name
assert sha(repo/'handoff/C文件索引.csv')==r['c_index_sha256']
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
out=args.workspace/'baselines/residual_atlas_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence')
for name in ('exterior_anchors_v1','cabin_anchors_v1','residual_atlas_v1'):
    shutil.copytree(repo/'voices'/name,out/'voices'/name)
(out/'bin').mkdir()
for name in r['binaries_sha256']:
    if name!='VslSystem.exe':shutil.copy2(repo/'handoff-build/bin/Release'/name,out/'bin'/name)
(out/'docs').mkdir()
for p in (summary,repo/'research/驾驶细节分层V1.md',repo/'handoff/C模块与接口.md',repo/'handoff/C文件索引.csv'):
    shutil.copy2(p,out/'docs'/p.name)
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'Run-DNA-Drive.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\nstart "" "bin\\VslAtlasMonitor.exe"\r\n')
(out/'README.txt').write_text('驾驶细节分层V1\n提交：'+revision+'\n'
    '运行Run-DNA-Drive.cmd；默认停止／未点火／细节0%。\n'
    'A驻车四档、E车内两档与独立残差模型均已包含，音色待听评。\n'
    '33项回归及实际静音设备／UI检查通过；零量回到旧15输出，2/12通道源相同。\n'
    'evidence中含首轮占用失败、旧测量和最终controls_final/device_final/ui_final。\n'
    '仅最终子目录和docs摘要作为最终技术依据；尚非完整负载／工况、低频／进气／机械声层。\n'
    '不是新take产品格式或实际7.1.4听评；原始素材和旧系统沿用既有交接包。\n',encoding='utf-8')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
       for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.residual-atlas-freeze/1',source_commit=revision,
    human_accepted=False,summary_sha256=sha(summary),files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(row['bytes'] for row in files)),ensure_ascii=False))
