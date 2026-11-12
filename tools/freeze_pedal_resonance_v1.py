"""Freeze the verified pedal-state evidence and the exact committed source."""
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
s = json.loads((repo/'research/pedal_resonance_v1_summary.json').read_text(encoding='utf-8'))
assert s['result'] == 'pedal_state_replay_technical_pass' and not s['stable_idle_detail_output']
for name, digest in s['evidence_sha256'].items():
    assert sha(a.workspace/name) == digest, name
v = json.loads((a.workspace/'references/analysis/pedal_resonance_v1/verify1/report.json').read_text(encoding='utf-8'))
for name, digest in v['evidence_sha256'].items():
    assert sha(a.workspace/'references/analysis/pedal_resonance_v1/verify1'/name) == digest, name
out = a.workspace/'baselines/pedal_resonance_v1'
out.mkdir(exist_ok=False)
shutil.copytree(a.workspace/'references/analysis/pedal_resonance_v1', out/'evidence')
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
with zipfile.ZipFile(out/'source.zip') as archive:
    assert archive.testzip() is None
(out/'README.txt').write_text('Pedal-state and local-detail coverage diagnostic\n'
    'evidence/verify1 contains exact executed sources, both players, a self-contained schema6 take, stems and state trace.\n'
    'Take file: evidence/verify1/pedals/detail_schema6.vslrun\n'
    'This evidence proves stable850engineeringRPM idle has ZERO new detail; loaded acceleration support is also sparse.\n'
    'No new timbre acceptance, RPM calibration or parameter change.\n', encoding='utf-8')
files = [dict(path=v.relative_to(out).as_posix(), bytes=v.stat().st_size, sha256=sha(v))
         for v in sorted(out.rglob('*')) if v.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1', source_commit=commit,
    full_state_timbre_accepted=False, files=files), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
for row in files:
    assert sha(out/row['path']) == row['sha256']
print(json.dumps(dict(result='frozen', commit=commit, files=len(files), bytes=sum(v['bytes'] for v in files))))
