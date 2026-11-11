"""Freeze the reviewed V0.5 runtime and diagnostics without altering old versions."""
from pathlib import Path
import hashlib
import json
import shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'baselines/v0.5.0'
if OUT.exists():raise SystemExit('V0.5 exists: preserve it and use a new version.')
audit=json.loads((ROOT/'renders/v0.5.0/workspace_audit.json').read_text())
assert audit['result']=='pass' and audit['version']=='0.5.0' and audit['ctest_count']==7
for name,digest in audit['source_code'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
OUT.mkdir()
for folder in ['src','tests']:shutil.copytree(ROOT/folder,OUT/folder)
for name in ['CMakeLists.txt','build.ps1','Launch.cmd','README.md','AGENTS.md']:shutil.copy2(ROOT/name,OUT/name)
for folder in ['bin','research','tools','renders','diagnostics']:(OUT/folder).mkdir()
for name in ['VehicleSoundLab.exe','vsl_render.exe']:shutil.copy2(ROOT/'build-v05/Release'/name,OUT/'bin'/name)
for name in ['V05降挡与独立时钟.md','goal_progress_v05.json','state_evidence_v02.json']:
    shutil.copy2(ROOT/'research'/name,OUT/'research'/name)
for name in ['render_v05_review.py','make_v05_review.py','verify_v05.py','freeze_v05.py',
             'check_dna_pipeline.py','verify_review_player.cjs','capture_preview.py']:
    shutil.copy2(ROOT/'tools'/name,OUT/'tools'/name)
for name in ['verification.json','workspace_audit.json','ctest.xml','ui_smoke.json','browser_qa.json',
             'ui_native_preview.png','ui_detail.png','listening_desktop.png','listening_mobile.png','downshift_trace.png']:
    shutil.copy2(ROOT/'renders/v0.5.0'/name,OUT/'diagnostics'/name)
shutil.copy2(ROOT/'renders/v0.5.0/dna_check/dna_pipeline_check.json',OUT/'diagnostics/dna_pipeline_check.json')
source=ROOT/'renders/v0.5.0'
for file in sorted(source.glob('audition_*.wav')):shutil.copy2(file,OUT/'renders'/file.name)
for name in ['drive_v04.wav','drive_v05.wav','downshift_v05.wav','engineering_110Hz.dna',
             'drive_v05.csv','shifts_v05.csv','downshift_v05.csv','custom_dna_v05.csv']:
    shutil.copy2(source/name,OUT/'renders'/name)
files=[dict(path=str(p.relative_to(OUT)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
       for p in sorted(OUT.rglob('*')) if p.is_file()]
(OUT/'manifest.json').write_text(json.dumps(dict(version='v0.5.0',seed=48271,sample_rate=48000,
    status='Frozen review: independent crank/DNA clocks, bounded clutch matching and downshift blips. Broad sound/driving goal remains active.',
    upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',files=files),indent=2),encoding='utf-8')
for entry in files:assert hashlib.sha256((OUT/entry['path']).read_bytes()).hexdigest()==entry['sha256']
print('Frozen V0.5:',len(files),'files verified')
