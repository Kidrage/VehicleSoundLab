"""Freeze driving evidence / provisional profiles without copying large PSDs twice."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args()
repository=Path(__file__).resolve().parents[1]
if subprocess.check_output(['git','status','--porcelain'],cwd=repository).strip():
    raise RuntimeError('Commit validated work first')
source=args.workspace/'references/analysis/drive_evidence_v1'
observation=json.loads((source/'observed/observations.json').read_text(encoding='utf-8'))
summary=json.loads((source/'summary_v3/report.json').read_text(encoding='utf-8'))
verification=json.loads((source/'summary_v3/verification.json').read_text(encoding='utf-8'))
anchors=json.loads((source/'cabin_anchors_tapered/build.json').read_text(encoding='utf-8'))
anchor_check=json.loads((source/'cabin_anchors_tapered/verification.json').read_text(encoding='utf-8'))
controls=json.loads((source/'windowed_controls.json').read_text(encoding='utf-8'))
assert verification['result']==anchor_check['result']==controls['result']=='pass'
assert verification['summary_sha256']==sha(source/'summary_v3/report.json')
assert anchor_check['build_sha256']==sha(source/'cabin_anchors_tapered/build.json')
assert anchors['summary_sha256']==sha(source/'summary_v3/report.json')
for record,prefix in [(observation,'tools'),(verification,''),(anchors,'tools')]:
    for name,expected in record['tools_sha256'].items():
        assert sha(repository/prefix/name)==expected,name
for row in anchors['anchors']:
    assert sha(repository/'voices/cabin_anchors_v1'/(row['name']+'.model'))==row['model_sha256']
probe=repository/'handoff-build/bin/Release/VslSoundDna_probe.exe'
assert sha(probe)==anchors['c_probe_sha256']
for name in ('verify_cabin_anchors_v1.py','verify_dna_windowed_v1.py'):
    record=anchor_check if name.startswith('verify_cabin') else controls
    assert sha(repository/'tools'/name)==record['verifier_sha256']
# Current realtime C / binaries still match the preceding validated host.
prior=json.loads((args.workspace/'references/analysis/scene_monitor_v1/report.json').read_text(encoding='utf-8'))
for name,expected in prior['source_sha256'].items():assert sha(repository/name)==expected,name
for name,expected in prior['binary_sha256'].items():assert sha(repository/'handoff-build/bin/Release'/name)==expected,name
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True).strip()
destination=args.workspace/'baselines/drive_evidence_v1'
destination.mkdir(exist_ok=False)
external=[]
for path in source.rglob('*'):
    if not path.is_file():continue
    relative=path.relative_to(source)
    if path.name=='audio.npz' and 'observed' in relative.parts:
        external.append(dict(path=str(path.relative_to(args.workspace)).replace('\\','/'),bytes=path.stat().st_size,sha256=sha(path)))
    else:
        target=destination/'evidence'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
shutil.copytree(repository/'voices/cabin_anchors_v1',destination/'voices/cabin_anchors_v1')
(destination/'bin').mkdir()
shutil.copy2(probe,destination/'bin'/probe.name)
(destination/'docs').mkdir()
for name in ('驾驶素材与DNA锚点V1.md','drive_evidence_v1_annotations.json','drive_evidence_v1_summary.json'):
    shutil.copy2(repository/'research'/name,destination/'docs'/name)
subprocess.run(['git','archive','--format=zip','--output='+str(destination/'source.zip'),revision],cwd=repository,check=True)
(destination/'README.txt').write_text('驾驶素材与DNA锚点V1\n源码提交：'+revision+'\n'
    'C运行时和已认可默认音色保持原样。voices/包含两档未听评的E车内模型。\n'
    '可在既有联合监听窗口“载入DNA”逐个载入；不要叠加A车外低频。\n'
    'evidence/cabin_anchors为高频泄漏的初版对照；cabin_anchors_tapered为修订候选。\n'
    'evidence/summary_v3为当前状态证据；summary和summary_v2保留初始失败。\n'
    '原始素材继续引用既有批准主文件，不重复放入本包。六个大型PSD矩阵保留原位，manifest.external_payloads逐一绑定。\n'
    '本包不是完整宽RPM驾驶接入，也不是主观真实度验收。\n',encoding='utf-8')
files=[dict(path=str(p.relative_to(destination)).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p))
       for p in destination.rglob('*') if p.is_file()]
manifest=dict(schema='vsl.drive-evidence-freeze/1',source_revision=revision,files=files,external_payloads=external,
    status='Five audiovisual shift contexts and two C-loaded experimental profiles; listening, phase-aligned atlas and driving integration pending')
(destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:assert sha(destination/row['path'])==row['sha256']
for row in external:assert sha(args.workspace/row['path'])==row['sha256']
print(json.dumps(dict(destination=str(destination),revision=revision,verified_files=len(files),external_matrices=len(external),copied_bytes=sum(r['bytes'] for r in files))))
