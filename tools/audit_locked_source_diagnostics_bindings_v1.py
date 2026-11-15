"""Independent archive bindings and scope; generic byte/ZIP audit is separate."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'out'): parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    proof = read(args.root/'validation.json'); evidence = args.root/'evidence'
    for original, relative in proof['input_archive_locations'].items():
        assert digest(original) == digest(args.root/'inputs'/relative)
    source = read(evidence/'virtual_known1/report.json')
    prior = read(evidence/'virtual_known_audit1/report.json')
    stereo = read(evidence/'virtual_stereo_audit1/report.json')
    references = read(evidence/'native_references1/report.json')
    assert prior['result'] == 'independent_locked_source_virtual_verified' and prior['all_consumer_checks_passed']
    assert prior['producer_sha256'] == stereo['producer_sha256'] == digest(evidence/'virtual_known1/report.json')
    assert stereo['result'] == 'independent_locked_source_virtual_stereo_verified' and stereo['all_stereo_checks_passed']
    assert stereo['prior_audit_sha256'] == digest(evidence/'virtual_known_audit1/report.json')
    assert len(source['cases']) == len(prior['cases']) == len(stereo['cases']) == 3
    assert len(source['guard_rejections']) == 6
    assert sum(row['signed_linear_changes_checked'] for row in prior['cases']) == proof['signed_linear_values'] == 10656
    assert sum(len(row['observations']) for row in stereo['cases']) == proof['direct_stereo_observations'] == 12
    assert max(stereo['maximum_errors'].values()) == proof['maximum_stereo_error'] < 2e-11
    assert references['all_reference_checks_passed'] and len(references['cases']) == 5
    assert references['no_terminal_fit_admission_or_render_qualification']
    assert all(not row['fitted_native_admission_exercised'] for row in references['cases'])
    assert not proof['actual_new_fit_admission_exercised'] and not proof['actual_new_fitted_native_render_qualified']
    assert proof['retained_legacy_cross_FFT_normalized_failures'] == 5
    spec = read(evidence/'real_launch_spec.json')
    assert spec['declared_cases'] == ['F3 Fifth First Mid'] and len(spec['sources']) == 124 and len(spec['inputs']) == 101
    repo = Path(__file__).resolve().parents[1]
    for name, wanted in spec['sources'].items(): assert digest(repo/name) == wanted
    for path, wanted in spec['inputs'].items(): assert digest(path) == wanted
    assert proof['real_job_observation']['ProcessId'] == 65232
    assert 'run_locked_source_real_v1.py' in proof['real_job_observation']['CommandLine']
    assert proof['original_first_case_never_refit'] and proof['original_jobs_not_restarted']
    result = dict(result='independent_locked_source_diagnostics_bindings_verified', all_bindings_verified=True,
        manifest_sha256=digest(args.root/'manifest.json'), input_count=len(proof['input_archive_locations']),
        actual_new_native_fit_qualified=False, full_goal_not_completed=True, auditor_sha256=digest(__file__))
    args.out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result['result'], result['input_count'], flush=True)


if __name__ == '__main__': main()
