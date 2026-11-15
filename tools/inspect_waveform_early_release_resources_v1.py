"""SAMEsix ORIGINAL and actual qualified context shapes after owned full proof."""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load,save,sha
from run_waveform_stream_full_v1 import physical_memory


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','full','full-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_inspection.py')
    repo=Path(__file__).resolve().parents[1]
    full=load(a.full/'report.json');audit=load(a.full_audit/'report.json')
    assert full['owned_pipeline'] and full['solver_qualified'] and full['fidelity_qualified']
    assert audit['result']=='independent_waveform_correction_native_full_verified'
    assert audit['solver_qualified'] and audit['fidelity_qualified'] and audit['source_released_before_inner']
    assert audit['base_graph_copy_avoided'] and audit['producer_sha256']==sha(a.full/'report.json')
    archive=a.workspace/'baselines/recorded_phase_context_v1'
    assert sha(archive/'manifest.json')==load(repo/'research/recorded_phase_context_v1_summary.json')['manifest_sha256']
    manifest={row['path']:row['sha256'] for row in load(archive/'manifest.json')['files']}
    mapping=load(archive/'validation.json')['original_input_archive_locations']
    data=load(archive/'evidence/real1/report.json');phase_audit=load(archive/'evidence/real_audit1/report.json')
    assert phase_audit['all_qualified'] and phase_audit['pass_count']==6
    assert phase_audit['producer_sha256']==sha(archive/'evidence/real1/report.json')
    memory=physical_memory();free=min(memory['available_physical_bytes'],memory['available_commit_bytes'])
    r=dict(result='waveform_early_release_real_resources_inspected',cases=[],available_memory=memory,
        inputs={},actual_recorded_context_qualified=True,no_real_fit_or_large_arrays_allocated=True)
    def bind(path):
        path=Path(path);digest=sha(path);r['inputs'][str(path)]=digest
        if path.is_relative_to(archive) and path.name!='manifest.json':assert digest==manifest[path.relative_to(archive).as_posix()]
        return path
    for path in (a.full/'report.json',a.full_audit/'report.json',archive/'manifest.json',
                 archive/'evidence/real1/report.json',archive/'evidence/real_audit1/report.json'):bind(path)
    for case in data['cases']:
        with np.load(bind(archive/'evidence/real1'/case['file'])) as z:
            original=z['original_audio'];extended=z['audio']
            assert np.array_equal(extended[2048:-2048],original)
            assert np.array_equal(z['positions'][2048:-2048],z['original_positions'])
            scale=z['original_scale'];assert scale.shape==(288,1)
            with np.load(bind(archive/mapping[case['original_bindings']['observer_source']])) as source:
                assert np.array_equal(original,source['audio'])
                nodes=source['positions']
            # Exact original nonuniform node positions are preserved. New
            # boundary nodes extend by256, never respace existing target nodes.
            context_nodes=np.r_[np.arange(-2048,0,256),nodes,nodes[-1]+np.arange(256,2049,256)]+2048
            assert len(context_nodes)==len(nodes)+16 and np.array_equal(context_nodes[8:-8]-2048,nodes)
            assert context_nodes[0]==0 and context_nodes[-1]==len(extended)-1
            node_file=a.out/(case['label']+'_nodes.npz')
            np.savez_compressed(node_file,original=nodes,context=context_nodes,scale=scale)
        for scope,N,M in (('original',len(original),len(nodes)),('genuine_context',len(extended),len(context_nodes))):
            n=2*M*288;k=min(N,n)
            W,X,graph,T=8*4096*N,8*N*n,8*(k+n)*k,8*k*k
            right,inner=8*n*k,16*k*k
            old=max(W+X+graph+T,X+right+inner)
            phases=dict(base=W+X+graph,right_build=X+right,inner_build=right+inner)
            main=max(phases.values());required=main+3*1024**3//2+3*1024**3
            r['cases'].append(dict(label=case['label'],scope=scope,frames=N,nodes=M,orders=288,RHS=2,
                node_file=node_file.name,node_sha256=sha(node_file),all_original_nodes_preserved=True,
                individual_bytes=dict(W_band=W,X=X,graph=graph,old_graph_T=T,inverse_right=right,inverse_inner=inner),
                major_phase_bytes=phases,main_arrays_only=main,prior_native_main_arrays_only=old,
                required_available=required,available_gate_passed=free>=required,
                native_temporary_allowance=3*1024**3//2,headroom_guard=3*1024**3,
                shape_arithmetic_only_NOT_real_fit_peak=True))
    assert len(r['cases'])==12
    r['auditor_sha256']=sha(__file__);save(a.out/'report.json',r)
    for case in r['cases']:
        print(case['label'],case['scope'],'required',case['required_available'],'fits',case['available_gate_passed'],flush=True)


if __name__=='__main__':main()
