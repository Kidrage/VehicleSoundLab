"""Bind technical success separately from the unestablished timbre hypothesis."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--reference', required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
root = args.workspace/'references/analysis/residual_motion_v1'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


fit = read(root/'fit1/report.json')
v = read(root/'verification2/verification.json')
review = read(root/'review1/review.json')
qa = read(root/'review1/browser_qa.json')
assert v['result'] == qa['result'] == 'pass'
assert v['fit_sha256'] == review['fit_sha256'] == sha(root/'fit1/report.json')
assert review['verification_sha256'] == sha(root/'verification2/verification.json')
assert qa['page_sha256'] == review['page_sha256'] == sha(review['page'])
assert qa['verifier_sha256'] == sha(repo/'tools/verify_residual_motion_review_v1.cjs')
assert qa['muted'] and qa['players'] == len(review['records']) == 7
for stage, report in (('fit1', fit), ('verification2', v)):
    for name, digest in report['source_sha256'].items():
        assert sha(repo/name) == sha(root/stage/'exact_sources'/name) == digest, name
for row in review['records']:
    assert sha(root/'review1'/row['file']) == row['sha256']
assert sha(root/'verification2/binaries/VslResidualMotion_probe.exe') == v['probe_sha256']
assert sha(root/'verification2/binaries/VslResidual_probe.exe') == v['static_probe_sha256'] == fit['probe_sha256']
for name, key in (('A_moving.residual', 'static_model_sha256'), ('A_moving.motion', 'motion_model_sha256')):
    assert sha(root/'fit1'/name) == sha(repo/'voices/residual_motion_v1'/name) == fit[key]

revision = subprocess.check_output(['git', 'rev-parse', args.reference], cwd=repo, text=True).strip()
archive = subprocess.check_output(['git', 'archive', '--format=zip', revision], cwd=repo)
preserved = []
with zipfile.ZipFile(io.BytesIO(archive)) as files:
    for name in files.namelist():
        if Path(name).suffix in ('.c', '.h'):
            assert (repo/name).read_bytes() == files.read(name), name
            preserved.append(name)
log = root/'ctest_38_LastTest.log'
text = log.read_text(encoding='utf-8', errors='replace')
assert text.count('Test Passed.') == 38 and 'Test Failed.' not in text

assessment = []
for row in v['real_context_assessment']:
    before, after = row['mean_covariance_distance_static'], row['mean_covariance_distance_motion']
    assessment.append(dict(name=row['name'], static=before, motion=after,
                           reduction_percent=100*(before-after)/before))
sources = [*repo.joinpath('modules/residual_motion').glob('*'),
           *repo.joinpath('experiments/residual_motion_v1').glob('*.c'),
           *repo.joinpath('tools/residual_motion_v1').glob('*.py'),
           *repo.joinpath('voices/residual_motion_v1').glob('*'),
           *[repo/'tools'/name for name in ('fit_residual_motion_v1.py', 'verify_residual_motion_v1.py',
             'make_residual_motion_review_v1.py', 'verify_residual_motion_review_v1.cjs',
             'summarize_residual_motion_v1.py', 'freeze_residual_motion_v1.py')],
           repo/'handoff/CMakeLists.txt', repo/'handoff/tools/index_sources.py']
evidence = [p for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
summary = dict(schema='vsl.residual-motion-summary/1', date='2026-11-12',
    technical_validation='pass', real_context_timbre_improvement='not_established',
    human_accepted=False, driving_attached=False, deployed_host_changed=False,
    context=fit['provenance'], ctest=dict(passed=38, failed=0, log_sha256=sha(log)),
    existing_c_h_preservation=dict(reference_commit=revision, files=len(preserved), all_bytes_equal=True),
    bounded_pitch=[.9, 1.1], zero_and_raw_exact=v['pitch_checks'],
    known_stereo_max_power_delta_db=max(abs(d) for case in v['known'] for row in case['comparison'] for d in row['power_delta_db']),
    known_stereo_max_coherence_change=max(row['complex_coherence_error'] for case in v['known'] for row in case['comparison']),
    expected_envelope_variance=v['expected_envelope_variance'],
    measured_envelope_variance=v['measured_envelope_variance'],
    measured_envelope_mean_square=v['measured_envelope_mean_square'],
    envelope_observation='CSV samples are at interpolation knots; moments do not measure all intermediate samples',
    procedural_seed_assessment=assessment,
    assessment_scope='Same1.217s real reference and new procedural seeds, not unseen-recording validation. No preregistered perceptual threshold.',
    interpretation='At most0.67% covariance-distance decrease, including one small increase; clear timbre improvement not established.',
    common_bound_scale=fit['temporal']['common_bound_scale'],
    negative_covariance_eigenvalue_mass=fit['temporal']['negative_eigenvalue_mass'],
    failures=['verification1: wrong probe executable path; original script and known error retained'],
    evidence_root=str(root), review=review,
    source_sha256={p.relative_to(repo).as_posix(): sha(p) for p in sorted(sources) if p.is_file()},
    evidence_sha256={p.relative_to(root).as_posix(): sha(p) for p in evidence},
    limits=fit['limits']+v['limits']+[
        'Positive mean power debt is absent in6–8kHz; this context does not support unconditional high-frequency boost',
        'The accepted moving A observation is effectively mono; no measured stereo widening claim',
        'Known-stereo controls are synthetic, distinct from the near-mono real reference',
        'Mean-power preservation is expected statistically, not guaranteed for every finite render',
        'No new event/state sound, physical source separation,7.1.4 listening or device-budget result'])
target = repo/'research/residual_motion_v1_summary.json'
target.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(summary=str(target), ctest=summary['ctest'], preserved_c_h=len(preserved),
                      assessment=assessment), ensure_ascii=False))
