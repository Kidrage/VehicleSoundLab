"""Immutable review snapshot; refuse to overwrite a previously frozen V0.4."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'baselines/v0.4.0'
if OUT.exists():raise SystemExit('V0.4 exists: preserve it and use a new version.')
audit=json.loads((ROOT/'renders/v0.4.0/workspace_audit.json').read_text())
assert audit['result']=='pass' and audit['version']=='0.4.0' and audit['ctest_count']==5
OUT.mkdir()
for folder in ['src','tests']:shutil.copytree(ROOT/folder,OUT/folder)
for name in ['CMakeLists.txt','build.ps1','Launch.cmd','README.md','AGENTS.md']:shutil.copy2(ROOT/name,OUT/name)
for folder in ['bin','research','tools','renders','diagnostics']:(OUT/folder).mkdir()
for name in ['VehicleSoundLab.exe','vsl_render.exe']:shutil.copy2(ROOT/'build-v04/Release'/name,OUT/'bin'/name)
for name in ['V04高阶声源实现.md','goal_progress_v04.json','state_evidence_v02.json']:
    shutil.copy2(ROOT/'research'/name,OUT/'research'/name)
for name in ['render_v04_review.py','make_v04_review.py','verify_v04.py','freeze_v04.py','analyze_multires_osc.py','check_dna_pipeline.py','verify_review_player.cjs']:
    shutil.copy2(ROOT/'tools'/name,OUT/'tools'/name)
shutil.copytree(ROOT/'tools/osc_research',OUT/'tools/osc_research',ignore=shutil.ignore_patterns('__pycache__'))
for name in ['verification.json','workspace_audit.json','ctest.xml','ui_smoke.json','browser_qa.json',
             'ui_native_preview.png','ui_detail.png','listening_desktop.png','listening_mobile.png']:
    shutil.copy2(ROOT/'renders/v0.4.0'/name,OUT/'diagnostics'/name)
shutil.copy2(ROOT/'renders/v0.4.0/dna_check/dna_pipeline_check.json',OUT/'diagnostics/dna_pipeline_check.json')
shutil.copy2(ROOT/'references/analysis/multires_v1/results.json',OUT/'research/multires_results.json')
for name in ['drive_v03.wav','drive_v04.wav','2500_v04.wav','5000_v04.wav','8000_v04.wav','pure5000_v04.wav',
             'lift_v04.wav','shifts_v04.wav','drive_v04.csv','lift_v04.csv','shifts_v04.csv']:
    shutil.copy2(ROOT/'renders/v0.4.0'/name,OUT/'renders'/name)
files=[dict(path=str(p.relative_to(OUT)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
       for p in sorted(OUT.rglob('*')) if p.is_file()]
(OUT/'manifest.json').write_text(json.dumps(dict(version='v0.4.0',seed=48271,sample_rate=48000,
    status='Frozen review candidate: phase-consistent dense V10 high orders. Full sound/driving objective remains active.',
    upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',files=files),indent=2),encoding='utf-8')
print('Frozen V0.4:',len(files),'files')
