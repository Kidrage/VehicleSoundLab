"""Conditional bounded-file resources for the SAMEsix actual recorded contexts.

Runs only after independent full-known qualification; no real inverse fit.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'full', 'full-audit', 'peak-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from waveform_file_full_v1.resources import preflight
    repo = Path(__file__).resolve().parents[1]
    audit, full = load(a.full_audit/'report.json'), load(a.full/'report.json')
    assert audit['result'] == 'independent_waveform_file_full_verified' and audit['all_qualified']
    assert full['solver_qualified'] and full['fidelity_qualified']
    assert audit['producer_sha256'] == sha(a.full/'report.json')
    measured = load(a.peak_audit/'report.json')
    assert measured['result'] == 'independent_waveform_file_measured_lifetimes_verified' and measured['all_qualified']
    assert measured['inputs'][str(a.full/'report.json')] == sha(a.full/'report.json')
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_inspection.py')
    r = dict(result='running', cases=[], inputs={}, actual_recorded_context_qualified=True,
        no_real_fit_or_large_arrays_allocated=True, block=1024)
    archive = a.workspace/'baselines/recorded_phase_context_v1'
    try:
        assert sha(archive/'manifest.json') == load(repo/'research/recorded_phase_context_v1_summary.json')['manifest_sha256']
        manifest = {x['path']:x['sha256'] for x in load(archive/'manifest.json')['files']}
        def bind(path):
            path = Path(path)
            digest = sha(path)
            if path.is_relative_to(archive) and path.name != 'manifest.json':
                assert digest == manifest[path.relative_to(archive).as_posix()]
            r['inputs'][str(path)] = digest
            return path
        for path in (a.full/'report.json', a.full_audit/'report.json', a.peak_audit/'report.json', archive/'manifest.json',
                     repo/'tools/waveform_file_full_v1/resources.py'): bind(path)
        data = load(bind(archive/'evidence/real1/report.json'))
        phase = load(bind(archive/'evidence/real_audit1/report.json'))
        assert phase['all_qualified'] and phase['pass_count'] == 6
        assert phase['producer_sha256'] == sha(archive/'evidence/real1/report.json')
        mapping = load(bind(archive/'validation.json'))['original_input_archive_locations']
        for case in data['cases']:
            with np.load(bind(archive/'evidence/real1'/case['file'])) as z:
                original, extended, scale = z['original_audio'], z['audio'], z['original_scale']
                assert np.array_equal(extended[2048:-2048], original)
                assert np.array_equal(z['positions'][2048:-2048], z['original_positions'])
                assert scale.shape == (288,1)
                with np.load(bind(archive/mapping[case['original_bindings']['observer_source']])) as old:
                    assert np.array_equal(old['audio'], original)
                    nodes = old['positions']
                context = np.r_[np.arange(-2048,0,256), nodes, nodes[-1]+np.arange(256,2049,256)]+2048
                assert context[0] == 0 and context[-1] == len(extended)-1
                assert np.array_equal(context[8:-8]-2048, nodes)
                nodefile = a.out/(case['label']+'_nodes.npz')
                np.savez_compressed(nodefile, original=nodes, context=context, scale=scale)
            for scope, N, M in (('original',len(original),len(nodes)),
                                ('genuine_context',len(extended),len(context))):
                values = preflight(a.out, N=N, M=M, H=288, block=1024)
                # Retain the full-known run's executed arithmetic in its own
                # report. For new shapes, count the previous returned panel
                # as well as the new input/output during graph transposition.
                n,k,B = 576*M,min(N,576*M),1024
                values['previous_two_panel_graph_transpose_arithmetic'] = values['major_phase_panel_arithmetic']['graph_transpose']
                values['major_phase_panel_arithmetic']['graph_transpose'] = 32768*N+8*k*B+24*n*B
                main = max(values['major_phase_panel_arithmetic'].values())+values['resident_misc_allowance']
                values['main_phase_array_allowance'] = main
                values['required_available'] = main+values['native_temporary_allowance']+values['headroom_guard']
                values['memory_passed'] = min(values['available_physical_bytes'],values['available_commit_bytes']) >= values['required_available']
                values['graph_transpose_three_owned_panels_counted'] = True
                r['cases'].append(dict(label=case['label'], scope=scope, frames=N, nodes=M,
                    orders=288, RHS=2, node_file=nodefile.name, node_sha256=sha(nodefile),
                    resources=values, conditional_arithmetic_NOT_real_fit_peak=True))
        assert len(r['cases']) == 12
        real = [x['resources'] for x in r['cases'] if x['scope'] == 'genuine_context']
        disk = sum(x['full_factor_disk_bytes'] for x in real)
        free = min(x['available_disk_bytes'] for x in real)
        r.update(result='waveform_file_real_resources_inspected',
            all12_conditional_preflights_passed=all(x['resources']['memory_passed'] and x['resources']['disk_passed'] for x in r['cases']),
            sequential_six_retained_factor_bytes=disk, sequential_six_required_disk_with_allowances=disk+2*1024**3,
            sequential_six_disk_passed=free >= disk+2*1024**3,
            inspector_sha256=sha(__file__), one_V10_two_rises_not_six_engines=True)
        save(a.out/'report.json', r)
        for c in r['cases']:
            print(c['label'], c['scope'], 'RAM', c['resources']['required_available'],
                  'DISK', c['resources']['required_available_disk'], c['resources']['memory_passed'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__': main()
