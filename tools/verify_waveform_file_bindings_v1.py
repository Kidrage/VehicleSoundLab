"""Independent immutable file-stage source versions, known gates and I/O bindings."""
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
    v = read(a.archive/'validation.json')
    e = a.archive/'evidence'
    assert {p.name for p in e.iterdir() if p.is_dir()} == set(v['selected_terminal_evidence_directories'])
    manifests = {}
    for name, digest in v['upstream_manifests_sha256'].items():
        path = a.archive/f'inputs/upstream/{name}/manifest.json'
        assert sha(path) == digest
        manifests[name] = {row['path']:row['sha256'] for row in read(path)['files']}
    input_count = source_count = factor_count = case_count = 0
    def bound(name, digest):
        target = v['original_input_archive_locations'][name]
        path = a.archive/target
        assert path.resolve().is_relative_to(a.archive.resolve()) and sha(path) == digest
        parts = Path(target).parts
        if parts[:2] == ('inputs', 'upstream'):
            leaf = Path(*parts[3:]).as_posix()
            expected = v['upstream_manifests_sha256'][parts[2]] if leaf == 'manifest.json' else manifests[parts[2]][leaf]
            assert expected == digest
    def factors(value):
        nonlocal factor_count
        if isinstance(value, dict):
            if {'path', 'shape', 'file_bytes', 'sha256'} <= value.keys():
                bound(value['path'], value['sha256'])
                assert value['file_bytes'] == value['declared_bytes'] == 8*value['shape'][0]*value['shape'][1]
                assert value['closed'] and not value['mapped']
                factor_count += 1
            for child in value.values():
                factors(child)
        elif isinstance(value, list):
            for child in value:
                factors(child)
    reports = {}
    for folder in v['selected_terminal_evidence_directories']:
        report = reports[folder] = read(e/folder/'report.json')
        for key in ('inputs', 'input_sha256'):
            for name, digest in report.get(key, {}).items():
                bound(name, digest)
                input_count += 1
        for name, digest in report.get('sources', {}).items():
            assert sha(e/folder/'exact_sources'/name) == digest == v['executed_source_versions'][name][folder]
            source_count += 1
        for key in ('kernel_cases', 'inverse_cases', 'original_cases', 'cases'):
            for case in report.get(key, []):
                if 'file' in case:
                    assert sha(e/folder/case['file']) == case['sha256']
                    case_count += 1
                for f in case.get('files', []):
                    path = e/folder/f['file']
                    assert path.stat().st_size == f['bytes'] and sha(path) == f['sha256']
        factors(report)
        if 'auditor_sha256' in report:
            assert sha(e/folder/'executed_audit.py') == report['auditor_sha256']
    for name, digest in v['current_source_sha256'].items():
        assert sha(a.archive/'source'/name) == digest
    for j in (1, 2, 3):
        source, audit = reports['controls'+str(j)], reports['controls_audit'+str(j)]
        assert audit['producer_sha256'] == sha(e/('controls'+str(j))/'report.json') and audit['all_qualified']
        assert len(source['kernel_cases']) == v['kernel_controls'] == 12
        assert len(audit['inverse_cases']) == v['inverse_controls'] == 8 and len(audit['original_cases']) == v['arbitrary_controls'] == 7
    for name in ('panels_audit1', 'panels_audit2'):
        report = reports[name]
        assert report['all_qualified'] and len(report['guards']) == v['input_guards'] == 12
        assert all(c['qualified'] for c in report['kernel_cases']+report['file_cases'])
    for name, count in (('known', 12), ('shared', 8)):
        source, audit = reports[name+'1'], reports[name+'_audit1']
        assert audit['producer_sha256'] == sha(e/(name+'1')/'report.json')
        assert source['file_pipeline'] and audit['file_pipeline'] and source['all_qualified'] and audit['all_qualified']
        assert source['pass_count'] == audit['pass_count'] == count
        assert all(c['qualified'] and c['original_gradient'] < 2e-7 and c['stable_complete_normal'] <= 1e-11
                   and c['original_backward'] <= 1e-11 and all(g['passed'] for g in c['certificates'].values()) for c in audit['cases'])
    resources = reports['resources_audit1']
    assert resources['all_qualified'] and resources['cases'] == v['complete_known_native_file_resources']
    assert resources['comparisons'] == v['all80_signed_comparisons'] and len(resources['comparisons']) == 80
    assert sum(c['regressed'] for c in resources['comparisons']) == v['numerical_regressions'] == 33
    assert sum(len(c['all_seven_output_array_changes']) for c in resources['cases']) == 140
    assert resources['original4DFT_3temporal_native_roots_reused_exact']
    document = (a.archive/'source/research/有界文件因子V1.md').read_text(encoding='utf-8')
    for kind in ('original12', 'shared8'):
        cases = [c for c in resources['cases'] if c['kind'] == kind]
        numbers = [max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in cases),
            max(c['process_memory']['cumulative_peak_private_commit_bytes'] for c in cases),
            max(c['registered_backing_peak_bytes'] for c in cases),
            max(f['max_native_panel_bytes'] for c in cases for f in c['factors']),
            max(f['max_native_work_array_bytes'] for c in cases for f in c['factors']),
            sum(c['total_read_bytes'] for c in cases), sum(c['total_write_bytes'] for c in cases)]
        assert all(format(n, ',') in document for n in numbers)
        assert format(sum(c['elapsed_host_seconds'] for c in cases), '.3f') in document
    assert sha(e/'executed_package.py') == sha(a.archive/'source/tools/package_waveform_file_panels_v1.py')
    assert v['full_goal'] == 'active' and not v['full_or_real_context_resource_qualified']
    assert v['no_C_or_timbre_promotion'] and not v['runtime_default_driver_owned_take_room_changed']
    result = dict(result='independent_waveform_file_archive_bindings_verified', input_bindings=input_count,
        executed_source_bindings=source_count, factor_file_bindings=factor_count, case_bindings=case_count,
        original_gates_and_all_versions_verified=True, all80_signed_and140_array_changes_verified=True,
        published_known_resources_verified=True, auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(result, flush=True)


if __name__ == '__main__':
    main()
