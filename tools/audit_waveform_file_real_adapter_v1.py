"""Independent original-target/context controls; no producer fitter imports."""
import argparse
import gc
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
    from scipy import linalg
    from observer_complete_v1.audit_oracle import curvature,full_frame
    from observer_frequency_v1.reduced_oracle import synthesize
    from observer_supported_v1.full_oracle import vec
    from waveform_file_real_v1.audit_oracle import make,mono_matrix,qr_solve
    from waveform_file_real_v1.audit_resources import inspect
    from waveform_trace_audit_v1 import root_frobenius
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],maximum_errors={},inputs={})
    def check(name,x,y,scale=None,gate=2e-12):
        x,y=np.asarray(x),np.asarray(y)
        assert x.shape==y.shape,(name,x.shape,y.shape)
        den=max(1.,float(np.max(abs(y)))) if scale is None else max(float(scale),1e-300)
        error=float(np.max(abs(x-y))/den)
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.))
        assert error<gate,(name,error,gate)
    def ratio(x,y):
        den=float(np.linalg.norm(y))
        return float(np.linalg.norm(x)/den) if den else (0. if not np.count_nonzero(x) else None)
    try:
        source=load(a.study/'report.json')
        r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
        assert source['result']=='waveform_file_real_adapter_known_measured' and len(source['cases'])==4
        for name,digest in source['sources'].items():
            assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for case in source['cases']:
            report_path=a.study/case['report'];capture_path=a.study/case['file']
            assert sha(report_path)==case['report_sha256'] and sha(capture_path)==case['capture_sha256']
            r['inputs'][str(report_path)]=sha(report_path);r['inputs'][str(capture_path)]=sha(capture_path)
            info=load(report_path)
            with np.load(capture_path) as f:z={name:f[name] for name in f.files}
            audio,target=z['audio'],z['target'];positions,old_positions=z['positions'],z['original_positions']
            N,M,H=len(audio),len(positions),len(z['orders']);shape=(M,H,2)
            assert np.array_equal(audio[2048:-2048],target)
            assert np.array_equal(positions[8:-8]-2048,old_positions)
            assert len(positions)==len(old_positions)+16 and len(np.unique(np.diff(old_positions)))>1
            oracle,old=make(audio,target,positions,z['orders'],z['scale'])
            check('locked_target_sigma',z['sigma'],old['sigma'])
            check('locked_target_amplitude',z['amplitude'],old['amplitude'])
            check('locked_target_weights',z['weights'],old['weights'])
            check('locked_target_band_power',z['band_power'],old['band_power'])
            assert np.array_equal(z['floor_active'],old['floor_active'])
            check('context_coverage',z['coverage'],oracle.profile['full_coverage'])
            check('context_time_coverage',z['time_coverage'],oracle.profile['time_coverage'])
            check('target_finite_coverage',oracle.profile['full_coverage'][2048:-2048],old['full_coverage'])
            starts=np.arange(0,N-4096+1,256)
            slots=np.where((starts>=2048)&(starts+4096<=N-2048))[0]
            assert np.array_equal(z['target_slots'],slots)
            check('original_target_spectral_rows',oracle.profile['rows'][slots],old['rows'])
            check('original_curvature',oracle.D[8:-8,8:-8],curvature(old_positions))
            check('all_original_forward_rows',z['probe_forward'],oracle.forward(z['probe_q']))
            check('all_original_adjoint_rows',z['probe_adjoint'],oracle.backward(z['probe_rows']))
            check('all_original_rhs_rows',z['probe_rhs'],np.r_[oracle.target(),np.zeros(len(z['probe_rhs'])-oracle.data_size)])
            check('adjoint_inner_product',z['probe_forward']@z['probe_rows'],z['probe_q']@z['probe_adjoint'])
            # Explicit positive objective decomposition, including crossing windows.
            qp=oracle.nodes(z['probe_q']);wp=synthesize(qp*z['scale'][None],positions,z['orders'],N)
            oldwave=synthesize(qp[8:-8]*z['scale'][None],old_positions,z['orders'],len(target))
            check('original_target_wave_rows',wp[2048:-2048],oldwave)
            ep=wp-audio;data=oracle.spectral(ep)
            raw,_=full_frame(oldwave-target)
            oldrows=raw[old['keep']]*old['amplitude']*old['weights'][None,:,None]
            check('original_target_error_rows',data[slots],oldrows)
            oldD=curvature(old_positions)
            oldpen=.001*np.sum(abs(oldD@qp[8:-8].reshape(M-16,-1))**2)+.000001*np.sum(abs(qp[8:-8])**2)
            oldJ=float(np.sum((oldwave-target)**2)/old['sigma']**2+np.sum(abs(oldrows)**2)+oldpen)
            added=np.ones(len(starts),bool);added[slots]=False
            outerD=oracle.D@qp.reshape(M,-1)
            extras=float(np.sum(ep[:2048]**2)/old['sigma']**2+np.sum(ep[-2048:]**2)/old['sigma']**2
                +np.sum(abs(data[added])**2)+.001*(np.sum(abs(outerD[:8])**2)+np.sum(abs(outerD[-8:])**2))
                +.000001*(np.sum(abs(qp[:8])**2)+np.sum(abs(qp[-8:])**2)))
            newJ=float(np.sum(ep**2)/old['sigma']**2+np.sum(abs(data)**2)+oracle.penalty(qp))
            assert extras>=0
            check('positive_objective_decomposition',newJ,oldJ+extras)
            q=oracle.nodes(z['q'].ravel());x=vec(q)
            wave=synthesize(q*z['scale'][None],positions,z['orders'],N)
            check('independent_full_wave',z['wave'],wave)
            check('independent_fitted_nodes',z['fitted'],q*z['scale'][None])
            L=np.linalg.cholesky(oracle.R)
            def inverse(value,transpose=False):
                q0=oracle.nodes(np.asarray(value).ravel())
                mapped=linalg.solve_triangular(L if transpose else L.T,q0.reshape(M,-1),lower=transpose)
                return vec(mapped.reshape(shape))
            trace=root_frobenius(oracle);normA=trace['root_Frobenius']
            check('independent_all_bin_Frobenius',info['production_original_trace']['root_Frobenius'],normA,scale=normA,gate=2e-11)
            history=[];resource=None;reference_difference=None
            if case['label']!='both_zero':
                B,tail,phi,b=mono_matrix(oracle)
                reference=qr_solve(B,tail,b)
                reference_difference=float(np.linalg.norm(z['q']-reference)/max(np.linalg.norm(reference),1e-300))
                assert reference_difference<2e-7
                check('dense_matrix_forward',B@z['probe_q'].reshape(-1,2),oracle.data_forward(z['probe_q']).reshape(-1,2),gate=2e-8)
                inv=linalg.solve_triangular(L.T,np.eye(M))
                transform=linalg.block_diag(np.kron(inv,np.eye(H)),np.kron(inv,np.eye(H)))
                G=B@transform
                check('explicit_matrix_all_bin_Frobenius',normA,np.sqrt(2*(np.sum(G*G)+2*M*H)),scale=normA,gate=2e-11)
                del B,tail,phi,b,G,transform
                zs,es,gs,ds=(z[name] for name in ('history_z','history_wave','history_original_normal','delta_z'))
                assert zs.shape==gs.shape==(3,2*M*H,2) and ds.shape==(2,2*M*H,2)
                assert np.array_equal(zs[0],z['base_z']) and np.array_equal(es[0],z['base_wave_model_residual'])
                for j in range(3):
                    dm=np.r_[es[j].ravel()/old['sigma'],vec(oracle.spectral(es[j]))]
                    gn=inverse(oracle.data_adjoint(dm),True)+zs[j].ravel()
                    denominator=max(normA*np.linalg.norm(np.r_[dm,zs[j].ravel()]),1e-300)
                    check('history_original_normal_'+str(j),gn,gs[j].ravel(),scale=max(denominator,1.))
                    consistent=oracle.data_forward(inverse(zs[j]))-oracle.target()
                    back=float(np.linalg.norm(consistent-dm)/max(np.linalg.norm(oracle.target()),1e-300))
                    stable=float(np.linalg.norm(gn)/denominator)
                    assert stable<=1e-11 and back<=1e-11
                    history.append(dict(step=j,stable=stable,backward=back))
                    if j==0:
                        pair=dm.reshape(-1,2)
                        side_den=normA/np.sqrt(2)*np.sqrt(np.sum(pair*pair,axis=0)+np.sum(zs[j]*zs[j],axis=0))
                        side_stable=np.linalg.norm(gn.reshape(-1,2),axis=0)/np.maximum(side_den,1e-300)
                        side_back=np.linalg.norm((consistent-dm).reshape(-1,2),axis=0)/np.maximum(np.linalg.norm(oracle.target().reshape(-1,2),axis=0),1e-300)
                        assert np.all(side_stable<=1e-11) and np.all(side_back<=1e-11)
                        check('base_guard_separate_LR_stable',side_stable,info['solver']['stable_root_normal_relative'])
                        check('base_guard_separate_LR_backward',side_back,info['solver']['root_backward_discrepancy'])
                    if j<2:
                        check('node_update_'+str(j),zs[j+1],zs[j]+ds[j])
                        delta=synthesize(oracle.nodes(inverse(ds[j]))*z['scale'][None],positions,z['orders'],N)
                        check('wave_update_'+str(j),es[j+1],es[j]+delta)
                assert np.array_equal(zs[-1],z['z']) and np.array_equal(es[-1],z['wave_model_residual'])
                check('evaluator_complete_stable_normal',history[-1]['stable'],info['original_stable_complete_normal'])
                check('evaluator_complete_backward',history[-1]['backward'],info['original_backward_discrepancy'])
                resource=inspect(info,a.study/case['label'])
            else:
                assert np.count_nonzero(z['q'])==np.count_nonzero(wave)==0
                bad=info['zero_reference_bad_candidate']
                assert bad['metrics']['target_wave_NRMSE'] is None and not bad['fidelity_qualified']
            e=oracle.data_forward(x)-oracle.target()
            normal=oracle.nodes(oracle.data_adjoint(e))+(oracle.R@q.reshape(M,-1)).reshape(shape)
            gradient=float(np.linalg.norm(vec(normal))/max(np.linalg.norm(oracle.data_adjoint(oracle.target())),1e-300))
            check('complete_gradient',gradient,info['original_gradient'])
            cert=oracle.gap(x,info['residual_certificate']['residual_dual_scale'])
            restored=linalg.solve(oracle.R,oracle.nodes(oracle.data_adjoint(z['u'])).reshape(M,-1),assume_a='pos').reshape(shape)
            pc=dict(primal=float(e@e)+oracle.penalty(q),dual_lower_bound=float(2*oracle.target()@z['u']-z['u']@z['u'])-oracle.penalty(restored),
                gap_upper_bound=float((e+z['u'])@(e+z['u']))+oracle.penalty(q-restored))
            for tag,c in (('residual',cert),('representer',pc)):
                for key,value in c.items():check(tag+'_'+key,value,info[tag+'_certificate'][key])
                assert c['gap_upper_bound']<=1e-6*c['primal']+1e-10
            error=wave-audio;rows,ref=oracle.spectral(error),oracle.spectral(audio)
            traw,_=full_frame(error[2048:-2048])
            trows=traw[old['keep']]*old['amplitude']*old['weights'][None,:,None]
            tref=old['rows']*old['weights'][None,:,None]
            bands=np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*16,side='right')
            metrics=dict(whole_wave_NRMSE=ratio(error,audio),target_wave_NRMSE=ratio(error[2048:-2048],target),
                target_supported_band_complex_NRMSE=[ratio(trows[:,bands==b],tref[:,bands==b]) for b in range(6)],
                whole_supported_band_complex_NRMSE=[ratio(rows[:,bands==b],ref[:,bands==b]) for b in range(6)],
                whole_wave_regions_NRMSE=[ratio(error[s],audio[s]) for s in (slice(0,2048),slice(2048,-2048),slice(-2048,None))])
            for key,value in metrics.items():check(key,value,info['metrics'][key])
            assert gradient<2e-7 and info['solver_qualified'] and info['fidelity_qualified']
            assert metrics['target_wave_NRMSE']<.02 and max(metrics['target_supported_band_complex_NRMSE'])<.02
            if case['label']=='silent_right':assert np.count_nonzero(z['q'][:,1])==np.count_nonzero(wave[:,1])==0
            r['cases'].append(dict(label=case['label'],all_qualified=True,positive_objective_terms=extras,
                independent_QR_relative_coefficient_difference=reference_difference,history=history,resources=resource,
                residual_certificate=cert,representer_certificate=pc,metrics=metrics))
            save(a.out/'report.json',r)
            print('AUDIT_ADAPTER',case['label'],'PASS',flush=True)
            del z,oracle,q,wave
            gc.collect()
        r.update(result='independent_waveform_file_real_adapter_verified',all_qualified=True,
            producer_sha256=sha(a.study/'report.json'),no_real_fit_or_C_or_hearing_promotion=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
