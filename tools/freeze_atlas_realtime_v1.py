"""Freeze the new native driving monitor with models and all iteration evidence."""
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
repository=Path(__file__).resolve().parents[1]
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
if subprocess.check_output(['git','status','--porcelain'],cwd=repository).strip():
    raise RuntimeError('Commit final validated source and documentation first')
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip()
summary=repository/'research/atlas_realtime_v1_summary.json'
report=json.loads(summary.read_text(encoding='utf-8'))
assert report['result']=='pass' and not report['human_accepted']
root=args.workspace/'references/analysis/atlas_realtime_v1'
assert str(root)==report['evidence_root']
for name,expected in report['source_sha256'].items():assert sha(repository/name)==expected,name
for name,expected in report['evidence_sha256'].items():assert sha(root/name)==expected,name
for name,expected in report['binaries_sha256'].items():assert sha(repository/'handoff-build/bin/Release'/name)==expected,name
test=repository/'handoff-build/Testing/Temporary/LastTest.log'
assert sha(test)==report['test_log_sha256']
assert sha(repository/'handoff/C文件索引.csv')==report['c_index_sha256']
destination=args.workspace/'baselines/atlas_realtime_v1'
destination.mkdir(exist_ok=False)
shutil.copytree(root,destination/'evidence')
for bank in ('exterior_anchors_v1','cabin_anchors_v1'):
    shutil.copytree(repository/'voices'/bank,destination/'voices'/bank)
(destination/'bin').mkdir()
for name in report['binaries_sha256']:
    shutil.copy2(repository/'handoff-build/bin/Release'/name,destination/'bin'/name)
shutil.copy2(repository/'handoff-build/Release/VslAtlasMonitor_checks.exe',destination/'bin')
(destination/'docs').mkdir()
for p in (summary,repository/'research/DNA驾驶原生监听V1.md',repository/'handoff/C模块与接口.md',repository/'handoff/C文件索引.csv'):
    shutil.copy2(p,destination/'docs'/p.name)
shutil.copy2(test,destination/'LastTest.log')
subprocess.run(['git','archive','--format=zip','--output='+str(destination/'source.zip'),revision],cwd=repository,check=True)
with zipfile.ZipFile(destination/'source.zip') as archive:assert archive.testzip() is None
(destination/'Run-DNA-Drive.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\nstart "" "bin\\VslAtlasMonitor.exe"\r\n')
(destination/'README.txt').write_text('DNA驾驶原生监听V1\n源码提交：'+revision+'\n'
    '运行Run-DNA-Drive.cmd，默认停止，先开始监听再点火。A驻车四档／E车内两档仍为实验音色。\n'
    '本包可独立运行新驾驶窗口；完整旧系统、原始音视频和Python依赖沿用既有完整交接包。\n'
    'evidence/cache为冻结声音对照；device_final／ui_final／build_final.log为最终技术依据。\n'
    '早期失败与中间截图保留在其余目录，不作为最终布局或设备验收。\n'
    '14组源音频一致；30项回归；本机短时静音设备与采用帧重合成通过。\n'
    '未完成长期稳定性、完整工况／低频／噪音声层、用户听评及新驾驶产品录制格式。\n',encoding='utf-8')
files=[dict(path=p.relative_to(destination).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
    for p in sorted(destination.rglob('*')) if p.is_file()]
manifest=dict(schema='vsl.atlas-realtime-freeze/1',source_commit=revision,human_accepted=False,
    summary_sha256=sha(summary),files=files)
(destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
for row in files:assert sha(destination/row['path'])==row['sha256']
print(json.dumps(dict(path=str(destination),commit=revision,files=len(files),bytes=sum(f['bytes'] for f in files)),ensure_ascii=False))
