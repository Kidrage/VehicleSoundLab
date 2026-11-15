"""Independent complete file-full correction, all histories, original gates and resources."""
import argparse
import math
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','original','prerequisite','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.full_oracle import FullOracle,vec
    from observer_frequency_v1.reduced_oracle import synthesize
    from waveform_trace_audit_v1 import root_frobenius
    from waveform_file_full_v1.audit_resources import inspect as inspect_resources
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/observer_supported_v1/full_oracle.py','tools/observer_supported_v1/audit_oracle.py',
        'tools/observer_frequency_v1/reduced_oracle.py','tools/observer_frequency_v1/audit_oracle.py',
        'tools/observer_complete_v1/audit_oracle.py','tools/waveform_trace_audit_v1.py',
        'tools/waveform_file_full_v1/audit_resources.py')
    for j,name in enumerate(helpers):shutil.copy2(repo/name,a.out/f'executed_oracle_{j}.py')
    r=dict(result='running',maximum_errors={},inputs={})
    def check(name,x,y,scale=1.,gate=2e-8):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
        error=float(np.max(abs(x-y))/max(scale,1e-300));r['maximum_errors'][name]=error
        assert error<gate,(name,error)
    try:
        source,old,prerequisite=[load(p/'report.json') for p in (a.study,a.original,a.prerequisite)]
        assert source['result']=='waveform_file_full_known_measured' and source['only_one_attempt']
        assert prerequisite['result']=='independent_waveform_trace_controls_verified' and prerequisite['all_qualified']
        assert sha(a.study/'capture.npz')==source['capture_sha256'] and sha(a.original/'capture.npz')==old['capture_sha256']
        for name,h in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==h
        for name,h in source['inputs'].items():assert sha(name)==h
        for path in (a.study/'report.json',a.study/'capture.npz',a.original/'report.json',a.original/'capture.npz',a.prerequisite/'report.json'):
            r['inputs'][str(path)]=sha(path)
        with np.load(a.study/'capture.npz') as z,np.load(a.original/'capture.npz') as original:
            for name in ('audio','positions','orders','scale','nodes','factors','loadings'):assert np.array_equal(z[name],original[name])
            oracle=FullOracle(z['audio'],z['positions'],z['orders'],z['scale'])
            shape=oracle.shape;assert shape==(49,288,2) and z['audio'].shape==(12289,2)
            L=np.linalg.cholesky(oracle.R)
            def inverse(v,transpose=False):
                nodes=oracle.nodes(v)
                return vec(linalg.solve_triangular(L if transpose else L.T,nodes.reshape(49,-1),lower=transpose).reshape(shape))
            q=z['fitted']/z['scale'][None];x=vec(q);root=vec((L.T@q.reshape(49,-1)).reshape(shape))
            check('independent_LR_interleave',x,z['q'].ravel(),max(1.,np.linalg.norm(x)),gate=2e-12)
            check('packed_root',root,z['z'].ravel(),max(1.,np.linalg.norm(root)),gate=2e-12)
            wave=synthesize(z['fitted'],z['positions'],z['orders'],12289)
            check('all288_scalar_waveform',wave,z['wave'])
            direct=np.r_[oracle.data_forward(inverse(root))-oracle.target(),root]
            wave_model=z['wave_model_residual']
            data_model=np.r_[wave_model.ravel()/oracle.profile['sigma'],vec(oracle.spectral(wave_model))]
            model=np.r_[data_model,root]
            normal=inverse(oracle.data_adjoint(data_model),True)+root
            check('complete_original_model',model,z['original_model_residual'],max(1.,np.linalg.norm(oracle.target())))
            trace=root_frobenius(oracle);normA=trace['root_Frobenius']
            check('complete_original_adjoint',normal,z['original_model_normal'],max(1.,normA*np.linalg.norm(oracle.target())))
            stable=float(np.linalg.norm(normal)/max(normA*np.linalg.norm(model),1e-300))
            backward=float(np.linalg.norm(direct-model)/np.linalg.norm(oracle.target()))
            # Internal-root norms are diagnostic outputs; the original complete
            # gate above uses an independently validated all-bin trace.
            strict_trace_error=abs(normA-source['production_original_trace']['root_Frobenius'])/normA
            assert strict_trace_error<2e-11
            base_root_trace_error=abs(normA-np.sqrt(2)*source['solver']['augmented_root_Frobenius'])/normA
            e=oracle.data_forward(x)-oracle.target();p=oracle.nodes(oracle.data_adjoint(e))
            reg=(oracle.R@q.reshape(49,-1)).reshape(shape)
            gradient=float(np.linalg.norm(vec(p+reg))/np.linalg.norm(oracle.data_adjoint(oracle.target())))
            check('complete_gradient',gradient,source['original_gradient'])
            cert=oracle.gap(x,source['residual_certificate']['residual_dual_scale'])
            restored=linalg.solve(oracle.R,oracle.nodes(oracle.data_adjoint(z['u'])).reshape(49,-1),assume_a='pos').reshape(shape)
            pc=dict(primal=float(e@e)+oracle.penalty(q),dual_lower_bound=float(2*oracle.target()@z['u']-z['u']@z['u'])-oracle.penalty(restored),
                gap_upper_bound=float((e+z['u'])@(e+z['u']))+oracle.penalty(q-restored))
            gates=[]
            for tag,c in (('residual',cert),('representer',pc)):
                for name,value in c.items():check(tag+'_'+name,value,source[tag+'_certificate'][name],max(1.,abs(value)))
                passed=bool(c['gap_upper_bound']<=1e-6*c['primal']+1e-10);gates.append(passed)
                assert passed==source[tag+'_certificate']['additional_gap_gate_passed']
            qualified=bool(gradient<2e-7 and stable<=1e-11 and backward<=1e-11 and all(gates) and source['solver']['stable_root_guard_passed'])
            assert qualified==source['solver_qualified']
            error=wave-z['audio'];rows,ref=oracle.spectral(error),oracle.spectral(z['audio'])
            starts=np.arange(0,8193,256);central=(starts>=2048)&(starts+4096<=10241)
            bands=np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*16,side='right')
            stats=dict(whole_wave_NRMSE=float(np.linalg.norm(error)/np.linalg.norm(z['audio'])),
                target_wave_NRMSE=float(np.linalg.norm(error[2048:10241])/np.linalg.norm(z['audio'][2048:10241])),
                target_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[central][:,bands==b])/np.linalg.norm(ref[central][:,bands==b])) for b in range(6)],
                whole_supported_band_complex_NRMSE=[float(np.linalg.norm(rows[:,bands==b])/np.linalg.norm(ref[:,bands==b])) for b in range(6)],
                whole_wave_regions_NRMSE=[float(np.linalg.norm(error[s])/np.linalg.norm(z['audio'][s])) for s in (slice(0,2048),slice(2048,10241),slice(10241,None))])
            for name,value in stats.items():check(name,value,source['metrics'][name])
            fidelity=bool(stats['target_wave_NRMSE']<.02 and max(stats['target_supported_band_complex_NRMSE'])<.02)
            assert fidelity==source['fidelity_qualified']
            resource_audit=inspect_resources(source,a.study)
            for row in resource_audit['factors']:
                path=a.study/'factors'/row['name']
                r['inputs'][str(path)]=row['sha256']
            progress=load(a.study/'progress.json')
            assert progress['status']=='completed' and progress['report_sha256']==sha(a.study/'report.json')
            # Independently check all three saved original-operator states.
            history=[]
            zs,es,gs,ds=(z[n] for n in ('history_z','history_wave','history_original_normal','delta_z'))
            assert zs.shape==gs.shape==(3,28224,2) and es.shape==(3,12289,2) and ds.shape==(2,28224,2)
            assert np.array_equal(zs[0],z['base_z']) and np.array_equal(es[0],z['base_wave_model_residual'])
            for j in range(3):
                packed=zs[j].ravel()
                dm=np.r_[es[j].ravel()/oracle.profile['sigma'],vec(oracle.spectral(es[j]))]
                gn=inverse(oracle.data_adjoint(dm),True)+packed
                denominator=max(normA*np.linalg.norm(np.r_[dm,packed]),1e-300)
                check('history_original_normal_'+str(j),gn,gs[j].ravel(),max(denominator,1.),gate=2e-12)
                consistent=oracle.data_forward(inverse(packed))-oracle.target()
                ratio=float(np.linalg.norm(consistent-dm)/np.linalg.norm(oracle.target()))
                assert ratio<=1e-11
                history.append(dict(step=j,stable_complete_normal=float(np.linalg.norm(gn)/denominator),backward=ratio))
                if j==0:
                    # Separate L/R checks against the complete original FFT
                    # metric; no production band-root actions are imported.
                    dm2=dm.reshape(-1,2)
                    per_denominator=(normA/np.sqrt(2))*np.sqrt(np.sum(dm2*dm2,axis=0)+np.sum(zs[j]**2,axis=0))
                    base_stable=np.linalg.norm(gn.reshape(28224,2),axis=0)/np.maximum(per_denominator,1e-300)
                    base_backward=np.linalg.norm((consistent-dm).reshape(-1,2),axis=0)/np.maximum(np.linalg.norm(oracle.target().reshape(-1,2),axis=0),1e-300)
                    assert np.all(base_stable<=1e-11) and np.all(base_backward<=1e-11)
                    check('base_guard_stable_LR',base_stable,source['solver']['stable_root_normal_relative'],gate=2e-12)
                    check('base_guard_backward_LR',base_backward,source['solver']['root_backward_discrepancy'],gate=2e-12)

                if j<2:
                    check('history_node_update_'+str(j),zs[j+1],zs[j]+ds[j],gate=2e-12)
                    delta_nodes=oracle.nodes(inverse(ds[j].ravel()))*z['scale'][None]
                    delta_wave=synthesize(delta_nodes,z['positions'],z['orders'],12289)
                    check('history_wave_update_'+str(j),es[j+1],es[j]+delta_wave,gate=2e-12)
            assert np.array_equal(zs[-1],z['z']) and np.array_equal(es[-1],z['wave_model_residual'])
            comparisons=[]
            for name,value in source['metrics'].items():
                now=value if isinstance(value,list) else [value]
                before=old['metrics'][name];before=before if isinstance(before,list) else [before]
                comparisons.extend(dict(metric=name,index=i,previous=x,current=y,regressed=y>x) for i,(x,y) in enumerate(zip(before,now)))
            assert len(comparisons)==17 and comparisons==source['comparison_rows']
            assert z['file_x_tau'].shape==(12289,) and z['file_graph_tau'].shape==(12289,)
            assert z['inverse_right_tau'].shape==(12289,) and z['inverse_inner_tau'].shape==(12289,)
            for name,h in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==h
            r.update(result='independent_waveform_file_full_verified',all_qualified=bool(qualified and fidelity and resource_audit['all_qualified']),solver_qualified=qualified,fidelity_qualified=fidelity,
                metrics=stats,gradient=gradient,stable_original_complete_normal=stable,original_backward=backward,
                independent_all_bin_trace=trace,extra_trace2e_11_passed=bool(strict_trace_error<2e-11),extra_trace_relative_error=float(strict_trace_error),
                residual_certificate=cert,representer_certificate=pc,residual_gap_passed=gates[0],representer_gap_passed=gates[1],
                file_resource_audit=resource_audit,actual_aliases_and_lifetimes_verified=True,
                process_peak_working_set_bytes=source['process_memory']['cumulative_peak_working_set_bytes'],
                tracked_peak_bytes=source['resources']['max_tracked_live_backing_bytes'],
                producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),oracles_sha256={n:sha(repo/n) for n in helpers},
                no_real_material_or_runtime_or_hearing_promotion=True,
                original_correction_history=history,all_phase_releases_verified=True,comparison_rows=comparisons,
                production_original_trace_relative_error=float(strict_trace_error),base_root_trace_diagnostic_error=float(base_root_trace_error))
        save(a.out/'report.json',r)
        print(r['result'],'solver',qualified,'fidelity',fidelity,'normal',stable,'gaps',cert['gap_upper_bound'],pc['gap_upper_bound'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
