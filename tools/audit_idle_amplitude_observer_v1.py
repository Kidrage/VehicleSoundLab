"""Independent weighted QR audit of every saved phase-aware magnitude window."""
import argparse, shutil, sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import linalg,signal
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),cases=[])
selected=[1,2,4];rate=48000;frames=9600
try:
    report=load(a.input/'report.json');assert report['result']=='phase_aware_idle_amplitude_observed'
    for path,digest in report['inputs'].items():assert sha(path)==digest
    with np.load(a.input/'known.npz') as f:known={k:f[k] for k in f.files}
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    origin=a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
    cases=[]
    for label in ['constant','nonlinearFM','AM','combined','neighbor']:
        cases.append((label,known[label+'_audio'],known[label+'_phasors'],known['frequencies'],
                      {'aware':known[label+'_coefficients']},None))
    for row in report['observations']:
        with np.load(origin/(row['part']+'.npz')) as f:audio=f['audio'];z=f['phasors']
        if row['seed'] is not None:
            fourier=np.fft.rfft(audio,axis=0);phase=np.random.default_rng(row['seed']).uniform(-np.pi,np.pi,len(fourier))
            phase[0]=phase[-1]=0;audio=np.fft.irfft(fourier*np.exp(1j*phase[:,None]),n=len(audio),axis=0)
            with np.load(origin/f"{row['part']}_phase_{row['seed']}.npz") as f:z=f['phasors']
        assert sha(a.input/row['file'])==row['sha256']
        with np.load(a.input/row['file']) as f:expected={key:f[key] for key in ['fixed','aware']}
        cases.append((row['label'],audio,z,np.array(profile['modal']['frequencies_hz']),expected,row))
    for label,audio,z,freq,expected,summary in cases:
        # Independently rebuild the actual bandpass/Hilbert path, not saved truth phases.
        extracted=[]
        for hz in freq[selected]:
            poles=signal.butter(4,[hz-10,hz+10],btype='bandpass',fs=rate,output='zpk')
            sos=signal.zpk2sos(*poles)
            y=signal.sosfiltfilt(sos,audio[:,0]);spectrum=np.fft.fft(y)
            mask=np.zeros(len(y));mask[0]=mask[len(y)//2]=1;mask[1:len(y)//2]=2
            analytic=np.fft.ifft(spectrum*mask);extracted.append(analytic/abs(analytic))
        rebuilt=np.array(extracted).T;phase_error=float(abs(rebuilt-z).max());assert phase_error<2e-9
        t=np.arange(len(audio))/rate;angle=2*np.pi*t[:,None]*freq
        base=np.column_stack([np.cos(angle),np.sin(angle),np.ones(len(t))])
        w=np.sqrt(signal.windows.hann(frames,sym=False));starts=np.arange(12000,len(t)-12000-frames+1,960)
        errors={};curves_error=0.
        for mode,wanted in expected.items():
            design=base.copy()
            if mode=='aware':design[:,selected]=z.real;design[:,np.array(selected)+len(freq)]=z.imag
            coefficients=[]
            for first in starts:
                solution,_,rank,_=linalg.lstsq(design[first:first+frames]*w[:,None],audio[first:first+frames,0]*w,
                                              lapack_driver='gelsy')
                assert rank==27
                coefficients.append(solution[:13]-1j*solution[13:26])
            coefficients=np.array(coefficients);errors[mode]=float(abs(coefficients-wanted).max())
            assert errors[mode]<2e-12,(label,mode,errors[mode])
            if summary is not None:
                x=np.log(abs(coefficients[:,selected]));x-=x.mean(axis=0)
                curves=np.array([sum((np.outer(x[i],x[i+k]) for i in range(len(x)-k)),np.zeros((3,3)))/(len(x)-k)
                                 for k in range(51)])
                curves_error=max(curves_error,float(abs(curves-np.array(summary[mode]['covariance_lags'])).max()))
                rho=float(np.sum(x[:-10]*x[10:])/np.sum(x[:-10]**2))
                assert abs(rho-summary[mode]['trace_200ms_correlation'])<1e-11
                assert curves_error<2e-12
        r['cases'].append(dict(label=label,windows=len(starts),phase_rebuild_error=phase_error,
                               coefficient_error=errors,complete_lag_curve_error=curves_error))
        print(r['cases'][-1],flush=True)
    r.update(result='passed',known_cases=5,source_and_controls=8,every_window_QR=True,all51lags=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
