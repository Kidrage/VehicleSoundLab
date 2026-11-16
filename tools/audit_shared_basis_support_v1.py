"""Support-explicit shared-basis audit; retain structurally zero coefficient slots."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from constrained_source_operator_v1 import oracle
    from operator_roundoff_v1.exact_dyadic import matvec
    from locked_source_guard_v1.measurement import declared,fidelity
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],auditor_sha256=sha(__file__))
    try:
        source=load(a.study/'report.json');assert source['result']=='shared_discrete_basis_known_execution_completed'
        repo=Path(__file__).resolve().parents[1]
        for name,digest in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for path,digest in source['inputs'].items():assert sha(path)==digest
        for case in source['cases']:
            name=case['name'];comp={};elements=0;block_entries=0
            r['active_case']=dict(name=name,comparisons=comp)
            def check(label,got,expected):
                nonlocal elements
                got,expected=np.asarray(got),np.asarray(expected);assert got.shape==expected.shape,label
                err=float(np.max(abs(got-expected)))/max(float(np.max(abs(expected))),1e-300)
                comp[label]=err;elements+=got.size
                if not np.isfinite(err) or err>2e-11:raise ValueError((name,label,err))
            path=next(Path(p) for p in source['inputs'] if Path(p).parent.name==name and Path(p).name=='operators.npz')
            with np.load(path) as f:z={key:f[key] for key in f.files}
            output=a.study/name/'output.npz';blocks=a.study/name/'blocks.npz'
            assert sha(output)==case['output_sha256'] and sha(blocks)==case['blocks_sha256']
            with np.load(output) as f:o={key:f[key] for key in f.files}
            phi,b,groups,prior=oracle.dense(z);x=z['x'];frames=int(z['frames']);nw=frames*2
            windows=1+(frames-4096)//256;nz=windows*2049*2
            assert np.array_equal(o['carriers'],oracle.table(z['orders']))
            with np.load(blocks) as f:
                assert set(f.files)=={k+'_'+str(j) for j in range(windows) for k in ('ids','matrix')}
                for j in range(windows):
                    ids=f['ids_'+str(j)];matrix=f['matrix_'+str(j)];first=j*256
                    # Determine spatially supported coefficient slots independently.
                    # Keep algebraic zero/null columns; they are not missing orders.
                    node_hats=np.array([np.interp(np.arange(first,first+4096),z['positions'],row) for row in np.eye(len(z['positions']))])
                    active_nodes=np.flatnonzero(np.any(node_hats!=0,axis=1));h=len(z['orders'])
                    real_ids=(active_nodes[:,None]*h+np.arange(h)).ravel()
                    active=np.r_[real_ids,real_ids+len(z['positions'])*h]
                    assert np.array_equal(ids,active),(name,j)
                    real=nw+j*2049*2+np.arange(2049)*2
                    selected=np.r_[real,real+nz]
                    expected=b[np.ix_(selected,2*ids)]
                    check('all_block_entries_'+str(j),matrix,expected);block_entries+=matrix.size
            check('every_source_sample',o['source'].ravel(),matvec(phi,x))
            check('every_full_forward_row',o['full_forward'],matvec(b,x))
            check('every_full_transpose_coefficient',o['full_adjoint'],matvec(b.T,z['full_dual']))
            for g in range(7):check('every_target_group_'+str(g),o['target_'+str(g)],matvec(groups[g],x))
            dual=np.concatenate([z['target_dual_'+str(g)] for g in range(7)])
            check('every_target_transpose_coefficient',o['target_adjoint'],matvec(np.column_stack([v.T for v in groups]),dual))
            residual=o['full_forward']-o['rhs'];matrix=np.column_stack((b.T,prior));rhs=np.r_[residual,x]
            check('every_objective_gradient_coefficient',o['gradient'],matvec(matrix,rhs))
            check('objective',case['objective'],.5*residual@residual+.5*x@prior@x)
            assert case['compiled_blocks']==windows and case['cache_hits']>=windows
            metrics=declared(z['audio'],o['source'],float(z['amplitude']),z['weights'])
            for key,value in metrics.items():check('original_direct_metric_'+key,case['original_direct_waveform_metrics'][key],value)
            assert case['original_direct_fidelity_passed']==fidelity(metrics)
            if 'null_full' in o:assert not np.count_nonzero(o['null_full'])
            # Preserve every old failed numerical comparison separately.
            legacy=[]
            for g in range(7):
                expected=z['target_'+str(g)];error=float(np.max(abs(o['target_'+str(g)]-expected)))/max(float(np.max(abs(expected))),1e-300)
                legacy.append(error)
            r['cases'].append(dict(name=name,comparisons=comp,elements_checked=elements,
                compiled_block_entries_checked=block_entries,maximum_scaled_error=max(comp.values()),
                cross_legacy_target_group_relative_differences=legacy,
                current_method_pass_does_not_relabel_old_19_failures=True))
            save(a.out/'report.json',r);print('SHARED_EXACT_AUDIT',name,elements,max(comp.values()),flush=True)
        # Derive complete-scale storage and work without importing producer
        # geometry/resource modules or compiling a complete-scale operator.
        f=source['full_geometry_resources'];frames=18430;h=288
        original=np.r_[np.arange(0,frames-4096,256),frames-4097]
        positions=np.r_[np.arange(-2048,0,256),original,original[-1]+np.arange(256,2049,256)]+2048
        hats=np.array([np.interp(np.arange(frames),positions,row) for row in np.eye(73)])
        def columns(first,last):return int(np.count_nonzero(np.any(hats[:,first:last]!=0,axis=1)))*h*2
        waves=[dict(first=start,rows=min(256,frames-start),columns=columns(start,min(start+256,frames))) for start in range(0,frames,256)]
        spectra=[dict(index=j,first=start,rows=4098,columns=columns(start,start+4096)) for j,start in enumerate(range(0,frames-4096+1,256))]
        for rows,expected in ((f['shared_wave_blocks'],waves),(f['shared_spectral_blocks'],spectra)):
            assert len(rows)==len(expected)
            for got,reference in zip(rows,expected):
                for key,value in reference.items():assert got[key]==value
                assert got['matrix_bytes']==reference['rows']*reference['columns']*8
        assert (f['real_unknowns'],f['full_data_rows'],f['full_supported_windows'],f['target_supported_windows'])==(84096,495836,56,40)
        spectrum_bytes=sum(v['rows']*v['columns']*8 for v in spectra);wave_bytes=sum(v['rows']*v['columns']*8 for v in waves)
        assert (f['shared_spectral_payload_bytes'],f['shared_wave_payload_bytes'])==(spectrum_bytes,wave_bytes)
        assert f['full_dense_bytes']==495836*84096*8 and f['one_channel_global_dense_bytes']==247918*42048*8
        assert f['one_forward_matrix_products']==f['one_adjoint_matrix_products']==2*(spectrum_bytes+wave_bytes)//8
        r.pop('active_case',None)
        r.update(result='distinct_shared_basis_small_known_method_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),maximum_scaled_error=max(v['maximum_scaled_error'] for v in r['cases']),
            complete_geometry_support_storage_work_counts_verified=True,
            full_scale_operator_or_constrained_solver_or_actual_source_qualification=False,
            original_19_failures_preserved=True,new_C1_source_eligible_for_statistics=False)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
