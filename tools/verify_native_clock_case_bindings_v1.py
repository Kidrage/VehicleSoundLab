"""Independent binding and retained-failure verification for audit controls."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()

    def load(path):
        return json.loads(Path(path).read_text(encoding='utf-8'))

    def sha(path):
        with Path(path).open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()

    v = load(a.archive / 'validation.json')
    e = a.archive / 'evidence'
    reports = {name: load(e / name / 'report.json') for name in v['selected_terminal_evidence_directories']}
    assert all(reports[name]['result'] == 'failed' for name in ('controls1', 'controls2', 'controls3'))
    good = reports['controls4']
    assert good['result'] == 'native_clock_case_audit_equations_controls_verified' and good['all_controls_passed']
    assert len(good['cases']) == 19 and all(c['all_checks_passed'] for c in good['cases'])
    assert sum(c['kind'] == 'qualified_analytic_control' for c in good['cases']) == 13
    assert sum(c['kind'] == 'actual_raw_and_source_FIR_only' for c in good['cases']) == 6
    assert good['no_actual_fit_binding_or_render_qualification']
    checked = 0
    for folder, report in reports.items():
        for name, digest in report.get('inputs', {}).items():
            path = a.archive / v['original_input_archive_locations'][name]
            assert path.resolve().is_relative_to(a.archive.resolve()) and sha(path) == digest
            checked += 1
        for name, digest in report.get('sources', {}).items():
            assert sha(e / folder / 'exact_sources' / name) == v['executed_source_versions'][name][folder] == digest
        for c in report.get('cases', []):
            assert sha(e / folder / c['file']) == c['sha256']
        if 'file' in report:
            assert sha(e / folder / report['file']) == report['sha256']
    diagnosis = load(e / 'roundoff1/window_diagnosis.json')
    assert not diagnosis['normalized_cross_FFT_all_qualified']
    assert diagnosis['failed_attempt_report_sha256'] == sha(e / 'controls3/report.json')
    assert diagnosis['original_normalized_gate'] == 2e-11
    assert diagnosis['Hann_vector_max_difference'] == 2.220446049250313e-16
    same, different = diagnosis['window_diagnosis']
    assert max(abs(x - y) for x, y in zip(same['NRMSE_norm'], same['NRMSE_sum'])) < 2e-11
    assert max(abs(x - y) for x, y in zip(same['NRMSE_sum'], different['NRMSE_sum'])) > 2e-11
    reproduced = reports['roundoff2']
    assert reproduced['result'] == 'native_clock_case_Hann_operator_discrepancy_reproduced'
    assert reproduced['same_Hann_cross_FFT_spectra_bitwise_equal']
    assert not reproduced['normalized_cross_FFT_all_qualified']
    assert reproduced['no_old_line_failure_relabel_or_gate_change']
    assert reproduced['window_diagnosis'] == diagnosis['window_diagnosis']
    for name, digest in v['current_source_sha256'].items():
        assert sha(a.archive / 'source' / name) == digest
    assert v['C_H_exact'] == 670 and v['voice_parameters_exact'] == 82 and v['F2_files_exact'] == 3
    assert not v['actual_terminal_fit_admission_exercised'] and not v['actual_fitted_native_render_qualified']
    assert v['protected_run_spec_sources'] == 96 and v['protected_run_spec_inputs'] == 71
    assert {p.name for p in e.iterdir() if p.is_dir()} == set(v['selected_terminal_evidence_directories'])
    for original in v['original_input_archive_locations']:
        if '/waveform_file_real_v1/real1/' in original.replace('\\', '/'):
            assert Path(original).name == 'run_spec.json'
    assert v['real_job_observation']['process_live'] and v['real_job_observation']['pid'] == 245372
    r = dict(result='independent_native_clock_case_control_bindings_verified', all_bindings_verified=True,
        checked_bindings=checked, analytic_controls=13, actual_raw_interval_controls=6,
        retained_failed_attempts=3, actual_fitted_native_qualification_claimed=False,
        manifest_sha256=sha(a.archive / 'manifest.json'), auditor_sha256=sha(__file__))
    a.out.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
