"""Freeze a review candidate after verification; never overwrite a baseline."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'baselines/v0.3.0'
if out.exists():raise SystemExit('Baseline already exists; preserve it and increment the version.')
audit=json.loads((ROOT/'renders/v0.3.0/workspace_audit.json').read_text())
assert audit['result']=='pass' and audit['device']['dsp']=='0.3.0'
out.mkdir()
for folder in ['src','tests']:
    shutil.copytree(ROOT/folder,out/folder)
for name in ['CMakeLists.txt','README.md','AGENTS.md','Launch.cmd','build.ps1']:
    shutil.copyfile(ROOT/name,out/name)
for folder in ['tools','research','diagnostics','bin','renders']:(out/folder).mkdir()
for name in ['render_v03_review.py','make_v03_review.py','finalize_v03_review.py','verify_v03.py','freeze_v03.py','analyze_state_transitions.py']:
    shutil.copyfile(ROOT/'tools'/name,out/'tools'/name)
for name in ['V03状态分层实现.md','state_evidence_v02.json','状态分层核查与下一轮标定.md','goal_progress_v03.json']:
    shutil.copyfile(ROOT/'research'/name,out/'research'/name)
for name in ['ui_smoke.json','ctest.xml','dna_pipeline_check.json','ui_detail.png','ui_listening.png']:
    shutil.copyfile(ROOT/'renders/v0.3.0'/name,out/'diagnostics'/name)
for name in ['VehicleSoundLab.exe','vsl_render.exe']:
    shutil.copyfile(ROOT/'build/Release'/name,out/'bin'/name)
for name in ['v10_drive.wav','v10_lift.wav','v10_shifts.wav','v10_neutral.wav','v10_5000_loaded.wav',
             'v10_drive.csv','v10_lift.csv','v10_shifts.csv','verification.json']:
    shutil.copyfile(ROOT/'renders/v0.3.0'/name,out/'renders'/name)
files=[dict(path=str(p.relative_to(out)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
       for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(version='v0.3.0',seed=48271,sample_rate=48000,
    status='Frozen review candidate. Subjective naturalness and Lamborghini calibration remain open.',
    upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',files=files),indent=2),encoding='utf-8')
print('Frozen v0.3.0:',len(files),'files')
