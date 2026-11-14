"""Independent QR, convolution reconstruction and periodogram/CSD budgets."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import linalg,signal
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),known=[],cases=[])
selected=np.array([1,2,4]);localQR=0


def rebuild(audio,z,freq,local=None,full=False):
    global localQR
    angle=2*np.pi*np.arange(len(audio))[:,None]*np.array(freq)/48000
    A=np.column_stack((np.cos(angle),np.sin(angle),np.ones(len(audio))))
    A[:,selected]=z.real;A[:,selected+13]=z.imag
    weight=np.sqrt(signal.windows.hann(len(audio)-24000,sym=False))
    beta,_,rank,_=linalg.lstsq(A[12000:-12000]*weight[:,None],audio[12000:-12000]*weight[:,None],lapack_driver='gelsy');assert rank==27
    starts=np.arange(12000,len(audio)-12000-9600+1,960)
    test=np.arange(len(starts)) if full else np.array([0,len(starts)//2,len(starts)-1])
    w=signal.windows.hann(9600,sym=False);sqrt=np.sqrt(w);local_error=0.;dc=[]
    if local is None:local=np.zeros((len(starts),13),complex)
    for j in test:
        first=starts[j]
        b,_,rank,_=linalg.lstsq(A[first:first+9600]*sqrt[:,None],audio[first:first+9600,0]*sqrt,lapack_driver='gelsy');assert rank==27
        expected=b[:13]-1j*b[13:26];localQR+=1
        if full and len(test)==len(starts):
            # Preserve supplied values for the audit error, then reconstruct from QR itself.
            if np.isfinite(local[j]).all() and np.any(local[j]):local_error=max(local_error,float(abs(local[j]-expected).max()))
            local[j]=expected
        else:local_error=max(local_error,float(abs(local[j]-expected).max()))
        dc.append(float(b[-1]))
    if full:assert local_error<2e-12,(local_error,'local QR')
    impulse=np.zeros((len(audio),3),complex);impulse[starts]=local[:,selected]
    denominator=np.zeros(len(audio));denominator[starts]=1
    numerator=signal.fftconvolve(impulse,w[:,None],axes=0)[:len(audio)]
    denominator=signal.fftconvolve(denominator,w)[:len(audio)]
    lo,hi=21600,122400;coefficient=numerator[lo:hi]/denominator[lo:hi,None]
    static=A[lo:hi]@beta;dynamic=static.copy();base=beta[selected]-1j*beta[selected+13];ratio=base[:,1]/base[:,0]
    for j in range(3):
        delta=coefficient[:,j]-base[j,0]
        dynamic[:,0]+=(z[lo:hi,j]*delta).real
        dynamic[:,1]+=(z[lo:hi,j]*(coefficient[:,j]*ratio[j]-base[j,1])).real
    return dict(static=static,dynamic=dynamic,beta=beta,denominator=denominator[lo:hi],coefficient=coefficient,
                local_error=local_error,local_qr_windows=len(test),dc=dc)


def budget(audio,main,residual,freq,bands):
    n=len(audio);window=signal.windows.hann(n,sym=False);df=48000/n
    hz,total=signal.periodogram(audio,fs=48000,window=window,detrend=False,axis=0)
    _,m=signal.periodogram(main,fs=48000,window=window,detrend=False,axis=0)
    _,s=signal.periodogram(residual,fs=48000,window=window,detrend=False,axis=0)
    _,cross=signal.csd(main,residual,fs=48000,window=window,nperseg=n,noverlap=0,detrend=False,axis=0)
    result={}
    for name,array in [('total',total),('main',m),('residual',s),('cross',2*cross.real)]:
        result[name]=np.array([sum(array[(hz>=lo)&(hz<hi)])*df for lo,hi in bands])
        result[name+'_near_lines']=np.array([sum(array[abs(hz-f)<=10])*df for f in np.asarray(freq)[selected]])
    return result


try:
    report=load(a.input/'report.json');assert report['result']=='local_selected_core_partition_observed'
    assert len(report['cases'])==80
    for path,digest in report['inputs'].items():assert sha(path)==digest
    with np.load(a.input/'known.npz') as f:fixtures={k:f[k] for k in f.files}
    freq=fixtures['frequencies'];bands=np.array(report['bands_hz'])
    for label in ['constant','nonlinearFM','AM','combined','fast','neighbor']:
        audio=fixtures[label+'_audio'];z=fixtures[label+'_phasors']
        # Empty values supplied explicitly; do not inspect uninitialized memory in known fixtures.
        rebuilt=rebuild(audio,z,freq,local=np.zeros((116,13),complex),full=True)
        errors={}
        if label in ['constant','nonlinearFM','AM','combined']:
            for kind in ['static','dynamic']:
                errors[kind]=float(abs(rebuilt[kind]-fixtures[label+'_'+kind]).max());assert errors[kind]<2e-12
        residual=audio[21600:122400]-rebuilt['dynamic']
        if label in ['constant','nonlinearFM']:assert abs(residual).max()<1e-12
        if label in ['AM','combined']:assert abs(residual).max()<.003
        if label in ['fast','neighbor']:assert np.sqrt(np.mean(residual**2))>.003
        r['known'].append(dict(label=label,native_main_error_FS=errors,dynamic_residual_rms=float(np.sqrt(np.mean(residual**2)))))
    known_budget=budget(fixtures['negative_audio'],fixtures['negative_main'],fixtures['negative_residual'],freq,bands)
    assert (known_budget['total']-known_budget['main']).min()<0 and known_budget['residual'].sum()>0
    r['negative_cross_control_identity_error']=float(abs(known_budget['total']-known_budget['main']-known_budget['residual']-known_budget['cross']).max())
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json');freq=np.array(profile['modal']['frequencies_hz'])
    for row in report['cases']:
        path=a.input/row['file'];assert sha(path)==row['sha256']
        with np.load(path) as f:given={k:f[k] for k in f.files}
        # Full source/control windows; fixed3 per each of ALL72 generated blocks.
        full=row['metadata']['kind']!='generated'
        rebuilt=rebuild(given['original_audio'],given['phasors'],freq,local=given['local_coefficients'].copy(),full=full)
        assert rebuilt['local_error']<2e-12
        assert abs(rebuilt['beta']-given['global_coefficients']).max()<2e-12
        assert abs(rebuilt['denominator']-given['denominator']).max()<2e-12
        tested=np.arange(116) if full else np.array([0,58,115])
        assert abs(np.array(rebuilt['dc'])-given['local_dc'][tested]).max()<2e-12
        errors={};budget_error=0.
        for kind in ['static','dynamic']:
            wanted=rebuilt[kind];residual=given['audio']-wanted
            errors[kind]=float(abs(wanted-given[kind+'_main']).max());assert errors[kind]<2e-12
            assert abs(residual-given[kind+'_residual']).max()<2e-12
            b=budget(given['audio'],wanted,residual,freq,bands)
            for name,value in b.items():budget_error=max(budget_error,float(abs(value-np.array(row['budgets'][kind][name])).max()))
            assert budget_error<2e-12
        r['cases'].append(dict(label=row['label'],source_all_windows_QR=full,local_qr_windows=rebuilt['local_qr_windows'],
             local_coefficient_error=rebuilt['local_error'],full_native_main_error_FS=errors,all_band_power_error=budget_error))
        if len(r['cases'])%10==0:
            save(a.out/'report.json',r);print(dict(cases=len(r['cases']),localQR=localQR),flush=True)
    r.update(result='passed',cases_checked=80,known_cases=6,local_QR_windows=localQR,
             all_source_control_windows_QR=True,fixed_three_QR_windows_per_generated_block=True,
             all_native_waveforms_and_all_band_budgets_checked=True,runtime_changed=False,new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
