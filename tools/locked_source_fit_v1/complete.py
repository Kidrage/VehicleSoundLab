"""Dimension-generic independent complete equations and locked-target scores.

No production solver, source adapter, synthesis or correction imports.
Legacy metric_target calibrates the metric; new audio supplies every data RHS.
The separate CLI first qualifies all equations on three new known captures.
"""
from pathlib import Path
import numpy as np
from scipy import linalg
from research_archive_v1 import load,sha
from observer_complete_v1.audit_oracle import full_frame
from observer_frequency_v1.reduced_oracle import synthesize
from observer_supported_v1.full_oracle import vec
from waveform_trace_audit_v1 import root_frobenius
from .oracle import make
from waveform_file_real_v1.audit_resources import inspect
from waveform_real_guard_v1.locked import audit_guard


def verify(directory):
    directory=Path(directory)
    source=load(directory/'report.json')
    assert sha(directory/'capture.npz')==source['capture_sha256']
    with np.load(directory/'capture.npz') as f:z={n:f[n] for n in f.files}
    if 'prepared_file' in source:
        assert sha(source['prepared_file'])==source['prepared_sha256']
        with np.load(source['prepared_file']) as original:
            for name in original.files:assert np.array_equal(z[name],original[name]),name
    oracle,old=make(z['audio'],z['metric_target'],z['positions'],z['orders'],z['scale'])
    N,M,H=len(z['audio']),len(z['positions']),len(z['orders']);shape=(M,H,2);n=2*M*H
    errors={}
    def check(name,x,y,scale=1.,gate=2e-8):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
        error=float(np.max(abs(x-y))/max(float(scale),1e-300))
        errors[name]=error;assert error<gate,(name,error,gate)
    for name,key in (('weights','weights'),('band_power','band_power'),('sigma','sigma'),('amplitude','amplitude')):
        check('original_target_'+name,z[name],old[key],max(1.,float(np.max(abs(old[key])))),gate=2e-12)
    assert np.array_equal(z['floor_active'],old['floor_active'])
    assert np.array_equal(z['audio'][2048:-2048],z['target'])
    L=np.linalg.cholesky(oracle.R)
    def inverse(v,transpose=False):
        nodes=oracle.nodes(np.asarray(v).ravel())
        return vec(linalg.solve_triangular(L if transpose else L.T,nodes.reshape(M,-1),lower=transpose).reshape(shape))
    q=z['fitted']/z['scale'][None];x=vec(q)
    root=vec((L.T@q.reshape(M,-1)).reshape(shape))
    check('independent_LR_interleave',x,z['q'].ravel(),max(1.,np.linalg.norm(x)),gate=2e-12)
    check('packed_penalty_root',root,z['z'].ravel(),max(1.,np.linalg.norm(root)),gate=2e-12)
    wave=synthesize(z['fitted'],z['positions'],z['orders'],N)
    check('all_order_scalar_waveform',wave,z['wave'])
    direct=np.r_[oracle.data_forward(inverse(root))-oracle.target(),root]
    wm=z['wave_model_residual']
    dm=np.r_[wm.ravel()/old['sigma'],vec(oracle.spectral(wm))]
    model=np.r_[dm,root]
    normal=inverse(oracle.data_adjoint(dm),True)+root
    trace=root_frobenius(oracle);normA=trace['root_Frobenius']
    check('complete_original_model',model,z['original_model_residual'],max(1.,np.linalg.norm(oracle.target())))
    check('complete_original_adjoint',normal,z['original_model_normal'],max(1.,normA*np.linalg.norm(oracle.target())))
    stable=float(np.linalg.norm(normal)/max(normA*np.linalg.norm(model),1e-300))
    backward=float(np.linalg.norm(direct-model)/max(np.linalg.norm(oracle.target()),1e-300))
    trace_difference=abs(normA-source['production_original_trace']['root_Frobenius'])/normA
    assert trace_difference<2e-11
    e=oracle.data_forward(x)-oracle.target()
    gradient_nodes=oracle.nodes(oracle.data_adjoint(e))+(oracle.R@q.reshape(M,-1)).reshape(shape)
    gradient=float(np.linalg.norm(vec(gradient_nodes))/max(np.linalg.norm(oracle.data_adjoint(oracle.target())),1e-300))
    check('complete_gradient',gradient,source['original_gradient'])
    check('complete_stable',stable,source['original_stable_complete_normal'])
    check('complete_backward',backward,source['original_backward_discrepancy'])
    cert=oracle.gap(x,source['residual_certificate']['residual_dual_scale'])
    restored=linalg.solve(oracle.R,oracle.nodes(oracle.data_adjoint(z['u'])).reshape(M,-1),assume_a='pos').reshape(shape)
    pc=dict(primal=float(e@e)+oracle.penalty(q),dual_lower_bound=float(2*oracle.target()@z['u']-z['u']@z['u'])-oracle.penalty(restored),
        gap_upper_bound=float((e+z['u'])@(e+z['u']))+oracle.penalty(q-restored))
    gaps=[]
    for tag,c in (('residual',cert),('representer',pc)):
        for name,value in c.items():check(tag+'_'+name,value,source[tag+'_certificate'][name],max(1.,abs(value)))
        passed=bool(c['gap_upper_bound']<=1e-6*c['primal']+1e-10)
        assert passed==source[tag+'_certificate']['additional_gap_gate_passed'];gaps.append(passed)
    qualified=bool(gradient<2e-7 and stable<=1e-11 and backward<=1e-11 and all(gaps) and source['solver']['stable_root_guard_passed'])
    assert qualified==source['solver_qualified']
    error=wave-z['audio'];rows,ref=oracle.spectral(error),oracle.spectral(z['audio'])
    target_rows,_=full_frame(error[2048:-2048])
    target_rows=target_rows[old['keep']]*old['amplitude']*old['weights'][None,:,None]
    target_ref,_=full_frame(z['target'])
    target_ref=target_ref[old['keep']]*old['amplitude']*old['weights'][None,:,None]
    bands=np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*16,side='right')
    def ratio(a,b):
        den=float(np.linalg.norm(b))
        return float(np.linalg.norm(a)/den) if den else (0. if not np.count_nonzero(a) else None)
    metrics=dict(whole_wave_NRMSE=ratio(error,z['audio']),target_wave_NRMSE=ratio(error[2048:-2048],z['target']),
        target_supported_band_complex_NRMSE=[ratio(target_rows[:,bands==b],target_ref[:,bands==b]) for b in range(6)],
        whole_supported_band_complex_NRMSE=[ratio(rows[:,bands==b],ref[:,bands==b]) for b in range(6)],
        whole_wave_regions_NRMSE=[ratio(error[s],z['audio'][s]) for s in (slice(0,2048),slice(2048,-2048),slice(-2048,None))])
    for name,value in metrics.items():check(name,value,source['metrics'][name],gate=2e-12)
    fidelity=bool(metrics['target_wave_NRMSE'] is not None and metrics['target_wave_NRMSE']<.02
        and all(v is not None and v<.02 for v in metrics['target_supported_band_complex_NRMSE']))
    assert fidelity==source['fidelity_qualified']
    history=[]
    zs,es,gs,ds=(z[k] for k in ('history_z','history_wave','history_original_normal','delta_z'))
    assert zs.shape==gs.shape==(3,n,2) and es.shape==(3,N,2) and ds.shape==(2,n,2)
    assert np.array_equal(zs[0],z['base_z']) and np.array_equal(es[0],z['base_wave_model_residual'])
    for j in range(3):
        dm=np.r_[es[j].ravel()/old['sigma'],vec(oracle.spectral(es[j]))]
        gn=inverse(oracle.data_adjoint(dm),True)+zs[j].ravel()
        den=max(normA*np.linalg.norm(np.r_[dm,zs[j].ravel()]),1e-300)
        check('history_original_normal_'+str(j),gn,gs[j].ravel(),max(den,1.),gate=2e-12)
        consistent=oracle.data_forward(inverse(zs[j]))-oracle.target()
        back=float(np.linalg.norm(consistent-dm)/max(np.linalg.norm(oracle.target()),1e-300))
        st=float(np.linalg.norm(gn)/den)
        # Preserve failures as measurements; agreement never promotes a failed gate.
        history.append(dict(step=j,stable_complete_normal=st,backward=back,
            original_gates_passed=bool(st<=1e-11 and back<=1e-11)))
        if j==0:
            dm2=dm.reshape(-1,2)
            side_den=normA/np.sqrt(2)*np.sqrt(np.sum(dm2*dm2,axis=0)+np.sum(zs[j]**2,axis=0))
            side_stable=np.linalg.norm(gn.reshape(n,2),axis=0)/np.maximum(side_den,1e-300)
            side_back=np.linalg.norm((consistent-dm).reshape(-1,2),axis=0)/np.maximum(np.linalg.norm(oracle.target().reshape(-1,2),axis=0),1e-300)
            # The original FFT composite and the declared rounded band-root
            # metric have separate guards; cross-operator equality was the
            # retained original audit failure, not a reason to enlarge gates.
            guard=audit_guard(z,source,oracle)
            check('base_guard_separate_LR_stable',guard['stable_LR'],source['solver']['stable_root_normal_relative'],gate=2e-12)
            check('base_guard_separate_LR_backward',guard['backward_LR'],source['solver']['root_backward_discrepancy'],gate=2e-12)
            guard['independent_original_FFT_stable_LR']=side_stable.tolist()
            guard['independent_original_FFT_backward_LR']=side_back.tolist()
            assert np.all(side_stable<=1e-11) and np.all(side_back<=1e-11)
            assert guard['stable_guard_passed'] and guard['backward_guard_passed']
        if j<2:
            check('node_update_'+str(j),zs[j+1],zs[j]+ds[j],gate=2e-12)
            delta=synthesize(oracle.nodes(inverse(ds[j]))*z['scale'][None],z['positions'],z['orders'],N)
            check('wave_update_'+str(j),es[j+1],es[j]+delta,gate=2e-12)
    assert np.array_equal(zs[-1],z['z']) and np.array_equal(es[-1],z['wave_model_residual'])
    resources=inspect(source,directory)
    assert resources['registered_peak_bytes']<=source['resource_preflight']['main_phase_array_allowance']
    if not np.count_nonzero(z['audio'][:,1]):
        assert np.count_nonzero(z['q'][:,1])==np.count_nonzero(wave[:,1])==0
    return dict(result='independent_locked_source_case_verified',verification_passed=True,
        all_qualified=bool(qualified and fidelity and resources['all_qualified']),solver_qualified=qualified,fidelity_qualified=fidelity,
        gradient=gradient,stable_original_complete_normal=stable,original_backward=backward,
        residual_certificate=cert,representer_certificate=pc,metrics=metrics,original_correction_history=history,
        independent_all_bin_trace=trace,trace_relative_difference=float(trace_difference),maximum_errors=errors,
        file_resource_audit=resources,independent_base_guard=guard,producer_sha256=sha(directory/'report.json'),
        capture_sha256=sha(directory/'capture.npz'),no_new_sustained_voice_or_C_or_hearing_qualification=True)
