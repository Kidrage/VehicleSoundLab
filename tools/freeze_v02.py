"""Freeze an immutable review baseline. Do not overwrite prior versions."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];version='v0.2.0';out=ROOT/'baselines'/version
if out.exists():raise SystemExit('Baseline exists: preserve it; intentional sound revisions need a new version.')
old=ROOT/'baselines/v0.1.0';manifest=json.loads((old/'manifest.json').read_text())
for item in manifest['files']:
    assert hashlib.sha256((old/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
out.mkdir();shutil.copytree(ROOT/'src',out/'src');shutil.copytree(ROOT/'tests',out/'tests')
for name in ['CMakeLists.txt','README.md','AGENTS.md']:shutil.copyfile(ROOT/name,out/name)
(out/'research').mkdir()
for name in ['V6方法论与V02实现.md','state_evidence_v02.json','v6_control_snapshot.json','backend_polling_observation.json']:
    shutil.copyfile(ROOT/'research'/name,out/'research'/name)
(out/'tools').mkdir()
for name in ['render_v02_review.py','make_v02_review.py','analyze_states_space.py','hybrid_experiment.py','sinusoidal_experiment.py','verify_v02.py']:
    shutil.copyfile(ROOT/'tools'/name,out/'tools'/name)
(out/'diagnostics').mkdir()
for name in ['ui_smoke.json','dna_pipeline_check.json']:
    shutil.copyfile(ROOT/'renders'/name,out/'diagnostics'/name)
(out/'bin').mkdir()
for name in ['VehicleSoundLab.exe','vsl_render.exe']:shutil.copyfile(ROOT/'build/Release'/name,out/'bin'/name)
for name in ['v10_drive_stereo.wav','v10_5000_light.wav','v10_5000_loaded.wav','v10_5000_overrun.wav','verification.json','scene.json','v10_drive_trace.csv']:
    shutil.copyfile(ROOT/'renders/v0.2.0'/name,out/name)
files=[dict(path=str(p.relative_to(out)).replace('\\','/'),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(version=version,seed=48271,sample_rate=48000,
    status='Review baseline; Lamborghini state/RPM/load calibration and subjective realism acceptance remain open.',
    upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',files=files),indent=2),encoding='utf-8')
print('Frozen',version,'files',len(files),'previous baseline hashes unchanged')
