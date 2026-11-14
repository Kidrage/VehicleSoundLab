"""Independent complete FFT synthesis, source observations and covariance budgets."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal,interpolate
from research_archive_v1 import load,save,sha

MASK=(1<<64)-1
def oscillator_features(z):
    angle=np.column_stack((np.angle(z),np.angle(z[:,1]*z[:,0].conj()),
        np.angle(z[:,2]*z[:,0].conj()),np.angle(z[:,2]*z[:,1].conj())))
    return np.column_stack((np.cos(angle),np.sin(angle)))
def independent_low_impulse(crossover):
    k=np.tan(np.pi*crossover/48000);b=k/(1+k);pole=(1-k)/(1+k)
    h=np.empty(1025);h[0]=b;h[1:]=b*(1+pole)*pole**np.arange(1024)
    return h,pole
def linear_law(feature,beta):
    beta=np.asarray(beta);out=np.tile(beta[0],(len(feature),1))
    for j in range(12):out+=feature[:,j,None]*beta[j+1]
    return out

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(Path(__file__),a.out/'executed_auditor.py')
r=dict(result='running',input_report_sha256=sha(a.input/'report.json'),source_checks=[],renders=[])
try:
    report=load(a.input/'report.json');assert report['result']=='finite_phase_conditioned_shape_candidate_pending_audit_and_hearing'
    for name,digest in report['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    for name,digest in report['inputs'].items():assert sha(name)==digest
    parent=a.workspace/'baselines';profile=load(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    model=load(a.input/'model.json');assert sha(a.input/'model.json')==report['model_sha256']
    origin=parent/'idle_conditioned_detail_v1/evidence/observe1'
    # Independent source filtering, features and all final Newton stationarity checks.
    for row in report['fits']:
        label='source' if row['seed'] is None else 'phase_'+str(row['seed'])
        for part in ['train','check']:
            with np.load(origin/(part+'.npz')) as f:audio=f['audio'];z=f['phasors']
            if row['seed'] is not None:
                fft=np.fft.rfft(audio,axis=0);rng=np.random.Generator(np.random.PCG64(row['seed']))
                phase=rng.uniform(-np.pi,np.pi,len(fft));phase[[0,-1]]=0
                audio=np.fft.irfft(fft*np.exp(1j*phase[:,None]),n=len(audio),axis=0)
                with np.load(origin/f"{part}_phase_{row['seed']}.npz") as f:z=f['phasors']
            with np.load(a.input/(label+'_'+part+'.npz')) as f:
                feature=f['feature'];power=f['power'];sections=f['sos'];filtered=f['filtered']
            expected_feature=oscillator_features(z)[12000:-12000]
            feature_error=float(abs(feature-expected_feature).max());assert feature_error<1e-12
            streams=[]
            for band,sos in zip(model['bands_hz'],sections):
                y=audio[:,0].copy()
                for b0,b1,b2,a0,a1,a2 in sos:y=signal.lfilter([b0,b1,b2],[a0,a1,a2],y)
                impulse,_=independent_low_impulse(sum(band)/2)
                lo=signal.fftconvolve(y,impulse)[:len(y)];streams.extend((lo,y-lo))
            expected=np.array(streams).T[12000:-12000]
            filter_error=float(abs(expected-filtered).max());assert filter_error<2e-11
            power_error=float(abs(expected**2-power).max());assert power_error<1e-12
            prediction=np.exp(linear_law(expected_feature,row['model']['coefficients']))
            if part=='train':
                target=power/row['model']['reference_power'];design=np.column_stack((np.ones(len(feature)),expected_feature))
                gradient=design.T@(prediction-target)/len(feature)
                assert abs(gradient).max()<1.01e-9
                assert np.linalg.matrix_rank(design)==13
                if row['seed'] is None:
                    b=np.asarray(row['model']['coefficients']);delta=b[:,0::2]-b[:,1::2]
                    center=delta[0]+expected_feature.mean(axis=0)@delta[1:];delta[0]-=center
                    assert abs(delta-model['coefficients']).max()<1e-12
            r['source_checks'].append(dict(label=label+'_'+part,feature_error=feature_error,
                independent_filter_error=filter_error,power_error=power_error))
    effective=[];grams=[];tail_bounds=[]
    for kernel,branch in zip(profile['kernels'][2:],model['branches']):
        h=np.asarray(kernel['taps']);impulse,pole=independent_low_impulse(branch['crossover_hz'])
        lo=np.convolve(h,impulse);original=np.r_[h,np.zeros(1024)];hi=original-lo
        g=np.array([[lo@lo,lo@hi],[hi@lo,hi@hi]])
        assert abs(g-branch['gram']).max()<1e-12 and np.linalg.eigvalsh(g).min()>0
        assert abs(float(original@original)-branch['variance'])<1e-12
        omitted=2*lo[-1]**2*pole**2/(1-pole**2)
        assert omitted<branch['variance']*1e-24
        effective.append((lo,hi));grams.append(g);tail_bounds.append(float(omitted))
    r['analytic_response_tail_variance_bounds']=tail_bounds
    frequencies=np.asarray(profile['modal']['frequencies_hz']);amplitude=np.asarray(profile['modal']['amplitude_LR']);initial=np.asarray(profile['modal']['initial_phase_LR'])
    for row in report['renders']:
        seed=row['seed'];frames=24*48000;warm=profile['warmup_frames'];count=frames+warm
        with np.load(parent/f'idle_phase_recipe_v1/evidence/render2/motion_{seed}.npz') as f:values=f['coordinate_nodes']
        phase_model=report['phase_model'];node_time=(np.arange(len(values))-2)/phase_model['node_rate']
        motion=interpolate.make_interp_spline(node_time,values,k=3,bc_type='natural')
        trace_path=a.input/row['trace_file'];assert sha(trace_path)==row['trace_sha256']
        with np.load(trace_path) as f:traces={name:f[name] for name in f.files}
        main=np.zeros((frames,2));q=np.empty((frames,4));delta=np.empty_like(q)
        for start in range(0,frames,48000):
            stop=min(frames,start+48000);t=np.arange(start,stop)/48000
            u=motion(t);phi=phase_model['carrier_phase_rad']+2*np.pi*phase_model['carrier_hz']*t
            constraints=np.array([[-1.,-1.,1.],[3.,-2.,0.],[2.,3.,5.]])
            theta=np.linalg.solve(constraints,np.column_stack((u,38*phi)).T).T
            z=np.exp(1j*theta);feature=oscillator_features(z)
            q[start:stop]=np.exp(linear_law(feature,report['law']['coefficients']))
            delta[start:stop]=linear_law(feature,model['coefficients'])
            for index,freq in enumerate(frequencies):
                for channel in range(2):
                    angle=theta[:,[1,2,4].index(index)]+initial[index,channel]-initial[index,0] if index in [1,2,4] else 2*np.pi*freq*t+initial[index,channel]
                    main[start:stop,channel]+=amplitude[index,channel]*np.cos(angle)
        q_error=float(abs(q-traces['q']).max());delta_error=float(abs(delta-traces['delta']).max())
        assert q_error<1e-9 and delta_error<1e-9
        details={str(s):np.zeros_like(main) for s in [0.,.5,1.]};branch_error=direct_error=variance_error=0.
        for index,kernel in enumerate(profile['kernels']):
            key=seed^(0x9E3779B97F4A7C15*(index+1)&MASK)
            if index<2:excitation=np.random.Generator(np.random.PCG64(key^0x794323AA)).standard_normal(count)
            else:
                p=report['probability'][index-2]
                u=np.random.Generator(np.random.PCG64(key^0x94D049BB133111EB)).random(count)
                n=np.random.Generator(np.random.PCG64(key^0xD1B54A32D192ED03)).standard_normal(count)
                excitation=np.where(u<p,n/p**.5,0.)
            h=np.asarray(kernel['taps']);original=signal.fftconvolve(excitation,h)[:count]*kernel['gain']
            ratio=np.array([1.,kernel['right_over_left']])
            for point in [warm,warm+1,warm+511,warm+512,warm+8191,warm+48000,count-1]:
                expected=excitation[point-np.arange(len(h))]@h*kernel['gain']
                direct_error=max(direct_error,abs(float(expected-original[point])))
            if index<2:
                for detail in details.values():detail+=original[warm:,None]*ratio
                continue
            lo=signal.fftconvolve(excitation,effective[index-2][0])[:count]*kernel['gain']
            hi=signal.fftconvolve(excitation,effective[index-2][1])[:count]*kernel['gain']
            actual=np.column_stack((original[warm:],lo[warm:],hi[warm:]))
            branch_error=max(branch_error,float(abs(actual-traces['branches'][index-2]).max()))
            g=grams[index-2];total=float(np.sum(g));d=delta[:,index-2];root=np.sqrt(q[:,index-2])
            for amount in [0.,.5,1.]:
                if amount==0:y=original[warm:]
                else:
                    weights=np.column_stack((np.exp(amount*d/4),np.exp(-amount*d/4)))
                    v=np.einsum('ni,ij,nj->n',weights,g,weights);weights/=np.sqrt(v/total)[:,None]
                    budget=np.einsum('ni,ij,nj->n',weights,g,weights)
                    variance_error=max(variance_error,float(abs(budget-total).max()))
                    y=weights[:,0]*lo[warm:]+weights[:,1]*hi[warm:]
                details[str(amount)]+=y[:,None]*root[:,None]*ratio
        assert branch_error<1e-12 and direct_error<1e-12 and variance_error<1e-12
        errors={}
        for name,item in row['files'].items():
            path=a.input/item['file'];assert sha(path)==item['sha256']
            actual,rate=sf.read(path,always_2d=True);assert rate==48000 and len(actual)==frames and np.isfinite(actual).all()
            if name=='main':expected=main
            else:
                bus,amount=name.split('_');expected=details[amount] if bus=='detail' else main+details[amount]
            error=float(abs(actual-expected).max());assert error<3e-8,(seed,name,error)
            assert abs(actual).max()<1.;errors[name]=error
        old,rate=sf.read(row['old_frozen_mix_comparison']['reference'],frames=frames,always_2d=True)
        zero=sf.read(a.input/row['files']['mix_0.0']['file'],always_2d=True)[0]
        assert np.array_equal(old,zero)
        r['renders'].append(dict(seed=seed,all_native_wave_errors=errors,q_error=q_error,delta_error=delta_error,
            full_branch_error=branch_error,selected_direct_FIR_error=direct_error,
            conditional_variance_error=variance_error,frozen_zero_samples_exact=True))
        save(a.out/'report.json',r);print(dict(seed=seed,errors=errors),flush=True)
    old=load(parent/'idle_microtexture_c_v1/inputs/C_files_sha256.json');voices=load(parent/'idle_microtexture_c_v1/inputs/voice_files_sha256.json')
    assert all(sha(repo/name)==digest for name,digest in {**old,**voices}.items())
    r.update(result='passed',complete_all3seeds_all3amounts_native_waves=True,all8source_control_observations_checked=True,
        old612C_H_and67voices_exact=True,no_C_or_default_changed=True,
        scope='Independent full waveform/response/source implementation audit, not exact source temporal statistics, CPU or human hearing acceptance.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],seeds=len(r['renders'])),flush=True)
