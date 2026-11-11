"""Freeze validated atlas/driving sources, binary, renders and intermediate evidence."""
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
    raise RuntimeError('Commit validated source and documentation first')
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip()
source=args.workspace/'references/analysis/atlas_drive_v1'
verified=source/'final_v3'
record=json.loads((verified/'verification.json').read_text(encoding='utf-8'))
review=json.loads((verified/'audition/review.json').read_text(encoding='utf-8'))
assert record['result']=='pass' and record['accepted'] is False
assert sha(repository/'handoff-build/bin/Release/VslAtlasDrive_probe.exe')==record['probe_sha256']
for paths in ('model_sha256','source_sha256'):
    for name,expected in record[paths].items():assert sha(repository/name)==expected,name
assert sha(repository/'tools/verify_atlas_drive_v1.py')==record['verifier_sha256']
bound_records=[verified/'verification.json',*verified.glob('verification_*.json')]
assert any(sha(path)==review['verification_sha256'] for path in bound_records)
assert review['builder_sha256']==sha(repository/'tools/make_atlas_drive_review_v1.py')
assert sha(review['page'])==review['page_sha256']
for row in record['runs']:
    command=json.loads((verified/(row['name']+'_command.json')).read_text(encoding='utf-8'))
    assert command['probe_sha256']==record['probe_sha256']
    for filename,expected in command['outputs_sha256'].items():assert sha(verified/filename)==expected,filename
for row in review['records']:
    assert sha(verified/'audition'/(row['name']+'.wav'))==row['sha256']
    assert sha(verified/(row['name']+'_render.wav'))==row['source_sha256']

# Old accepted context is preserved, independent of the new cabin bank.
for name,expected in {
    'voices/dna_bank_v1/V10 Exterior.model':'6f8992e6674f603334f82bdbc526fd8ac5bbe750606154c5e83c166c077bb1b7',
    'voices/coherent_low_v1/measured_phase.model':'9e456a4198bce540a4ccc60220b9cf86e40dc80eadc8d1c2904dc5248715e895'
}.items():assert sha(repository/name)==expected,name
test_log=repository/'handoff-build/Testing/Temporary/LastTest.log'
log=test_log.read_bytes().decode('utf-8',errors='replace')
assert log.count('Test Passed.')==29 and 'Test Failed.' not in log

destination=args.workspace/'baselines/atlas_drive_v1'
destination.mkdir(exist_ok=False)
shutil.copytree(verified,destination/'evidence')
(destination/'bin').mkdir()
for path in [repository/'handoff-build/bin/Release/VslAtlasDrive_probe.exe',
    repository/'handoff-build/Release/VslAtlas_checks.exe',repository/'handoff-build/Release/VslAtlasDrive_checks.exe']:
    shutil.copy2(path,destination/'bin'/path.name)
shutil.copytree(repository/'voices/cabin_anchors_v1',destination/'voices/cabin_anchors_v1')
(destination/'docs').mkdir()
shutil.copy2(repository/'research/多锚点驾驶接入V1.md',destination/'docs')
shutil.copy2(repository/'research/atlas_drive_v1_summary.json',destination/'docs')
shutil.copy2(review['page'],destination/'review-source.html')
shutil.copy2(test_log,destination/'LastTest.log')
subprocess.run(['git','archive','--format=zip','--output='+str(destination/'source.zip'),revision],cwd=repository,check=True)
with zipfile.ZipFile(destination/'source.zip') as archive:assert archive.testzip() is None
# Standalone package page uses its own evidence, without depending on localhost.
original=Path(review['page']).read_text(encoding='utf-8')
prefix='../'+verified.relative_to(args.workspace).as_posix()+'/'
assert original.count(prefix)==8
(destination/'review.html').write_text(original.replace(prefix,'evidence/'),encoding='utf-8')
(destination/'README.txt').write_text('多锚点驾驶接入V1\n源码提交：'+revision+'\n'
    '打开review.html可试听。本包为未获听评的E车内两锚点驾驶实验，不能代替A车外认可基线。\n'
    'evidence/包含原始float分轨、200Hz遥测、配置与验证；高度在room0时静音。\n'
    '可选事件仍为旧程序合成；独立车内低频、进气、噪声和原生驾驶UI未完成。\n'
    '所有输出非旧take格式；旧DSP0.20.0和take schema5保持独立。\n',encoding='utf-8')
external=[]
for path in source.rglob('*'):
    if not path.is_file() or path.is_relative_to(verified):continue
    external.append(dict(path=path.relative_to(args.workspace).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
files=[dict(path=p.relative_to(destination).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
    for p in destination.rglob('*') if p.is_file()]
manifest=dict(schema='vsl.atlas-drive-freeze/1',source_commit=revision,accepted=False,
    validation_sha256=sha(verified/'verification.json'),files=files,external_payloads=external,
    intermediate_policy='Preserve initial partial exports and earlier complete pre-hardening runs at original paths; do not use as final validation')
(destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
for row in files:assert sha(destination/row['path'])==row['sha256']
print(json.dumps(dict(path=str(destination),commit=revision,files=len(files),
    bytes=sum(f['bytes'] for f in files),external_files=len(external)),ensure_ascii=False))
