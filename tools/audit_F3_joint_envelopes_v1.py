"""Independent Welch/CSD, explicit DFT and scalar time-statistic audit."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args();repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy import signal
    a.out.mkdir(parents=True, exist_ok=False);shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[], windows=0, DFT_complex_values=0,
             max_matrix_error_FS2=0, max_DFT_error=0, max_statistic_error=0)
    try:
        m = load(a.study/'report.json')
        assert m['result'] == 'native_joint_full_band_envelopes_observed'
        for name, h in m['sources'].items():assert sha(a.study/'exact_sources'/name) == sha(repo/name) == h
        for name, h in m['inputs'].items():assert sha(name) == h
        plan = load(a.study/'exact_sources/research/F3_joint_envelopes_v1_plan.json')
        spec, gates = plan['measurement'], plan['gates'];rate = spec['rate']
        n, hop, size = [spec[k] for k in ['window_samples','hop_samples','fft_samples']]
        hz = np.arange(size//2+1)*rate/size
        bands = [np.flatnonzero((hz >= low)&(hz < high)) for low, high in spec['bands_hz']]
        bins = np.array([int(b[j]) for b in bands for j in [0,len(b)//2,-1]])
        angles = 2*np.pi*bins[:,None]*np.arange(n)/size
        trig = np.cos(angles)-1j*np.sin(angles)
        window = signal.windows.hann(n,sym=False)
        kw = dict(fs=rate,window='hann',nperseg=n,noverlap=0,nfft=size,detrend=False,scaling='density',axis=1)
        for row in m['known']+m['real']:
            label=row['label'];path=a.study/label/'arrays.npz';assert sha(path)==row['arrays_sha256']
            d=np.load(path);audio=d['audio'];starts=np.arange(0,len(audio)-n+1,hop)
            assert np.array_equal(starts,d['window_starts'])
            if label.startswith('F3_'):
                receipt=load(a.study/label/'source_receipt.json');catalog=load(a.workspace/'references/segments_v1.json')
                source=catalog['sources']['F3'];segment=catalog['segments'][label]
                first,last=[round(t*rate) for t in segment['seconds']]
                with sf.SoundFile(a.workspace/source['master']) as stream:
                    stream.seek(first);original=stream.read(last-first,always_2d=True,dtype='float64')
                assert np.array_equal(audio,original) and receipt['seconds']==segment['seconds']
                assert receipt['master_sha256']==source['master_sha256']
            else:
                name=label.removeprefix('known_');t=np.arange(len(audio))/rate
                truth=np.zeros_like(audio);env=np.ones((len(t),4,2))
                # The producer groups f*t before multiplication by 2*pi;
                # this oracle multiplies 2*pi*f first. Bound the forward
                # roundoff of both evaluations rather than require an
                # arbitrary FS tolerance after tens of thousands of cycles.
                gamma=12*np.finfo(float).eps/(1-12*np.finfo(float).eps)
                wave_roundoff_bound=np.zeros_like(audio)
                for b,freq in enumerate([4100,7000,9000,12000]):
                    for c in range(2):
                        if name=='zero':e=np.zeros(len(t))
                        elif name=='shared_AM4Hz':e=1+.4*np.cos(8*np.pi*t)
                        elif name=='differential_AM':
                            e=(1+.1*t)*(1+.3*np.cos(2*np.pi*(2+b)*t+.2*b)) if c==0 else (1+.04*t)*(1+.25*np.sin(2*np.pi*(3+b)*t+.4*b))
                        else:e=np.ones(len(t))
                        env[:,b,c]=e
                        phase=2*np.pi*freq*t+(100*np.pi*t*t if name=='rising_carriers' else 0)
                        truth[:,c]+=[.055,.045,.035,.025][b]*(1 if c==0 else .7)*e*np.cos(phase+(0 if c==0 else [.2,-.4,.65,-.8][b]))
                        amplitude=[.055,.045,.035,.025][b]*(1 if c==0 else .7)*abs(e)
                        wave_roundoff_bound[:,c]+=amplitude*gamma*(2*(abs(phase)+1)+4)
                assert np.all(abs(audio-truth)<=wave_roundoff_bound+1e-15)
                assert np.array_equal(env,d['known_envelopes'])
                expected=np.zeros_like(d['P'][:,4:])
                for w,s in enumerate(starts):
                    for b,amp in enumerate([.055,.045,.035,.025]):
                        l,rch=env[s:s+n,b].T
                        avg=lambda x:float(np.dot(window*window,x)/np.dot(window,window))
                        expected[w,b,0,0]=amp*amp/2*avg(l*l)
                        expected[w,b,1,1]=amp*amp*.49/2*avg(rch*rch)
                        theta=[.2,-.4,.65,-.8][b]
                        expected[w,b,0,1]=amp*amp*.7/2*avg(l*rch)*complex(math.cos(theta),-math.sin(theta))
                        expected[w,b,1,0]=expected[w,b,0,1].conjugate()
                assert abs(expected-d['P'][:,4:]).max() <= gates['analytic_HF_matrix_absolute_FS2']
            frames=audio[starts[:,None]+np.arange(n)]
            _,density=signal.welch(frames,**kw)
            _,cross=signal.csd(frames[:,:,1],frames[:,:,0],**kw)
            independent=np.empty_like(d['P'])
            for b,indices in enumerate(bands):
                independent[:,b,0,0],independent[:,b,1,1]=(density[:,indices].sum(axis=1)*rate/size).T
                independent[:,b,0,1]=cross[:,indices].sum(axis=1)*rate/size
                independent[:,b,1,0]=independent[:,b,0,1].conjugate()
            error=abs(independent-d['P'])
            assert np.all(error <= gates['matrix_absolute_FS2']+gates['matrix_relative']*abs(independent))
            r['max_matrix_error_FS2']=max(r['max_matrix_error_FS2'],float(error.max()))
            ft=np.fft.rfft(frames*window[None,:,None],n=size,axis=1)[:,bins]
            direct=np.stack([(frames[:,:,c]*window)@trig.T for c in range(2)],axis=-1)
            error=float(abs(ft-direct).max());assert error<=gates['DFT_amplitude_absolute']
            r['max_DFT_error']=max(r['max_DFT_error'],error);r['DFT_complex_values']+=direct.size
            # Independently verify log/trend/covariance on literal saved input
            # matrices, isolating feature arithmetic from FFT roundoff/floors.
            power=d['P'].diagonal(axis1=-2,axis2=-1).real
            floor=plan['features']['log_floor_FS2'];assert np.array_equal(power<=floor,d['floored'])
            v=np.array([[10*math.log10(max(float(p),floor)) for p in w.flat] for w in power])
            assert abs(v-d['log_power_dB']).max()<=gates['feature_absolute_dB']
            times=np.array([(int(s)+n/2)/rate for s in starts]);center=math.fsum(times)/len(times)
            dt=times-center
            mean=np.array([math.fsum(col)/len(col) for col in v.T])
            slope=np.array([math.fsum(float(t*x) for t,x in zip(dt,col))/math.fsum(float(t*t) for t in dt) for col in v.T])
            assert abs(np.stack([mean,slope])-d['trend_coefficients']).max()<=gates['statistic_absolute']
            trend=mean+dt[:,None]*slope
            residual=v-trend
            for name,values in [('centered',v-mean),('affine_residual',residual)]:
                covariance=np.array([[math.fsum(float(x*y) for x,y in zip(left,right))/len(values) for right in values.T] for left in values.T])
                error=float(abs(covariance-d[name+'_covariance']).max())
                assert error<=gates['statistic_absolute'];r['max_statistic_error']=max(r['max_statistic_error'],error)
                for i,lag in enumerate(plan['features']['lags_windows']):
                    lagged=np.array([[math.fsum(float(x*y) for x,y in zip(left,right))/(len(values)-lag) for right in values[lag:].T] for left in values[:-lag].T])
                    error=float(abs(lagged-d[name+'_lag_products'][i]).max())
                    assert error<=gates['statistic_absolute'];r['max_statistic_error']=max(r['max_statistic_error'],error)
                literal=d[name+'_covariance'];eigen=d[name+'_eigenvalues']
                assert abs(eigen.sum()-np.trace(literal))<gates['statistic_absolute']
                assert eigen.min()>=-gates['statistic_absolute'] and abs(eigen@eigen-np.sum(literal*literal))<gates['statistic_absolute']
            assert abs(residual-d['affine_residual_dB']).max()<=gates['feature_absolute_dB']
            assert abs(trend-d['fitted_trend_dB']).max()<=gates['feature_absolute_dB']
            assert abs(v[:,0::2]-v[:,1::2]-d['ILD_dB']).max()<=gates['feature_absolute_dB']
            rho=d['P'][:,:,0,1]/np.sqrt(np.maximum(power[:,:,0],floor)*np.maximum(power[:,:,1],floor))
            assert abs(rho-d['complex_coherence']).max()<=1e-12
            r['cases'].append(dict(label=label,original_samples_exact=True,all_band_matrices=True,all_scalar_statistics=True))
            r['windows']+=len(starts);save(a.out/'report.json',r);print('PASS independent joint envelopes',label,flush=True)
        for name,h in m['protected_before'].items():assert sha(repo/name)==h
        r.update(result='independent_joint_envelope_audit_passed',producer_report_sha256=sha(a.study/'report.json'),
                 auditor_sha256=sha(__file__),runtime_C_voices_F2_exact=True,stochastic_law_qualified=False)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(a.out/'report.json',r)


if __name__=='__main__':main()
