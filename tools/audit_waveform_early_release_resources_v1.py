"""Independent actual-context node geometry and conditional byte arithmetic."""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],inputs={})
    def bind(path):
        path=Path(path);r['inputs'][str(path)]=sha(path);return path
    try:
        source=load(bind(a.study/'report.json'))
        assert source['result']=='waveform_early_release_real_resources_inspected'
        assert source['actual_recorded_context_qualified'] and source['no_real_fit_or_large_arrays_allocated']
        for name,digest in source['inputs'].items():assert sha(bind(name))==digest
        root=a.workspace/'baselines/recorded_phase_context_v1'
        original=load(bind(root/'evidence/real1/report.json'))
        entries={c['label']:c for c in original['cases']}
        mapping=load(bind(root/'validation.json'))['original_input_archive_locations']
        assert len(source['cases'])==12
        free=min(source['available_memory']['available_physical_bytes'],source['available_memory']['available_commit_bytes'])
        for case in source['cases']:
            row=entries[case['label']]
            with np.load(bind(root/'evidence/real1'/row['file'])) as z:
                frames=len(z['original_audio'] if case['scope']=='original' else z['audio'])
                assert np.array_equal(z['audio'][2048:-2048],z['original_audio'])
                scale=z['original_scale']
            with np.load(bind(root/mapping[row['original_bindings']['observer_source']])) as z:nodes=z['positions']
            path=bind(a.study/case['node_file']);assert sha(path)==case['node_sha256']
            with np.load(path) as z:
                assert np.array_equal(z['original'],nodes) and np.array_equal(z['scale'],scale)
                expected=np.concatenate((np.arange(-2048,0,256),nodes,nodes[-1]+256*np.arange(1,9)))+2048
                assert np.array_equal(z['context'],expected) and np.array_equal(z['context'][8:-8]-2048,nodes)
            N,M=frames,len(nodes)+(16 if case['scope']=='genuine_context' else 0)
            assert (N,M)==(case['frames'],case['nodes']) and case['orders']==288 and case['RHS']==2
            columns=576*M;reduced=min(N,columns)
            values=dict(W_band=32768*N,X=8*N*columns,graph=8*(reduced+columns)*reduced,
                old_graph_T=8*reduced**2,inverse_right=8*columns*reduced,inverse_inner=16*reduced**2)
            assert values==case['individual_bytes']
            phases=dict(base=values['W_band']+values['X']+values['graph'],
                        right_build=values['X']+values['inverse_right'],
                        inner_build=values['inverse_right']+values['inverse_inner'])
            assert phases==case['major_phase_bytes'] and max(phases.values())==case['main_arrays_only']
            required=max(phases.values())+1610612736+3221225472
            assert required==case['required_available']
            assert case['available_gate_passed']==(free>=required)
            old=max(phases['base']+values['old_graph_T'],values['X']+values['inverse_right']+values['inverse_inner'])
            assert old==case['prior_native_main_arrays_only']
            assert case['shape_arithmetic_only_NOT_real_fit_peak']
            r['cases'].append(dict(label=case['label'],scope=case['scope'],frames=N,nodes=M,
                required_available=required,available_gate_passed=free>=required,
                all_original_nodes_and_scales_preserved=True))
        r.update(result='independent_waveform_early_release_real_resources_verified',
            actual_context_shape_count=6,conditional_resource_case_count=12,
            no_real_fit_or_large_allocation_verified=True,original_reserves_unchanged=True,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__))
        save(a.out/'report.json',r);print(r['result'],12,flush=True)
    except BaseException as e:
        r.update(result='failed',error=repr(e));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
