"""Bind the residual experiment to verified code, models, audio and test evidence."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--reference', required=True, help='Git revision before adding residual C')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
root = args.workspace/'references/analysis/residual_osc_v1'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


build = read(root/'fitted/report.json')
verification = read(root/'controls/verification.json')
review = read(root/'review/review.json')
qa = read(root/'review/browser_qa.json')
assert verification['result'] == qa['result'] == 'pass'
assert not build['human_accepted'] and not verification['human_accepted']
assert verification['build_sha256'] == review['build_sha256'] == sha(root/'fitted/report.json')
probe = repo/'handoff-build/bin/Release/VslResidual_probe.exe'
assert build['probe_sha256'] == verification['probe_sha256'] == sha(probe)
for record in (build, verification):
    for name, expected in record['source_sha256'].items():
        assert sha(repo/name) == expected, name
assert qa['muted'] and qa['players'] == len(review['records']) == 10
assert qa['page_sha256'] == review['page_sha256'] == sha(review['page'])
assert qa['verifier_sha256'] == sha(repo/'tools/verify_residual_review_v1.cjs')
for item in review['records']:
    assert sha(root/'review'/item['file']) == item['sha256']
for name, case in build['cases'].items():
    assert sha(repo/'voices/residual_osc_v1'/(name+'.residual')) == case['profile_sha256']

revision = subprocess.check_output(['git', 'rev-parse', args.reference], cwd=repo, text=True).strip()
archive = subprocess.check_output(['git', 'archive', '--format=zip', revision], cwd=repo)
preserved = []
with zipfile.ZipFile(io.BytesIO(archive)) as files:
    for name in files.namelist():
        if Path(name).suffix in ('.c', '.h'):
            assert (repo/name).read_bytes() == files.read(name), name
            preserved.append(name)
test_source = repo/'handoff-build/Testing/Temporary/LastTest.log'
test_text = test_source.read_text(encoding='utf-8', errors='replace')
assert test_text.count('Test Passed.') == 31 and 'Test Failed.' not in test_text
test_target = root/'ctest.log'
if test_target.exists():
    assert sha(test_target) == sha(test_source), 'Use a new evidence directory for another test run'
else:
    shutil.copy2(test_source, test_target)

sources = [*repo.joinpath('modules/sound_residual').glob('*'),
           *repo.joinpath('experiments/residual_osc_v1').glob('*.c'),
           *repo.joinpath('tools/residual_osc_v1').glob('*.py'),
           *repo.joinpath('voices/residual_osc_v1').glob('*'),
           *[repo/'tools'/name for name in ('run_residual_osc_v1.py', 'verify_residual_osc_v1.py',
             'make_residual_review_v1.py', 'verify_residual_review_v1.cjs',
             'summarize_residual_osc_v1.py', 'freeze_residual_osc_v1.py')]]
evidence_names = ('fitted/report.json', 'controls/verification.json', 'review/review.json',
                  'review/browser_qa.json', 'review/desktop.png', 'review/mobile.png', 'ctest.log')
summary = dict(
    schema='vsl.residual-osc-summary/1', date='2026-11-11', result='pass',
    human_accepted=False, driving_attached=False, deployed_host_changed=False,
    existing_c_h_preservation=dict(reference_commit=revision, files=len(preserved), all_bytes_equal=True),
    ctest=dict(passed=31, failed=0, log_sha256=sha(test_target)),
    model=dict(rate=48000, bands=8, oscillators=512, bounded_pitch=[.9, 1.1]),
    real=verification['real'],
    cases={name: dict(source=case['source'], profile_sha256=case['profile_sha256'],
        clipped_coherence_bands=sum(row['coherence_clipped'] for row in case['rows']),
        training_before_db=[row['power_delta_db'] for row in case['before_error']],
        training_after_db=[row['power_delta_db'] for row in case['after_error']])
        for name, case in build['cases'].items()},
    limits=build['limits']+['No matched-loudness listening, fitted temporal envelope or physical object mapping',
                           'Independent additive residual cannot repair all existing DNA stereo covariance'],
    evidence_root=str(root), probe_sha256=sha(probe), review=review,
    source_sha256={p.relative_to(repo).as_posix(): sha(p) for p in sorted(sources) if p.is_file()},
    evidence_sha256={name: sha(root/name) for name in evidence_names})
target = repo/'research/residual_osc_v1_summary.json'
target.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(summary=str(target), ctest=summary['ctest'], preserved_c_h=len(preserved),
                      real=summary['real']), ensure_ascii=False))
