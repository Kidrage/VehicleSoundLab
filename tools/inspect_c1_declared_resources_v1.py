"""Read-only single-input resource/duplicate preflight; never reserve or fit."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    from c1_source_prepare_v1.provenance import Proofs
    from waveform_file_real_v1.resources import preflight
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', inputs={}, sources={}, observed_utc=datetime.now(timezone.utc).isoformat(),
             no_fit_or_registration_or_factor_mutation=True)
    proof = Proofs(a.workspace, repo, r)
    try:
        root = a.workspace/'references/analysis'
        math = proof.read(root/'c1_declared_objective_v1/real1/report.json')
        assert math['complete_declared_preparation_mathematics_passed']
        assert not math['original_SciPy_preparation_audit_passed']
        assert math['source_fidelity_not_evaluated'] and not math['eligible_for_later_source_statistics']
        proof.absorb(math)
        prepared = proof.read(root/'c1_source_adapter_v1/prepare1/report.json')
        row, = prepared['cases']
        assert row['label'] == 'F3 Fifth First Late'
        N, M, H, B = row['frames'], row['nodes'], row['orders'], 1024
        assert (N, M, H) == (18430, 73, 288)
        packet = root/'c1_source_adapter_v1/prepare1'/row['file']
        assert sha(proof.bind(packet)) == row['sha256']
        before = proof.protect(row['label'])
        assert before == proof.read(root/'c1_source_adapter_v1/prepare1/protected_before.json')
        target = Path(before['D_storage_root'])/'preflight1'
        assert target.is_dir() and not list(target.iterdir()), 'Existing empty SSD probe only'
        resources = preflight(target, N, M, H, B)

        # Independent lifetime/file arithmetic, without sharing the preflight
        # implementation's expressions or relying on its Boolean conclusions.
        n = 2*M*H
        k = min(N, n)
        band = N*4096*8
        column, row_panel, graph_panel = N*B*8, n*B*8, (k+n)*B*8
        phases = dict(source_columns=band+2*column,
            row_whitening=band+4*row_panel, source_QR=band+2*column,
            graph_transpose=band+k*B*8+3*row_panel,
            graph_QR=band+2*graph_panel, inverse_right=2*row_panel,
            inverse_inner=4*k*B*8,
            diagonal_and_update=2*B*B*8+(N+n+k)*4*8)
        files = {name: rows*columns*8 for name, rows, columns in (
            ('source', N, n), ('graph', k+n, k), ('right', n, k), ('inner', 2*k, k))}
        memory_needed = max(phases.values())+128*1024**2+3*1024**3//2+3*1024**3
        disk_needed = sum(files.values())+2*1024**3
        assert resources['major_phase_panel_arithmetic'] == phases
        assert resources['full_factor_file_bytes'] == files
        assert resources['full_factor_disk_bytes'] == sum(files.values())
        assert resources['resident_misc_allowance'] == 128*1024**2
        assert resources['native_temporary_allowance'] == 3*1024**3//2
        assert resources['headroom_guard'] == 3*1024**3
        assert resources['required_available'] == memory_needed
        assert resources['disk_output_allowance'] == resources['disk_guard'] == 1024**3
        assert resources['required_available_disk'] == disk_needed
        assert resources['graph_transpose_three_owned_panels_counted']
        assert resources['conditional_arithmetic_NOT_actual_peak_proof']
        memory_passed = min(resources['available_physical_bytes'], resources['available_commit_bytes']) >= memory_needed
        disk_passed = resources['available_disk_bytes'] >= disk_needed
        assert resources['memory_passed'] == memory_passed
        assert resources['disk_passed'] == disk_passed
        assert memory_passed and disk_passed
        after = proof.protect('F3 Fifth First Late')
        assert before == after and not list(target.iterdir())
        for name in ('tools/inspect_c1_declared_resources_v1.py',
                     'tools/waveform_file_real_v1/resources.py', 'tools/waveform_file_full_v1/resources.py',
                     'tools/c1_source_prepare_v1/provenance.py', 'tools/run_waveform_stream_full_v1.py'):
            r['sources'][name] = sha(repo/name)
        for name, expected in r['sources'].items():
            assert sha(repo/name) == expected
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
        r.update(result='c1_declared_single_input_preflight_verified', label='F3 Fifth First Late',
            frames=N, nodes=M, orders=H, block=B, resources=resources,
            independent_all_phase_and_file_arithmetic_verified=True,
            namespace_before=before, namespace_after=after,
            original_bindings_and_C_contracts_unchanged=True,
            both_canonical_E_namespaces_and_D_have_no_selected_fit=True,
            cross_drive_reservation_NOT_implemented=True, fit_NOT_authorized_by_this_report=True,
            actual_peak_or_speedup_NOT_measured=True, source_fidelity_NOT_evaluated=True)
        save(a.out/'report.json', r)
        print('C1_DECLARED_PREFLIGHT', dict(factor_GiB=sum(files.values())/2**30,
            required_memory_GiB=memory_needed/2**30, required_disk_GiB=disk_needed/2**30,
            available_disk_GiB=resources['available_disk_bytes']/2**30), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
