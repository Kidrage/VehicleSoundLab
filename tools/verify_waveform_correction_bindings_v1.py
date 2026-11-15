"""Independent archive bindings, unchanged gates and resource arithmetic."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()

    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))

    def sha(path):
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()

    e = a.archive/'evidence'; v = read(a.archive/'validation.json')
    assert {p.name for p in e.iterdir() if p.is_dir()} == set(v['selected_terminal_evidence_directories'])
    parents = {}
    for name, digest in v['upstream_manifests_sha256'].items():
        path = a.archive/f'inputs/upstream/{name}/manifest.json'; assert sha(path) == digest
        parents[name] = {r['path']: r['sha256'] for r in read(path)['files']}
    sources = inputs = cases = 0
    for folder in v['selected_terminal_evidence_directories']:
        r = read(e/folder/'report.json')
        for name, digest in r.get('inputs', {}).items():
            target = v['original_input_archive_locations'][name]
            assert sha(a.archive/target) == digest
            parts = Path(target).parts
            if parts[:2] == ('inputs', 'upstream'):
                leaf = Path(*parts[3:]).as_posix()
                assert (v['upstream_manifests_sha256'][parts[2]] if leaf == 'manifest.json'
                        else parents[parts[2]][leaf]) == digest
            inputs += 1
        for name, digest in r.get('sources', {}).items():
            assert sha(e/folder/'exact_sources'/name) == digest; sources += 1
        for key in ('cases', 'inverse_cases', 'original_cases'):
            for case in r.get(key, []):
                if 'file' in case and 'sha256' in case:
                    assert sha(e/folder/case['file']) == case['sha256']; cases += 1

    def report(name):
        return read(e/name/'report.json')

    controls = report('controls_audit1')
    assert controls['result'] == 'independent_waveform_original_correction_controls_passed'
    assert controls['all_qualified'] and len(controls['inverse_cases']) == v['inverse_controls_qualified'] == 8
    assert len(controls['original_cases']) == v['original_arbitrary_controls_qualified'] == 7
    assert controls['producer_sha256'] == sha(e/'controls1/report.json')
    assert controls['auditor_sha256'] == sha(e/'controls_audit1/executed_audit.py')
    for producer, auditor, count in (('known1', 'known_audit1', 12), ('shared1', 'shared_audit1', 8)):
        source, audit = report(producer), report(auditor)
        assert source['result'] == 'waveform_original_operator_correction_known_measured'
        assert audit['result'] == 'independent_waveform_original_correction_known_verified'
        assert source['fixed_correction_steps'] == v['fixed_correction_steps'] == 2
        assert source['pass_count'] == audit['pass_count'] == count
        assert audit['producer_sha256'] == sha(e/producer/'report.json')
        assert audit['auditor_sha256'] == sha(e/auditor/'executed_audit.py')
        assert source['all_qualified'] and audit['all_qualified']
        assert len(source['cases']) == len(audit['cases']) == count
        for case in audit['cases']:
            assert case['qualified'] and case['stable_complete_normal'] <= 1e-11
            assert case['original_gradient'] < 2e-7 and case['dense_relative_error'] < 2e-7
            assert case['original_backward'] <= 1e-11
            assert all(c['passed'] for c in case['certificates'].values())
            assert len(case['independent_normal_history']) == 3
            assert case['all_original_directions_and_two_updates_verified']
    shared = report('shared_audit1')
    delayed = next(c for c in shared['cases'] if c['kind'] == 'Hann' and c['label'] == 'delayed_right')
    assert delayed['stable_complete_normal'] == v['delayed_right_independent_original_normal']
    assert not delayed['previous_qualified'] and delayed['qualified']
    assert v['unchanged_original_normal_gate'] == 1e-11
    upstream = read(a.archive/'inputs/upstream/waveform_banded_v1/validation.json')
    assert upstream['shared8_qualified'] == v['upstream_band_shared_pass_count'] == 7
    assert len(upstream['shared_original_failures']) == 1
    assert upstream['shared_original_failures'][0]['stable_complete_normal'] > 1e-11
    assert len(upstream['old_root_Gram_2e_11_failures']) == 8
    resources = report('resources_audit1')
    assert resources['result'] == 'independent_waveform_correction_resources_inspected'
    assert resources['auditor_sha256'] == sha(e/'resources_audit1/executed_audit.py')
    assert resources['native_module_sha256'] == sha(e/'resources_audit1/executed_native_triangular.py')
    assert resources['native_module_sha256'] == sha(a.archive/'source/tools/waveform_correction_v1/native_triangular.py')
    assert len(resources['native_replays']) == v['native_triangle_replays'] == 23
    assert len(resources['native_rejections']) == v['native_invalid_cases_rejected'] == 5
    assert not resources['native_probe_factory_selected'] and not v['native_factory_selected']
    for row in resources['native_replays']:
        assert row['native_pointer_aliases_existing_QR'] and row['matrix_readonly_and_unchanged'] and row['RHS_inplace']
        assert row['leading_dimension'] == row['raw_shape'][0] > row['triangle_size']
        for result in row['results']:
            assert result['relative_error'] < 2e-12 and result['backward'] < 1e-11
    assert resources['conditional_cases'] == v['conditional_resource_cases']
    free = min(resources['available_memory']['available_physical_bytes'],
               resources['available_memory']['available_commit_bytes'])
    for row in resources['conditional_cases']:
        N, M = row['frames'], row['nodes']; n = 2*M*288; k = min(N, n)
        base = dict(W_band=8*4096*N, X_raw=8*N*n, graph_raw=8*(k+n)*k, graph_T=8*k*k)
        correction = dict(X_raw=8*N*n, inverse_right=8*n*k, inverse_inner=16*k*k, inverse_T=8*k*k)
        assert base == row['base_arrays'] and correction == row['correction_arrays']
        assert row['native_and_temporary_allowance_bytes'] == 3*1024**3//2
        assert row['unchanged_headroom_bytes'] == 3*1024**3
        sizes = dict(all_old_factors_retained=sum(base.values())+sum(correction.values())-correction['X_raw'],
                     proposed_separate_phases=max(sum(base.values()), sum(correction.values())),
                     proposed_separate_phases_native_triangle=max(sum(base.values()), sum(correction.values())-correction['inverse_T']))
        for key, value in sizes.items():
            assert row[key]['main_arrays_only'] == value
            required = value+3*1024**3//2+3*1024**3
            assert row[key]['required_available'] == required
            assert row[key]['available_memory_gate_passed'] == (free >= required)
        assert not row['integrated_release_or_native_solver_implemented']
        assert row['conditional_only_not_allocated'] and row['peak_memory_or_feasibility_NOT_proven']
    assert len(resources['conditional_cases']) == 13
    assert all(not row['proposed_separate_phases_native_triangle']['available_memory_gate_passed']
               for row in resources['conditional_cases'][1:])
    for producer, key in (('known1', 'original12_cumulative_peak'), ('shared1', 'shared8_cumulative_peak')):
        peak = max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in report(producer)['cases'])
        assert peak == v[key]
    assert sha(e/'executed_package.py') == sha(a.archive/'source/tools/package_waveform_correction_v1.py')
    assert not v['full_or_real_or_native48k_or_C_or_hearing_qualified'] and not v['outer_corrected_phase_qualified']
    assert not v['runtime_default_driver_owned_take_room_changed'] and v['full_goal'] == 'active'
    result = dict(result='independent_waveform_original_correction_archive_bindings_verified',
        source_bindings=sources, input_bindings=inputs, case_file_bindings=cases,
        original12=12, shared8=8, inverse_controls=8, arbitrary_controls=7,
        native_replays=23, upstream_failures_retained=True, resource_arithmetic_verified=True,
        full_or_source_or_runtime_not_promoted=True, auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result, flush=True)


if __name__ == '__main__':
    main()
