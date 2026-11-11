"""Freeze the committed self-contained recorder/player and its exact evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=repo/'research/atlas_take_v1_summary.json';r=json.loads(summary.read_text(encoding='utf-8'))
assert r['result']=='pass' and r['tests']==35 and not r['ui_interaction_verified']
root=Path(r['evidence_root'])
for path,digest in r['source_sha256'].items():assert sha(repo/path)==digest,path
for path,digest in r['evidence_sha256'].items():assert sha(root/path)==digest,path
for name,digest in r['binary_sha256'].items():assert sha(repo/'handoff-build/bin/Release'/name)==digest,name
assert sha(repo/'handoff/C文件索引.csv')==r['c_index_sha256']
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
out=args.workspace/'baselines/atlas_take_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence')
for folder in ('exterior_anchors_v1','cabin_anchors_v1','residual_atlas_v1'):
    shutil.copytree(repo/'voices'/folder,out/'voices'/folder)
(out/'bin').mkdir()
for name in r['binary_sha256']:shutil.copy2(repo/'handoff-build/bin/Release'/name,out/'bin'/name)
(out/'docs').mkdir()
for path in (summary,repo/'research/驾驶行程录制V1.md',repo/'handoff/C模块与接口.md',repo/'handoff/C文件索引.csv'):
    shutil.copy2(path,out/'docs'/path.name)
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
(out/'Run-DNA-Drive.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\nstart "" "bin\\VslAtlasMonitor.exe"\r\n')
(out/'README.txt').write_text('新DNA行程录制V1\n提交：'+revision+'\n运行Run-DNA-Drive.cmd，默认停止。\n'
    '新行程使用.vslrun，录制从第0帧开始。内嵌模型，无需原始素材回放。\n'
    'bin/VslAtlasTake_render.exe可将evidence/final/设备 行程.vslrun导出为2或12通道。\n'
    '35项回归及短时静音设备校验通过；新UI交互和目视验证待完成，音色验收未扩大。\n'
    '本目录是研究分支增量，未上传旧Release。\n',encoding='utf-8',newline='\n')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.atlas-take-freeze/1',source_commit=revision,ui_verified=False,files=files),
    ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for f in files:assert sha(out/f['path'])==f['sha256']
print(json.dumps(dict(path=str(out),files=len(files),bytes=sum(f['bytes'] for f in files),commit=revision),ensure_ascii=False))
