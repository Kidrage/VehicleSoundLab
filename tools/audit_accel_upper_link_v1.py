"""Independent FFT causal filter/Hilbert and Welch/CSD of every native observation."""
import argparse, math, os, shutil, sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import signal
from scipy.special import roots_hermitenorm
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},observations=0,windows=0,
       cross_spectra=0,band_summaries=0,full_MSC_tolerance_failures=[])


def check(key,x,y,gate=1e-10,relative=False):
    x=np.asarray(x);y=np.asarray(y);d=float(np.max(abs(x-y)))
    if relative:
        scale=float(max(abs(x).max(),abs(y).max()))
        if scale:d/=scale
    r['errors'][key]=max(d,r['errors'].get(key,0.));assert d<=gate,(key,d,gate)


def fft_features(audio,sos):
    n=1<<int(math.ceil(math.log2(len(audio)+131072)))
    z=np.exp(-2j*np.pi*np.arange(n//2+1)/n);F=np.fft.rfft(audio,n=n,axis=0);columns=[]
    for sections in sos:
        H=np.ones(len(z),complex)
        for b0,b1,b2,a0,a1,a2 in sections:
            H*=(b0+b1*z+b2*z*z)/(a0+a1*z+a2*z*z)
        for ch in range(2):columns.append(np.fft.irfft(F[:,ch]*H,n=n)[:len(audio)])
    real=np.column_stack(columns);h=np.zeros(len(audio));h[0]=1
    if len(h)%2==0:h[len(h)//2]=1;h[1:len(h)//2]=2
    else:h[1:(len(h)+1)//2]=2
    analytic=np.fft.ifft(np.fft.fft(real,axis=0)*h[:,None],axis=0)
    return audio[4800:-4800],(analytic.real**2+analytic.imag**2)[4800:-4800]


def spectra(reference,power):
    kw=dict(fs=48000,window='hann',nperseg=4800,noverlap=2400,nfft=4800,
            detrend='constant',return_onesided=True,scaling='density',axis=0,average='mean')
    hz,xx=signal.welch(reference,**kw);_,yy=signal.welch(power,**kw)
    xy=np.empty((2401,2,4),complex)
    for i in range(2):
        for j in range(4):_,xy[:,i,j]=signal.csd(reference[:,i],power[:,j],**kw)
    valid=xx[:,:,None]*yy[:,None,:]>0;msc=np.zeros((2401,2,4))
    for i in range(2):
        for j in range(4):
            mask=valid[:,i,j];msc[mask,i,j]=abs(xy[mask,i,j])**2/(xx[mask,i]*yy[mask,j])
    return hz,xx,yy,xy,valid,msc


try:
    run=load(a.input/'report.json');assert run['result']=='all12_low_to_upper_power_associations_observed'
    for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    # Closed native examples and independent Welch operator BEFORE reading source arrays.
    t=np.arange(144000)/48000;ref=np.column_stack((np.cos(2*np.pi*300*t),np.sin(2*np.pi*300*t)))
    amp=(1+.4*np.cos(2*np.pi*300*t))**2;power=amp[:,None]*np.array([1,.3,.1,.7])[None,:]
    beat=1.04+.4*np.cos(2*np.pi*300*t)
    with np.load(a.input/'known.npz') as f:
        check('known_native_reference',ref,f['reference'],1e-12)
        check('known_native_AM_power',power,f['power'],1e-12)
        check('known_two_tone_power',beat,f['beating_power'],1e-10)
    hz,xx,yy,xy,valid,msc=spectra(ref,power);check('known_AM_MSC',msc[30],1,1e-12)
    scaled=spectra(ref*.173,power*.013);check('known_gain_invariance',scaled[-1][30],msc[30],1e-12)
    permutation=[2,0,3,1];swapped=spectra(ref[:,::-1],power[:,permutation])
    check('known_permutation',swapped[-1][30],msc[30][::-1][:,permutation],1e-12)
    constant=spectra(ref,np.ones_like(power));assert not constant[-2].any() and not constant[-1].any()
    beating=spectra(ref,np.tile(beat[:,None],(1,4)));check('known_beating_MSC',beating[-1][30],1,1e-12)
    q,w=roots_hermitenorm(9);x,y=np.meshgrid(q,q,indexing='ij');W=np.outer(w,w)/(2*np.pi)
    third=math.fsum((W*x*((.6*x+.8*y)**2-1)).ravel());check('known_Gaussian_third',third,0,1e-12)
    for key in ['AM_supported_bin_MSC_error','gain_invariance_error','beating_supported_bin_MSC_error']:
        assert run['known'][key]<1e-12
    assert abs(run['known']['Gaussian_third_moment'])<1e-12
    assert run['known']['channel_permutation'] and run['known']['constant_power_undefined']
    assert run['known']['source_or_excitation_detector'] is False
    parent=a.workspace/'baselines/accel_upper_joint_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    assert load(parent/'evidence/audit1/report.json')['result']=='passed'
    for row in run['observations']:
        path=a.input/row['file'];assert sha(path)==row['sha256']
        with np.load(parent/row['parent_file']) as old:
            reference,power=fft_features(old['audio'],old['sos'])
        with np.load(path) as f:
            check('native_reference',reference,f['reference'],0)
            check('native_FFT_Hilbert_power',power,f['power'],1e-11)
            # Saved samples follow the independent native-array check; spectra are a separate operator audit.
            reference=f['reference'];power=f['power'];hz,xx,yy,xy,valid,msc=spectra(reference,power)
            check('native_Hz',hz,f['hz'],0)
            starts=np.arange((len(power)-4800)//2400+1)*2400
            check('all_starts',starts,f['starts'],0)
            assert len(reference)==row['frames'] and len(starts)==row['windows']
            for j in range(2):check('reference_PSD',xx[:,j],f['Pxx'][:,j],1e-10,True)
            for j in range(4):check('power_PSD',yy[:,j],f['Pyy'][:,j],1e-10,True)
            for i in range(2):
                for j in range(4):check('signed_complex_CSD',xy[:,i,j],f['Cxy'][:,i,j],1e-10,True)
            assert np.array_equal(valid,f['valid'])
            # Retain the original all-bin gate and collect every failing case instead of stopping at case 1.
            # No bin is excluded from this failed qualification; native and fixed-band checks remain separate.
            delta=abs(msc-f['MSC']);peak=np.unravel_index(int(delta.argmax()),delta.shape)
            err=float(delta[peak]);r['errors']['every_bin_MSC']=max(err,r['errors'].get('every_bin_MSC',0.))
            if err>2e-8:
                k,i,j=peak;r['full_MSC_tolerance_failures'].append(dict(segment=row['segment'],branch=row['branch'],
                    error=err,gate=2e-8,indices=[int(k),int(i),int(j)],hz=float(hz[k]),
                    original_MSC=float(f['MSC'][peak]),independent_MSC=float(msc[peak]),
                    Pxx=float(xx[k,i]),Pyy=float(yy[k,j]),relative_Pyy=float(yy[k,j]/yy[:,j].max())))
            check('fixed_30_to600Hz_MSC',msc[(hz>=30)&(hz<600)],f['MSC'][(hz>=30)&(hz<600)],2e-8)
            saved_denominator=f['Pxx'][:,:,None]*f['Pyy'][:,None,:]
            closure=np.zeros_like(saved_denominator);np.divide(abs(f['Cxy'])**2,saved_denominator,out=closure,where=f['valid'])
            check('all_bin_saved_MSC_algebra',closure,f['MSC'],1e-12)
            check('reported_max_MSC',msc.max(),row['maximum_MSC'],2e-8)
            assert msc.min()>=0 and msc.max()<=1+1e-12
            for b,(lo,hi) in enumerate([(30,120),(120,200),(200,400),(400,600)]):
                bins=[k for k,v in enumerate(hz) if lo<=v<hi];summary=row['summary'][b]
                assert summary['band_hz']==[lo,hi]
                low=np.array([math.fsum(xx[bins,i])*10 for i in range(2)])
                upper=np.array([math.fsum(yy[bins,j])*10 for j in range(4)])
                fraction=np.array([[math.fsum(float(msc[k,i,j])*float(yy[k,j]) for k in bins)*10/upper[j]
                                    if upper[j]>0 else 0 for j in range(4)] for i in range(2)])
                check('all_band_reference_power',low,summary['reference_power'],1e-10,True)
                check('all_band_upper_modulation_power',upper,summary['upper_power_modulation'],1e-10,True)
                check('all_band_weighted_MSC',fraction,summary['power_weighted_MSC'],1e-10)
                assert np.array_equal(upper>0,summary['modulation_present']);r['band_summaries']+=1
        r['observations']+=1;r['windows']+=len(starts);r['cross_spectra']+=8;save(a.out/'report.json',r)
        print(dict(observation=r['observations'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['observations']==12 and r['windows']==900 and r['band_summaries']==48
    r.update(result='native_and_summaries_passed_full_MSC_tolerance_not_passed' if r['full_MSC_tolerance_failures'] else 'passed',
             all_native2401bins=True,all2x4signed_complex_spectra=True,
             full_MSC_independent_tolerance_passed=not bool(r['full_MSC_tolerance_failures']),
             original_full_MSC_gate_unchanged=2e-8,fixed_30_to600Hz_summaries_passed=True,
             old_phase_stream_PSD_LRCSD_audit='hash_bound_reuse_not_rerun',source_detector=False,new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
