"""Independent source QR/DFT/response/FFT audio and same-observer transfer audit."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','parent','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import fft,linalg,ndimage,signal
from research_archive_v1 import load,save,sha
from idle_phase_amplitude_v1.observe import observe,statistics
from idle_conditioned_detail_v1.features import phases

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),renders=[],comparisons=[])
try:
    report=load(a.input/'report.json');assert report['result']=='finite_separated_low_residual_pending_audit'
    for path,digest in report['inputs'].items():assert sha(path)==digest
    old=load(a.parent/'report.json');assert sha(a.input/'extraction.npz')==report['extraction_sha256']
    origin=a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    freq=np.array(profile['modal']['frequencies_hz'])
    with np.load(origin/'train.npz') as f:audio=f['audio'];z=f['phasors']
    with np.load(a.input/'extraction.npz') as f:given={k:f[k] for k in f.files}
    t=np.arange(len(audio))/48000;angle=2*np.pi*t[:,None]*freq
    A=np.column_stack((np.cos(angle),np.sin(angle),np.ones(len(t))))
    A[:,[1,2,4]]=z.real;A[:,[14,15,17]]=z.imag
    lo,hi=12000,len(audio)-12000;w=np.sqrt((1-np.cos(2*np.pi*np.arange(hi-lo)/(hi-lo)))/2)
    beta,_,rank,_=linalg.lstsq(A[lo:hi]*w[:,None],audio[lo:hi]*w[:,None],lapack_driver='gelsy');assert rank==27
    residual=audio[lo:hi]-A[lo:hi]@beta
    r['source_QR_coefficient_error']=float(abs(beta-given['coefficients']).max())
    r['full_source_residual_error_FS']=float(abs(residual-given['residual']).max())
    assert max(r['source_QR_coefficient_error'],r['full_source_residual_error_FS'])<1e-12
    # Direct nine-window two-sided Welch density, separate reflected Gaussian convolution.
    hann=(1-np.cos(2*np.pi*np.arange(24000)/24000))/2
    density=sum((abs(np.fft.rfft(residual[j:j+24000,0]*hann))**2 for j in range(0,len(residual)-23999,12000)))/(9*48000*sum(hann*hann))
    f=np.fft.rfftfreq(65536,1/48000);hz=np.fft.rfftfreq(24000,1/48000)
    sigma=8/(48000/65536);radius=int(4*sigma+.5);gaussian=np.exp(-.5*(np.arange(-radius,radius+1)/sigma)**2);gaussian/=sum(gaussian)
    density=ndimage.convolve1d(np.interp(f,hz,density),gaussian,mode='reflect')
    hs=[]
    for j,kernel in enumerate(profile['kernels'][:2]):
        low,high=kernel['band_hz'];pad=(high-low)/10
        mask=np.zeros(len(f));inside=(f>=low)&(f<=high);mask[inside]=1
        left=(f>low-pad)&(f<low);right=(f>high)&(f<high+pad)
        mask[left]=np.sin(np.pi*(f[left]-low+pad)/(2*pad))**2
        mask[right]=np.cos(np.pi*(f[right]-high)/(2*pad))**2
        one=density*mask;power=np.concatenate((one,one[-2:0:-1]))
        cepstrum=np.fft.ifft(np.log(np.maximum(power,1e-30))/2).real
        lift=cepstrum.copy();lift[1:32768]*=2;lift[32769:]=0
        h=np.fft.ifft(np.exp(np.fft.fft(lift))).real[:8192];h/=np.linalg.norm(h);hs.append(h)
    hs=np.array(hs);r['all_filter_taps_error']=float(abs(hs-given['taps']).max());assert r['all_filter_taps_error']<2e-12
    r['filter_response_error']=float(abs(np.fft.rfft(hs,65536,axis=1)-np.fft.rfft(given['taps'],65536,axis=1)).max())
    assert r['filter_response_error']<1e-10
    frames=24*48000;warm=profile['warmup_frames'];count=frames+warm;mask=(1<<64)-1
    for row,parent in zip(report['renders'],old['renders']):
        seed=row['seed'];assert seed==parent['seed'];delta=np.zeros((frames,2))
        for j,kernel in enumerate(profile['kernels'][:2]):
            key=seed^((0x9E3779B97F4A7C15*(j+1))&mask)
            noise=np.random.Generator(np.random.PCG64(key^0x794323AA)).standard_normal(count)
            taps=hs[j]-np.array(kernel['taps']);size=fft.next_fast_len(count+len(taps)-1)
            y=fft.irfft(fft.rfft(noise,size)*fft.rfft(taps,size),size)[warm:count]*kernel['gain']
            delta+=y[:,None]*[1.,kernel['right_over_left']]
        base,_=sf.read(a.parent/parent['files']['mix_0.0']['file'],always_2d=True)
        main,_=sf.read(a.parent/parent['files']['main_0.0']['file'],always_2d=True)
        main50,_=sf.read(a.parent/parent['files']['main_0.5']['file'],always_2d=True)
        errors={};conditions=[('0.0',base,main),('0.5',base+delta,main),('1.0',base+delta+main50-main,main50)]
        for condition,mix,source in conditions:
            for bus,wanted in [('mix',mix),('main',source)]:
                entry=row['files'][bus+'_'+condition];path=a.input/entry['file'];assert sha(path)==entry['sha256']
                actual,rate=sf.read(path,always_2d=True);assert rate==48000 and len(actual)==frames
                error=float(abs(actual-wanted).max());errors[bus+'_'+condition]=error;assert error<3.1e-8
                if condition=='0.0':assert np.array_equal(actual,wanted)
                if bus=='mix':
                    portions=[]
                    for first in range(0,frames,144000):
                        audio=actual[first:first+144000];z=phases(audio[:,0],freq[[1,2,4]])
                        observation=observe(audio,freq,z);summary,_=statistics(observation['coefficients']);portions.append(summary)
                    r['comparisons'].append(dict(seed=seed,condition=condition,portions=portions,
                        median_observed_std=np.median([p['raw_log_std'] for p in portions],axis=0).tolist(),
                        median_trace_200ms_correlation=float(np.median([p['trace_200ms_correlation'] for p in portions]))))
        r['renders'].append(dict(seed=seed,all_native_waveform_errors_FS=errors,old_baseline_exact=True))
        save(a.out/'report.json',r)
        print(dict(seed=seed,errors=errors,observed=[(v['condition'],v['median_observed_std']) for v in r['comparisons'] if v['seed']==seed]),flush=True)
    r.update(result='passed',same_observer_blocks=72,source_CHECK_not_fitted=True,
             physical_source_separation=False,old_expected_residual_power_preserved=True,
             high_detail_and_phase_and_other_modes_unchanged=True,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
