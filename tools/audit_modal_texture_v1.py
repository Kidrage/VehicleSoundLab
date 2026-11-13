"""Independent QR extraction, scalar AR/gain math and complex-OSC/FIR replay."""
import argparse,json,math,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--known',type=Path,required=True);p.add_argument('--input',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import linalg,signal
from research_archive_v1 import load,save,sha


def normals(seed,count):
    mask=(1<<64)-1;state=seed or 1;out=[]
    def uniform():
        nonlocal state
        state=(state^(state>>12));state^=(state<<25)&mask;state^=state>>27;state&=mask
        return (((state*2685821657736338717)&mask)>>11)+.5
    while len(out)<count:
        radius=math.sqrt(-2*math.log(uniform()/2**53));angle=2*math.pi*uniform()/2**53
        out.extend((radius*math.cos(angle),radius*math.sin(angle)))
    return np.asarray(out[:count])


def check_one_line_links(windows,saved,plan):
    dt=plan['hop']/plan['sample_rate'];identity=0
    assert len(saved['frames'])==len(windows)
    for i,window in enumerate(windows):
        assert len(window['lines'])==1 and window['lines'][0]['eligible']
        current=window['lines'][0]
        if i:
            old=windows[i-1]['lines'][0]
            forward=current['frequency_hz']-old['frequency_hz']-dt*old['chirp_hz_per_second']
            backward=old['frequency_hz']-current['frequency_hz']+dt*current['chirp_hz_per_second']
            dq=current['chirp_hz_per_second']-old['chirp_hz_per_second']
            accepted=abs(forward)<=plan['link_prediction_error_hz'] and abs(backward)<=plan['link_prediction_error_hz'] and abs(dq)<=plan['link_chirp_difference_hz_per_second']
            assert bool(saved['transitions'][i-1]['edges'])==accepted
            if not accepted:identity+=1
        assert saved['frames'][i][0]['track_id']==identity
    return identity+1


def known_diagnosis():
    old=load(a.known/'exact_sources/research/low_chirp_v1_plan.json');plan=load(a.known/'exact_sources/research/modal_texture_v1_plan.json')
    fulltime=np.arange(144000)/48000;phase=2*np.pi*75.31*fulltime+.4;maximum=0.;count=0
    for name in ['constant','AM','FM']:
        folder=a.known/name;audio=np.load(folder/'audio.npz')['audio'];windows=load(folder/'windows.json')
        expected=.2*np.cos(phase)
        if name=='AM':expected*=1+.2*np.sin(2*np.pi*.8*fulltime)
        if name=='FM':expected=.2*np.cos(phase-(1.2/1.6)*np.cos(2*np.pi*1.6*fulltime))
        assert abs(audio[:,0]-expected).max()<1e-13 and np.array_equal(audio[:,1],.67*audio[:,0])
        exact=[]
        for i,window in enumerate(windows):
            state=dict(np.load(folder/f'window{i}.npz'));params=state['parameters'];m=len(window['lines'])
            nominal=np.asarray(window['inventory']['native_frequency_hz']);n=old['frames'];t=np.arange(n)/48000-.25
            coefficients=np.column_stack((params[2*m:],state['right_coefficients']));wave=np.tile(coefficients[-1],(n,1))
            stems=[]
            for k in range(m):
                oscillator=np.exp(2j*np.pi*((nominal[k]+params[k])*t+.5*params[m+k]*t*t))
                component=np.real(oscillator[:,None]*(coefficients[k]-1j*coefficients[m+k]));wave+=component;stems.append(component)
            tile=audio[window['start_frame']:window['start_frame']+n];residual=tile-wave
            maximum=max(maximum,float(abs(wave-state['reconstructed']).max()),float(abs(residual-state['residual']).max()))
            hann=.5-.5*np.cos(2*np.pi*np.arange(n)/n);cost=float(np.sum(hann*(wave[:,0]-tile[:,0])**2)/(2*n))
            assert abs(cost-window['cost'])<=1e-12
            assert np.all(params>=state['lower']) and np.all(params<=state['upper'])
            zr=np.fft.rfft(residual*hann[:,None],axis=0);hz=np.fft.rfftfreq(n,1/48000)
            for k,row in enumerate(window['lines']):
                extent=abs(row['chirp_hz_per_second'])*.25+old['support_padding_hz'];mask=abs(hz-row['frequency_hz'])<=extent
                zl=np.fft.rfft(stems[k]*hann[:,None],axis=0)
                explained=1-np.sum(abs(zr[mask])**2,axis=0)/np.sum(abs((zr+zl)[mask])**2,axis=0)
                assert abs(explained-row['local_explained_fraction_LR']).max()<=1e-10
                assert row['eligible']==bool(window['success'] and not row['bound_contact'] and min(explained)>=old['minimum_local_explained_fraction'])
            center=(window['start_frame']+n/2)/48000
            ff=75.31+(1.2*np.sin(2*np.pi*1.6*center) if name=='FM' else 0)
            qq=1.2*2*np.pi*1.6*np.cos(2*np.pi*1.6*center) if name=='FM' else 0
            exact.append(dict(lines=[dict(frequency_hz=float(ff),chirp_hz_per_second=float(qq),eligible=True)]));count+=1
        check_one_line_links(windows,load(folder/'fitted_links.json'),old)
        check_one_line_links(exact,load(folder/'truth_links.json'),old)
    assert maximum<=2e-11
    return dict(windows=count,maximum_wave_error=maximum,truth_link_operator_rebuilt=True)


a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',optimizer_rerun=False,holdout_read=False)
try:
    (a.out/'executed_audit.py').write_bytes(Path(__file__).read_bytes())
    report=load(a.input/'report.json');profile=load(a.input/'profile.json');plan=report['plan']
    assert report['result']=='amplitude_only_fixed_idle_candidates_pending_listening'
    r['known_diagnosis']=known_diagnosis()
    parent=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1/F2_tailpipe'
    base=load(parent/'profile.json');assert profile['modal']==base['modal']
    assert not profile['recorded_trajectory'] and not profile['envelope']['recorded_trajectory'] and not profile['room']
    assert set(profile['envelope'])=={'schema','covariance','factor','alpha','hop_frames','recorded_trajectory','scope'}
    modal=profile['modal'];frequencies=np.asarray(modal['frequencies_hz']);m=len(frequencies)
    audio,rate=sf.read(parent/'training.wav',always_2d=True);assert sha(parent/'training.wav')==report['training_sha256']
    observed=np.load(a.input/'source_observations.npz');n=plan['observation_frames'];t=(np.arange(n)-n/2)/rate
    w=np.sqrt(.5-.5*np.cos(2*np.pi*np.arange(n)/n))
    design=np.column_stack((np.cos(2*np.pi*t[:,None]*frequencies),np.sin(2*np.pi*t[:,None]*frequencies),np.ones(n)))
    Q,R=np.linalg.qr(w[:,None]*design,mode='reduced');coefficients=[]
    for start in observed['starts']:
        beta=linalg.solve_triangular(R,Q.T@(w*audio[start:start+n,0]))
        coefficients.append(beta[:m]-1j*beta[m:2*m])
    coefficients=np.asarray(coefficients);coefficient_error=float(abs(coefficients-observed['coefficients']).max());assert coefficient_error<=1e-11
    assert len(coefficients)==141
    magnitude=abs(coefficients);floor=np.maximum(magnitude.mean(axis=0)*plan['magnitude_floor_fraction'],1e-30)
    log=np.log(np.maximum(magnitude,floor));log-=log.mean(axis=0)
    std=np.sqrt(np.mean(log*log,axis=0));scale=np.minimum(1.,plan['maximum_log_amplitude_std']/np.maximum(std,1e-30));limited=log*scale
    covariance=sum(np.outer(row,row) for row in limited)/len(limited)
    model=profile['envelope'];C=np.asarray(model['covariance']);L=np.asarray(model['factor'])
    covariance_error=float(abs(covariance-C).max());factor_error=float(abs(L@L.T-C).max())
    assert max(covariance_error,factor_error)<=1e-12
    lag=plan['correlation_lag'];den=math.fsum(float(v*v) for v in limited[:-lag].flat)
    numerator=math.fsum(float(x*y) for x,y in zip(limited[:-lag].flat,limited[lag:].flat))
    raw=numerator/den if den>1e-24 else 0.;alpha=max(0.,min(plan['correlation_ceiling'],raw))
    assert abs(alpha-model['alpha'])<=1e-12
    frames=plan['seconds']*rate;tt=np.arange(frames)/rate;hop=model['hop_frames'];index=np.arange(frames)//hop
    u=(1-np.cos(np.pi*(np.arange(frames)%hop)/hop))/2
    normalized_variance=(1-u)**2+u*u+2*alpha*u*(1-u)
    rows=[];max_sample_error=0.;max_state_error=0.
    for seed in plan['seeds']:
        saved=np.load(a.input/f'states_{seed}.npz');state=saved['state'];normal=saved['normal']
        independent=normals(seed^0x8CB92BA72F3D8DD7,normal.size).reshape(normal.shape)
        assert np.array_equal(independent,normal)
        expected=np.empty_like(state)
        for j,z in enumerate(normal):
            innovation=np.asarray([math.fsum(float(a*b) for a,b in zip(row,z)) for row in L])
            expected[j]=innovation if j==0 else alpha*expected[j-1]+math.sqrt(1-alpha*alpha)*innovation
        max_state_error=max(max_state_error,float(abs(expected-state).max()));assert max_state_error<=2e-13
        value=((1-u[:,None])*expected[index]+u[:,None]*expected[index+1])/np.sqrt(normalized_variance[:,None])
        detail=np.zeros((frames,2))
        count=frames+base['warmup_frames']
        for k,kernel in enumerate(base['kernels']):
            noise=normals(seed^(0x9E3779B97F4A7C15*(k+1)&((1<<64)-1)),count)
            filtered=signal.fftconvolve(noise,np.asarray(kernel['taps']))[base['warmup_frames']:count]*kernel['gain']
            detail+=filtered[:,None]*np.asarray([1.,kernel['right_over_left']])
        for amount in plan['amounts']:
            gain=np.exp(amount*value-amount*amount*np.diag(C))
            core=np.zeros((frames,2))
            for k,ff in enumerate(frequencies):
                oscillator=np.exp(2j*np.pi*np.remainder(tt*ff,1.))
                amplitude=np.asarray(modal['amplitude_LR'][k])*np.exp(1j*np.asarray(modal['initial_phase_LR'][k]))
                core+=gain[:,k,None]*np.real(oscillator[:,None]*amplitude)
            label=f'{round(amount*100):03d}';actual,_=sf.read(a.input/f'core_{label}_{seed}.wav',always_2d=True)
            core_error=float(abs(core-actual).max());mix,_=sf.read(a.input/f'mix_{label}_{seed}.wav',always_2d=True)
            mix_error=float(abs(core+detail-mix).max());max_sample_error=max(max_sample_error,core_error,mix_error)
            assert max(core_error,mix_error)<=3e-8,(seed,amount,core_error,mix_error)
            if amount==0:
                frozen,_=sf.read(a.workspace/f'baselines/idle_texture_v2/evidence/trial1/fine_{seed}.wav',always_2d=True)
                assert np.array_equal(mix,frozen)
            rows.append(dict(seed=seed,amount=amount,core_error=core_error,mix_error=mix_error))
        print(json.dumps(dict(stage='replayed',seed=seed)),flush=True)
    r.update(result='amplitude_proxy_and_all9_core_mix_renders_independently_rebuilt',rows=rows,
        source_coefficient_error=coefficient_error,covariance_error=covariance_error,factor_error=factor_error,
        maximum_state_error=max_state_error,maximum_FLOAT_sample_error=max_sample_error,
        modal_parameters_exact=True,zero_FLOAT_baseline_exact=True,recorded_trajectory=False,
        parent_sha256=sha(a.input/'report.json'),scope='Numerical/source-statistics audit; no timbre acceptance or physical AM inference')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps({key:value for key,value in r.items() if key!='rows'}),flush=True)
