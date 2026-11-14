"""Independent residual compiler/finite expectation and complete native audio checks."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','partition','model','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import fft,signal,ndimage,linalg,interpolate
from research_archive_v1 import load,save,sha
from idle_phase_amplitude_v1.observe import observe,statistics
from idle_conditioned_detail_v1.features import phases

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),compile_sha256=sha(a.model/'report.json'),renders=[],observations=[])
bands=np.array([[0,30],[30,120],[120,400],[400,1200],[1200,2200],[2200,4000],[4000,8000],[8000,14000],[14000,24000.000001]])


def expected(h,envelope):
    h=np.asarray(h);n=len(envelope);w=signal.windows.hann(n,sym=False)
    ac=signal.correlate(envelope*w,envelope*w,method='fft')[n-1:n-1+len(h)]
    hc=signal.correlate(h,h,method='direct')[len(h)-1:]
    spectrum=hc*ac;k=np.zeros(n);k[:len(h)]=spectrum
    for j in range(1,len(h)):k[-j]=spectrum[j]
    result=np.fft.rfft(k).real/(n*np.dot(w,w));result[1:len(result)-(1 if n%2==0 else 0)]*=2
    hz=np.fft.rfftfreq(n,1/48000)
    return np.array([result[(hz>=lo)&(hz<hi)].sum() for lo,hi in bands]),result


try:
    compilation=load(a.model/'report.json');render=load(a.input/'report.json');model=load(a.model/'model.json')
    assert compilation['result']=='joint_coherent_and_low_residual_budget_compiled'
    assert render['result']=='finite_idle_joint_budget_pending_audit'
    for report in [compilation,render]:
        for path,digest in report['inputs'].items():assert sha(path)==digest
    # Independent expected-spectrum controls: explicit every-input DFT and both odd/even lengths.
    r['known']=[]
    for n in [80,81]:
        h=np.array([.7,-.2,.1,.05]);t=np.arange(n);envelope=1+.2*np.cos(2*np.pi*t/n)+.1*np.sin(6*np.pi*t/n)
        w=signal.windows.hann(n,sym=False);A=np.zeros((n,n+len(h)-1))
        for i in range(n):
            for j in range(len(h)):A[i,i+len(h)-1-j]=h[j]*w[i]*envelope[i]
        D=np.exp(-2j*np.pi*np.arange(n//2+1)[:,None]*np.arange(n)/n)
        oracle=np.sum(abs(D@A)**2,axis=1)/(n*np.dot(w,w));oracle[1:len(oracle)-(1 if n%2==0 else 0)]*=2
        _,actual=expected(h,envelope);error=float(abs(actual-oracle).max());assert error<1e-12
        r['known'].append(dict(frames=n,all_DFT_bins_error=error))
    parent=a.workspace/'baselines';profile=load(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    report=load(a.partition/'report.json');train=next(row for row in report['cases'] if row['label']=='source_train')
    with np.load(a.partition/train['file']) as f:residual=f['dynamic_residual'];variable=f['variable_coefficients'];ratio=f['stereo_ratio']
    main=np.sqrt(np.mean(abs(variable)**2,axis=0));main=np.column_stack((main,main*abs(ratio)))
    assert abs(main-np.array(model['main_amplitude_LR'])).max()<1e-12
    # Independent seven-window direct DFT residual shape and reflected Gaussian weights.
    hann=signal.windows.hann(24000,sym=False);sections=list(range(0,len(residual)-23999,12000));assert len(sections)==7
    density=sum(abs(np.fft.rfft(residual[j:j+24000,0]*hann))**2 for j in sections)/(7*48000*np.dot(hann,hann))
    hz=np.fft.rfftfreq(24000,1/48000);f=np.fft.rfftfreq(65536,1/48000);sigma=8*65536/48000
    radius=int(4*sigma+.5);gaussian=np.exp(-.5*(np.arange(-radius,radius+1)/sigma)**2);gaussian/=gaussian.sum()
    density=ndimage.convolve1d(np.interp(f,hz,density),gaussian,mode='reflect');hs=[]
    for kernel in model['kernels']:
        lo,hi=kernel['band_hz'];pad=(hi-lo)/10;mask=np.zeros(len(f));mask[(f>=lo)&(f<=hi)]=1
        left=(f>lo-pad)&(f<lo);right=(f>hi)&(f<hi+pad)
        mask[left]=np.sin(np.pi*(f[left]-lo+pad)/(2*pad))**2;mask[right]=np.cos(np.pi*(f[right]-hi)/(2*pad))**2
        one=density*mask;power=np.r_[one,one[-2:0:-1]];c=np.fft.ifft(.5*np.log(np.maximum(power,1e-30))).real
        c[1:32768]*=2;c[32769:]=0;h=np.fft.ifft(np.exp(np.fft.fft(c))).real[:8192];h/=np.linalg.norm(h);hs.append(h)
    r['all_filter_taps_error']=float(max(abs(h-np.array(k['taps'])).max() for h,k in zip(hs,model['kernels'])))
    assert r['all_filter_taps_error']<2e-12
    law=load(parent/'idle_local_shape_v1/evidence/fit1/report.json')['law'];beta=np.array(law['coefficients'])
    with np.load(a.model/'spectra.npz') as file:spectra={k:file[k] for k in file.files}
    r['source_spectrum_checks']=[]
    for part in ['train','check']:
        row=next(v for v in report['cases'] if v['label']=='source_'+part)
        with np.load(a.partition/row['file']) as file:z=file['phasors'][21600:122400]
        feature=np.column_stack((z,z[:,1]*z[:,0].conj(),z[:,2]*z[:,0].conj(),z[:,2]*z[:,1].conj()))
        q=np.exp(beta[0]+np.column_stack((feature.real,feature.imag))@beta[1:]);assert abs(q-spectra[part+'_q']).max()<1e-12
        upper=np.zeros((9,2));error=0.
        for j,kernel in enumerate(profile['kernels'][2:]):
            power,spectrum=expected(kernel['taps'],np.sqrt(q[:,j]));error=max(error,float(abs(spectrum-spectra[part+'_upper_spectra'][j]).max()))
            upper+=power[:,None]*kernel['gain']**2*np.array([1.,kernel['right_over_left']**2])
        low=np.column_stack([expected(h,np.ones(len(z)))[0] for h in hs]);target=np.array(row['budgets']['dynamic']['residual'])
        if part=='train':
            squared=np.column_stack([linalg.solve(low[[2,3]],(target-upper)[[2,3],channel]) for channel in range(2)])
            assert abs(squared-np.array(model['gains_squared_LR'])).max()<1e-12 and np.all(squared>0)
        prediction=upper+low@squared;record=next(x for x in compilation['assessment'] if x['part']==part)
        assert abs(prediction-np.array(record['predicted_residual_power_LR'])).max()<1e-12
        assert error<1e-12
        r['source_spectrum_checks'].append(dict(part=part,all_expected_spectral_bins_error=error,
            all9band_error_dB=(10*np.log10(prediction/target)).tolist()))
    # Reuse frozen independently audited AM native values; assert identical model/code/nodes.
    am_root=parent/'idle_phase_amplitude_v1/evidence/render2';am_report=load(am_root/'report.json')
    assert sha(repo/'tools/idle_phase_amplitude_v1/model.py')==am_report['sources']['tools/idle_phase_amplitude_v1/model.py']
    am_model=load(am_root/'model.json');cov=np.array(am_model['training_covariance'])
    previous_root=parent/'idle_phase_amplitude_v1/evidence/residual_render1';previous=load(previous_root/'report.json')
    oldhs=load(previous_root/'model.json')['taps'];phase_root=parent/'idle_phase_recipe_v1/evidence/render2'
    phase_model=load(phase_root/'model.json');selected=[1,2,4];oldamp=np.array(profile['modal']['amplitude_LR'])[selected]
    delta=np.diff(np.array(profile['modal']['initial_phase_LR'])[selected],axis=1)[:,0]
    right=linalg.lstsq(np.array([[-1.,-1.,1.],[3.,-2.,0.]]),np.eye(2))[0]
    for row,previous_row in zip(render['renders'],previous['renders']):
        seed=row['seed'];frames=row['frames'];t=np.arange(frames)/48000
        assert sha(a.input/row['nodes_file'])==row['nodes_sha256']
        with np.load(a.input/row['nodes_file']) as file:nodes=file['nodes']
        with np.load(am_root/f'trace_{seed}.npz') as file:
            assert abs(nodes-file['nodes']).max()<1e-12;x=file['native_log']
        with np.load(phase_root/f'motion_{seed}.npz') as file:coords=file['coordinate_nodes']
        motion=interpolate.make_interp_spline((np.arange(len(coords))-2)/200,coords,bc_type='natural')
        angles=(phase_model['carrier_phase_rad']+2*np.pi*phase_model['carrier_hz']*t)[:,None]*[2.,3.,5.]+motion(t)@right.T
        z=np.exp(1j*angles)
        base,_=sf.read(previous_root/previous_row['files']['mix_0.5']['file'],always_2d=True)
        oldmain,_=sf.read(previous_root/previous_row['files']['main_0.5']['file'],always_2d=True)
        lowdelta=np.zeros_like(base);count=frames+profile['warmup_frames'];warm=profile['warmup_frames'];mask=(1<<64)-1
        for j,kernel in enumerate(model['kernels']):
            key=seed^((0x9E3779B97F4A7C15*(j+1))&mask)
            noise=np.random.Generator(np.random.PCG64(key^0x794323AA)).standard_normal(count)
            n=fft.next_fast_len(count+8192-1);source=fft.rfft(noise,n)
            before=profile['kernels'][j]
            old=fft.irfft(source*fft.rfft(oldhs[j],n),n)[warm:count]*before['gain']
            new=fft.irfft(source*fft.rfft(hs[j],n),n)[warm:count]*kernel['gain']
            lowdelta+=new[:,None]*[1.,kernel['right_over_left']]-old[:,None]*[1.,before['right_over_left']]
        errors={}
        for condition,amount in [('0.0',None),('0.5',0.),('1.0',1.)]:
            newmain=oldmain.copy()
            if amount is not None:
                g=np.exp(amount*x-amount**2*np.diag(cov))
                for channel in range(2):newmain[:,channel]+=np.sum((z*np.exp(1j*delta*channel)).real*(main[:,channel]*g-oldamp[:,channel]),axis=1)
            mix=base if amount is None else base+lowdelta+newmain-oldmain
            for bus,wanted in [('mix',mix),('main',newmain)]:
                entry=row['files'][bus+'_'+condition];path=a.input/entry['file'];assert sha(path)==entry['sha256']
                actual,rate=sf.read(path,always_2d=True);assert rate==48000 and len(actual)==frames
                error=float(abs(actual-wanted).max());errors[bus+'_'+condition]=error;assert error<3.1e-8
                if amount is None:assert np.array_equal(actual,wanted)
                if bus=='mix':
                    portions=[];freq=np.array(profile['modal']['frequencies_hz'])
                    for first in range(0,frames,144000):
                        audio=actual[first:first+144000];ph=phases(audio[:,0],freq[selected])
                        observation=observe(audio,freq,ph);stats,_=statistics(observation['coefficients']);portions.append(stats)
                    r['observations'].append(dict(seed=seed,condition=condition,portions=portions,
                        median_observed_std=np.median([p['raw_log_std'] for p in portions],axis=0).tolist(),
                        median_trace_200ms_correlation=float(np.median([p['trace_200ms_correlation'] for p in portions]))))
        r['renders'].append(dict(seed=seed,all_native_waveform_error_FS=errors,old_baseline_exact=True))
        save(a.out/'report.json',r);print(dict(seed=seed,errors=errors,observed=[(v['condition'],v['median_observed_std']) for v in r['observations'] if v['seed']==seed]),flush=True)
    r.update(result='passed',all9source_bands_and_native_waveforms=True,all72generated_blocks_observed=True,
         AM_native_evidence_reused_with_identical_model_and_nodes=True,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
