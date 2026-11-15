"""Independent genuine node/audio/scale checks and all file-resource formulas."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'): p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[name] = '2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r = dict(result='running',cases=[],inputs={})
    def bind(path):
        path = Path(path)
        r['inputs'][str(path)] = sha(path)
        return path
    try:
        source = load(bind(a.study/'report.json'))
        assert source['result'] == 'waveform_file_real_resources_inspected'
        assert source['actual_recorded_context_qualified'] and source['no_real_fit_or_large_arrays_allocated']
        for name,digest in source['inputs'].items(): assert sha(bind(name)) == digest
        root = a.workspace/'baselines/recorded_phase_context_v1'
        data = load(bind(root/'evidence/real1/report.json'))
        entries = {c['label']:c for c in data['cases']}
        mapping = load(bind(root/'validation.json'))['original_input_archive_locations']
        assert len(source['cases']) == 12 and source['block'] == 1024
        for c in source['cases']:
            row = entries[c['label']]
            with np.load(bind(root/'evidence/real1'/row['file'])) as z:
                original, extended, scale = z['original_audio'], z['audio'], z['original_scale']
                assert np.array_equal(extended[2048:-2048],original)
                assert np.array_equal(z['positions'][2048:-2048],z['original_positions'])
            with np.load(bind(root/mapping[row['original_bindings']['observer_source']])) as z:
                nodes = z['positions']
                assert np.array_equal(z['audio'],original)
            nodefile = bind(a.study/c['node_file'])
            assert sha(nodefile) == c['node_sha256']
            with np.load(nodefile) as z:
                expected = np.concatenate((np.arange(-2048,0,256),nodes,nodes[-1]+256*np.arange(1,9)))+2048
                assert np.array_equal(z['original'],nodes) and np.array_equal(z['context'],expected)
                assert np.array_equal(z['scale'],scale) and np.array_equal(expected[8:-8]-2048,nodes)
            N = len(original) if c['scope'] == 'original' else len(extended)
            M = len(nodes)+(16 if c['scope'] == 'genuine_context' else 0)
            assert (N,M,288,2) == (c['frames'],c['nodes'],c['orders'],c['RHS'])
            n,k,B = 576*M,min(N,576*M),1024
            band,col,rw = 32768*N,8*N*B,8*n*B
            phases = dict(source_columns=band+2*col,row_whitening=band+4*rw,source_QR=band+2*col,
                graph_transpose=band+8*k*B+3*rw,graph_QR=band+16*(k+n)*B,
                inverse_right=2*rw,inverse_inner=32*k*B,
                diagonal_and_update=16*B*B+32*(N+n+k))
            f = dict(source=8*N*n,graph=8*(k+n)*k,right=8*n*k,inner=16*k*k)
            p = c['resources']
            assert p['previous_two_panel_graph_transpose_arithmetic'] == band+8*k*B+2*rw
            assert p['graph_transpose_three_owned_panels_counted']
            assert p['major_phase_panel_arithmetic'] == phases and p['full_factor_file_bytes'] == f
            main = max(phases.values())+134217728
            required = main+1610612736+3221225472
            assert p['resident_misc_allowance'] == 134217728 and p['main_phase_array_allowance'] == main
            assert p['native_temporary_allowance'] == 1610612736 and p['headroom_guard'] == 3221225472
            assert p['required_available'] == required
            fits = min(p['available_physical_bytes'],p['available_commit_bytes']) >= required
            assert p['memory_passed'] == fits
            assert p['full_factor_disk_bytes'] == sum(f.values())
            assert p['disk_output_allowance'] == p['disk_guard'] == 1073741824
            assert p['required_available_disk'] == sum(f.values())+2147483648
            assert p['disk_passed'] == (p['available_disk_bytes'] >= sum(f.values())+2147483648)
            r['cases'].append(dict(label=c['label'],scope=c['scope'],frames=N,nodes=M,
                required_available=required,factor_disk_bytes=sum(f.values()),memory_passed=fits,
                disk_passed=p['disk_passed'],all_original_nodes_scales_and_context_preserved=True))
        real = [x for x in r['cases'] if x['scope'] == 'genuine_context']
        disk = sum(x['factor_disk_bytes'] for x in real)
        free = min(x['resources']['available_disk_bytes'] for x in source['cases'] if x['scope']=='genuine_context')
        assert source['sequential_six_retained_factor_bytes'] == disk
        assert source['sequential_six_required_disk_with_allowances'] == disk+2147483648
        assert source['sequential_six_disk_passed'] == (free>=disk+2147483648)
        assert source['all12_conditional_preflights_passed'] == all(x['memory_passed'] and x['disk_passed'] for x in r['cases'])
        r.update(result='independent_waveform_file_real_resources_verified',all_qualified=True,
            all12_conditional_preflights_passed=source['all12_conditional_preflights_passed'],
            sequential_six_retained_factor_bytes=disk,sequential_six_disk_passed=free>=disk+2147483648,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            no_real_fit_or_actual_peak_qualification=True)
        save(a.out/'report.json',r)
        print(r['result'],len(r['cases']),source['all12_conditional_preflights_passed'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__ == '__main__': main()
