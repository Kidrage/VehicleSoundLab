"""Read-only independent actual pair, provenance and resource inspection."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    def sha(path):
        with Path(path).open('rb') as f:
            return hashlib.file_digest(f, 'sha256').hexdigest()
    def read(path):
        return json.loads(Path(path).read_text(encoding='utf-8'))
    r = dict(result='running', inputs={}, sources={})
    try:
        producer = read(a.study/'report.json')
        assert producer['result'] == 'c1_source_single_registration_reserved'
        pair = producer['pair']
        original = pair['spec']
        left, right = map(Path, (original['canonical_claim'], original['storage_claim']))
        assert left.drive.upper() == 'E:' and right.drive.upper() == 'D:'
        assert (left/'run_spec.json').read_bytes() == (right/'run_spec.json').read_bytes()
        assert sha(left/'run_spec.json') == pair['registration_sha256']
        spec = read(left/'run_spec.json')
        assert spec == original and spec['schema'] == 'vsl.c1-source-fit-registration/1'
        assert spec['state'] == 'reserved_only' and spec['original_label'] == 'F3 Fifth First Late'
        expected_key = hashlib.sha256(b'f3 fifth first late').hexdigest()
        assert spec['claim_key'] == left.name == right.name == expected_key
        assert (left/'pair_receipt.json').read_bytes() == (right/'pair_receipt.json').read_bytes()
        assert read(left/'pair_receipt.json') == dict(schema='vsl.c1-source-fit-pair-receipt/1',
            claim_key=expected_key, registration_sha256=pair['registration_sha256'], both_specs_identical=True)
        assert sha(left/'pair_receipt.json') == pair['receipt_sha256']
        assert spec['source_identity'] == 'vsl.c1-22k-source-preparation/1'
        assert spec['measurement_identity'] == 'vsl.c1-declared-objective/1'
        assert spec['input_schema'] == 'vsl.c1-source-input/1'
        for name, expected in spec['source_closure'].items():
            assert sha(a.repo/name) == sha(Path(spec['exact_sources_root'])/name) == expected
            r['sources'][name] = expected
        for name, expected in spec['input_closure'].items():
            assert sha(name) == expected
            r['inputs'][name] = expected
        for name, expected in spec['toolchain']['native_files_sha256'].items():
            assert sha(name) == expected
        assert sha(spec['input_file']) == spec['input_sha256']
        for name in ('original_preparation', 'original_context'):
            assert Path(spec[name]).stem == spec['original_label']
            assert sha(spec[name]) == spec['ancestry'][name+'_sha256']
        assert spec['geometry'] == dict(frames=18430, target_frames=14334, orders=288,
            nodes=73, original_nodes=57, clock_observations=89, channels=2, block=1024)
        known = read(spec['known_registration_proof'])
        assert known['rejection_count'] == 18 and known['independent_success_pair_inspection']
        math = read(spec['complete_preparation_math'])
        assert math['complete_declared_preparation_mathematics_passed'] and not math['original_SciPy_preparation_audit_passed']
        failed = read(spec['original_failed_audit'])
        assert failed['result'] == 'failed' and '2.5585096571438003e-12' in failed['error']
        N, M, H, B = (spec['geometry'][k] for k in ('frames', 'nodes', 'orders', 'block'))
        n, k = 2*M*H, min(N, 2*M*H)
        disk = {name:8*rows*columns for name, rows, columns in (
            ('source', N, n), ('graph', k+n, k), ('right', n, k), ('inner', 2*k, k))}
        band, column, row = 8*4096*N, 8*N*B, 8*n*B
        phases = dict(source_columns=band+2*column, row_whitening=band+4*row,
            source_QR=band+2*column, graph_transpose=band+8*k*B+3*row,
            graph_QR=band+16*(k+n)*B, inverse_right=2*row, inverse_inner=32*k*B,
            diagonal_and_update=16*B*B+32*(N+n+k))
        budget = spec['resource_preflight']
        assert budget['full_factor_file_bytes'] == disk
        assert budget['major_phase_panel_arithmetic'] == phases
        assert budget['full_factor_disk_bytes'] == sum(disk.values())
        assert budget['required_available_disk'] == sum(disk.values())+2*1024**3
        assert budget['required_available'] == max(phases.values())+128*1024**2+3*1024**3//2+3*1024**3
        assert budget['memory_passed'] and budget['disk_passed']
        assert min(budget['available_physical_bytes'], budget['available_commit_bytes']) >= budget['required_available']
        assert budget['available_disk_bytes'] >= budget['required_available_disk']
        for item in spec['legacy_namespace_snapshot']['namespaces']:
            root = Path(item['root'])
            assert read(root/'report.json')['result'] == 'failed'
            assert sorted(p.name for p in root.iterdir() if p.is_dir()) == item['existing_directories']
        assert not list(left.rglob('*.bin')) and not list(right.rglob('*.bin'))
        assert not (left/'launch_intent.json').exists() and not (right/'launch_intent.json').exists()
        r.update(result='independent_c1_source_registration_verified', verification_passed=True,
            producer_sha256=sha(a.study/'report.json'), registration_sha256=pair['registration_sha256'],
            actual_pair_bytes_and_receipts_verified=True, source_ancestry_and_toolchain_verified=True,
            full_geometry_and_original_resource_arithmetic_verified=True,
            original_namespaces_frozen_contracts_and_failure_preserved=True,
            authored_source_count=len(r['sources']), input_count=len(r['inputs']),
            native_toolchain_file_count=len(spec['toolchain']['native_files_sha256']),
            no_fit_or_actual_peak_or_source_fidelity_or_runtime_qualification=True)
        (a.out/'report.json').write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('C1_REGISTRATION_AUDIT', r['authored_source_count'], r['input_count'], r['native_toolchain_file_count'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        (a.out/'report.json').write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
