"""Independent FIR/polynomial/native-wave checks and same-observer source comparison."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','observation','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import fft,linalg,interpolate
from research_archive_v1 import load,save,sha
from idle_conditioned_detail_v1.features import phases
from idle_phase_amplitude_v1.observe import observe,statistics

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),renders=[])
try:
    report=load(a.input/'report.json');assert report['result']=='finite_phase_aware_amplitude_audio_pending_audit'
    for path,digest in report['inputs'].items():assert sha(path)==digest
    model=load(a.input/'model.json');h=np.array(model['taps']);selected=[1,2,4];step=960
    with np.load(a.observation/'source_train.npz') as f:train=f['aware_log']
    # Different matrix-root and triangular solve implementation of the declared fit.
    w=(1-np.cos(2*np.pi*np.arange(32)/32))/2
    spectra=[]
    for first in range(0,116-31,16):spectra.append(np.fft.rfft(train[first:first+32]*w[:,None],n=64,axis=0))
    S=np.array([sum((np.outer(z[k],z[k].conj()) for z in spectra),np.zeros((3,3),complex))/(6*sum(w*w)) for k in range(33)])
    root=np.array([linalg.sqrtm(s).astype(complex) for s in S]);hp=np.roll(np.fft.irfft(root,n=64,axis=0),32,axis=0)
    target=train.T@train/len(train);raw=sum((z@z.T for z in hp),np.zeros((3,3)))
    change=linalg.solve_triangular(linalg.cholesky(raw,lower=True),np.eye(3),lower=True)
    hp=np.einsum('ij,tjk->tik',linalg.cholesky(target,lower=True)@change,hp)
    r['independent_fit_tap_error']=float(abs(hp-h).max());assert r['independent_fit_tap_error']<2e-12
    curves=[]
    for k in range(51):curves.append(sum((h[j]@h[j+k].T for j in range(64-k)),np.zeros((3,3))))
    curves=np.array(curves);assert abs(curves-np.array(model['predicted_node_covariance_lags'])).max()<1e-12
    # Complete native fractional covariance. Four-point Lagrangian-polynomial form.
    u=np.arange(960)/960
    weight=np.array([-.5*u*(1-u)**2,(1-u)*(1+u-1.5*u*u),.5*u*(1+4*u-3*u*u),-.5*u*u*(1-u)]).T
    cov=np.zeros((960,3,3))
    for j in range(4):
        for k in range(4):
            v=curves[k-j] if k>=j else curves[j-k].T
            cov+=weight[:,j,None,None]*weight[:,k,None,None]*v
    correction=np.array([linalg.cholesky(target,lower=True)@linalg.solve_triangular(linalg.cholesky(c,lower=True),np.eye(3),lower=True) for c in cov])
    with np.load(a.input/'interpolation.npz') as f:
        r['full_fractional_table_error']=float(max(abs(correction-f['transform']).max(),abs(weight-f['weights']).max(),abs(cov-f['raw_covariance']).max()))
    assert r['full_fractional_table_error']<2e-12
    r['full_fractional_covariance_error']=float(abs(np.einsum('fij,fjk,flk->fil',correction,cov,correction)-target).max())
    assert r['full_fractional_covariance_error']<1e-12
    parent=a.workspace/'baselines';phase_root=parent/'idle_phase_recipe_v1/evidence/render2'
    phase_model=load(phase_root/'model.json');profile=load(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    law=load(parent/'idle_local_shape_v1/evidence/fit1/report.json')['law'];beta=np.array(law['coefficients'])
    probability=load(parent/'idle_post_budget_v1/evidence/observe1/report.json')['allocation']['probability']
    amp=np.array(profile['modal']['amplitude_LR']);initial=np.array(profile['modal']['initial_phase_LR']);freq=np.array(profile['modal']['frequencies_hz'])
    M=np.array([[-1.,-1.,1.],[3.,-2.,0.]]);right=linalg.lstsq(M,np.eye(2))[0]
    observation=load(a.observation/'report.json')
    r['source_curves']={v['label']:v['aware'] for v in observation['observations']}
    r['predicted_trace_200ms_correlation']=float(np.trace(curves[10])/np.trace(curves[0]))
    r['same_observer_generated_comparisons']=[]
    for row in report['renders']:
        seed=row['seed'];frames=row['frames'];t=np.arange(frames)/48000
        with np.load(a.input/row['trace']) as f:stored={key:f[key] for key in f.files}
        assert sha(a.input/row['trace'])==row['trace_sha256']
        count=len(stored['nodes']);warm=63;rng=np.random.Generator(np.random.PCG64(seed^0xA1D1E5A39B47))
        white=rng.standard_normal((count+warm,3));values=np.zeros((count,3))
        for i in range(3):
            for j in range(3):values[:,i]+=np.convolve(white[:,j],h[:,i,j])[warm:warm+count]
        node_error=float(abs(values-stored['nodes']).max());assert node_error<1e-12
        xx=np.empty((frames,3))
        for k in range(frames//step):
            v0,v1,v2,v3=values[k+1:k+5]
            raw=.5*(2*v1+u[:,None]*((-v0+v2)+u[:,None]*((2*v0-5*v1+4*v2-v3)+u[:,None]*(-v0+3*v1-3*v2+v3))))
            xx[k*step:(k+1)*step]=np.einsum('fij,fj->fi',correction,raw)
        native_error=float(abs(xx-stored['native_log']).max());assert native_error<1e-12
        with np.load(phase_root/f'motion_{seed}.npz') as f:coordinates=f['coordinate_nodes']
        motion=interpolate.make_interp_spline((np.arange(len(coordinates))-2)/200,coordinates,bc_type='natural')
        angles=(phase_model['carrier_phase_rad']+2*np.pi*phase_model['carrier_hz']*t)[:,None]*[2.,3.,5.]+motion(t)@right.T
        z=np.exp(1j*angles)
        feature=np.column_stack((z,z[:,1]*z[:,0].conj(),z[:,2]*z[:,0].conj(),z[:,2]*z[:,1].conj()))
        q=np.exp(beta[0]+np.column_stack((feature.real,feature.imag))@beta[1:])
        q_error=float(abs(q-stored['q']).max());assert q_error<1e-9
        main=np.zeros((frames,2));components=[]
        for mode in range(13):
            angle=angles[:,selected.index(mode)] if mode in selected else 2*np.pi*np.remainder(t*freq[mode],1)+initial[mode,0]
            component=np.cos(angle[:,None]+[0.,initial[mode,1]-initial[mode,0]])*amp[mode]
            main+=component
            if mode in selected:components.append(component)
        detail=np.zeros_like(main);n=frames+profile['warmup_frames'];start=profile['warmup_frames']
        mask=(1<<64)-1
        for index,kernel in enumerate(profile['kernels']):
            key=seed^((0x9E3779B97F4A7C15*(index+1))&mask)
            if index<2:excitation=np.random.Generator(np.random.PCG64(key^0x794323AA)).standard_normal(n)
            else:
                uniform=np.random.Generator(np.random.PCG64(key^0x94D049BB133111EB)).random(n)
                normal=np.random.Generator(np.random.PCG64(key^0xD1B54A32D192ED03)).standard_normal(n)
                p0=probability[index-2];excitation=np.where(uniform<p0,normal/np.sqrt(p0),0.)
            taps=np.array(kernel['taps']);length=fft.next_fast_len(n+len(taps)-1)
            y=fft.irfft(fft.rfft(excitation,length)*fft.rfft(taps,length),length)[start:n]*kernel['gain']
            if index>=2:y*=np.sqrt(q[:,index-2])
            detail+=y[:,None]*[1.,kernel['right_over_left']]
        errors={};all_observed={}
        for amount in [0.,.5,1.]:
            g=np.exp(amount*xx-amount*amount*np.diag(target));new_main=main.copy()
            for j,v in enumerate(components):new_main+=(g[:,j,None]-1)*v
            for bus,y in [('main',new_main),('mix',new_main+detail)]:
                entry=row['files'][bus+'_'+str(amount)];path=a.input/entry['file'];assert sha(path)==entry['sha256']
                saved,rate=sf.read(path,always_2d=True);assert rate==48000 and len(saved)==frames
                error=float(abs(y-saved).max());errors[bus+'_'+str(amount)]=error
                assert error<3.1e-8,(seed,bus,amount,error)
                if bus=='mix':all_observed[str(amount)]=saved
        # Same measured-acoustic observer on ALL eight non-overlapping3s blocks per amount.
        for amount,wave in all_observed.items():
            portions=[]
            for first in range(0,frames,144000):
                audio=wave[first:first+144000];z0=phases(audio[:,0],freq[selected])
                result=observe(audio,freq,z0);summary,x=statistics(result['coefficients']);portions.append(summary)
            r['same_observer_generated_comparisons'].append(dict(seed=seed,amount=amount,portions=portions,
                median_observed_std=np.median([p['raw_log_std'] for p in portions],axis=0).tolist(),
                median_trace_200ms_correlation=float(np.median([p['trace_200ms_correlation'] for p in portions]))))
        r['renders'].append(dict(seed=seed,node_error=node_error,full_native_log_error=native_error,
                                 full_native_q_error=q_error,full_native_waveform_errors_FS=errors))
        save(a.out/'report.json',r);print(r['renders'][-1],flush=True)
    r.update(result='passed',all_native_frames_verified=True,all_source_observer_windows_QR_separate=True,
             source_CHECK_not_fitted=True,same_observer_blocks=72,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
