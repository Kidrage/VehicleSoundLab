"""Independent Welch/CSD, direct DFT and explicit lag statistics; no meter import."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],maximum_errors={},inputs={})
    def check(name,x,y,scale,gate=2e-11):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
        if scale==0:assert np.count_nonzero(x)==np.count_nonzero(y)==0;error=0.
        else:error=float(np.max(abs(x-y))/scale) if x.size else 0.
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.))
        assert error<gate,(name,error,gate)
    try:
        source=load(a.study/'report.json');assert source['result']=='extraction_sound_known_measured' and len(source['cases'])==9
        for name,digest in source['sources'].items():assert sha(a.study/'exact_sources'/name)==digest
        r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
        for c in source['cases']:
            path=a.study/c['file'];assert sha(path)==c['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as f:z={name:f[name] for name in f.files}
            audio=z['audio'];size,hop,rate=int(z['size']),int(z['hop']),float(z['rate'])
            starts=list(range(0,len(audio)-size+1,hop))
            raw=np.array([audio[first:first+size] for first in starts])
            w=signal.windows.hann(size,sym=False)
            kw=dict(fs=rate,window=w,nperseg=size,noverlap=0,detrend=False,scaling='density',axis=1)
            frequency,diag=signal.welch(raw,**kw)
            _,cross=signal.csd(raw[:,:,1],raw[:,:,0],**kw)
            perbin=np.empty((len(raw),len(frequency),2,2),complex)
            perbin[:,:,0,0]=diag[:,:,0];perbin[:,:,1,1]=diag[:,:,1]
            perbin[:,:,0,1]=cross;perbin[:,:,1,0]=cross.conj()
            ms=np.stack(((raw[:,:,0]+raw[:,:,1])/2,(raw[:,:,0]-raw[:,:,1])/2),axis=-1)
            _,msdiag=signal.welch(ms,**kw)
            bands=np.searchsorted([3000,6000,8000,10000,14000],frequency,side='right')
            G=np.stack([perbin[:,bands==b].sum(axis=1)*rate/size for b in range(6)],axis=1)
            MG=np.stack([msdiag[:,bands==b].sum(axis=1)*rate/size for b in range(6)],axis=1)
            energy=float(np.max(np.mean(raw*raw,axis=1)))
            # Raw time and windowed scales differ slightly; choose the exact
            # same fixture's largest actual power, never an absolute floor1.
            energy=max(energy,float(np.max(abs(G))))
            check('broad_Gram',z['broad_Gram'],G,energy)
            check('direct_mid_side',z['broad_mid_side'],MG,energy)
            check('full_Gram',z['full_Gram'],perbin.sum(axis=1)*rate/size,energy)
            expected_time=np.array([[(frame*w[:,None]).T@(frame*w[:,None])][0]/np.sum(w*w) for frame in raw])
            check('Parseval_real_part',z['full_Gram'].real,expected_time,energy)
            series=[('broad',G,MG)]
            if c['line_diagnostic']:
                bins=4*np.arange(1,289)
                line_ids=np.searchsorted([3000,6000,8000,10000,14000],64*np.arange(1,289),side='right')
                gain=rate*np.sum(w*w)/np.sum(w)**2
                LG=np.stack([perbin[:,bins[line_ids==b]].sum(axis=1)*gain for b in range(6)],axis=1)
                LM=np.stack([msdiag[:,bins[line_ids==b]].sum(axis=1)*gain for b in range(6)],axis=1)
                check('line_Gram',z['line_Gram'],LG,energy)
                check('line_direct_mid_side',z['line_mid_side'],LM,energy)
                series.append(('line',LG,LM))
            for prefix,gram,mid_side in series:
                power=np.stack((gram[:,:,0,0].real,gram[:,:,1,1].real),axis=-1)
                mean=np.sum(power,axis=0)/len(power)
                centered=power.reshape(len(power),12)-mean.ravel()
                cov=np.array([[np.dot(centered[:,i],centered[:,j])/len(power) for j in range(12)] for i in range(12)])
                cv=np.zeros((6,2));defined=mean>0
                for i in range(6):
                    for j in range(2):
                        if defined[i,j]:cv[i,j]=np.sqrt(cov[2*i+j,2*i+j])/mean[i,j]
                den=np.sqrt(mean[:,0])*np.sqrt(mean[:,1]);valid=den>0
                coherence=np.zeros(6,complex)
                coherence[valid]=np.sum(gram[:,:,0,1],axis=0)[valid]/len(power)/den[valid]
                assert np.array_equal(z[prefix+'_power_defined'],defined)
                assert np.array_equal(z[prefix+'_coherence_defined'],valid)
                check(prefix+'_mean_power',z[prefix+'_mean_power'],mean,energy)
                check(prefix+'_mean_mid_side',z[prefix+'_mean_mid_side'],mid_side.mean(axis=0),energy)
                check(prefix+'_CV',z[prefix+'_CV'],cv,max(1.,float(np.max(abs(cv)))),gate=2e-10)
                check(prefix+'_coherence',z[prefix+'_complex_coherence'],coherence,1.,gate=2e-10)
                check(prefix+'_covariance',z[prefix+'_covariance'],cov,energy**2,gate=2e-10)
                lags=[]
                for lag in range(1,min(9,len(power))):
                    lags.append([[np.dot(centered[:-lag,i],centered[lag:,j])/(len(power)-lag) for j in range(12)] for i in range(12)])
                check(prefix+'_lag_covariance',z[prefix+'_lag_covariance'],np.array(lags),energy**2,gate=2e-10)
            # Actual4096 all band edges/centers, and compact128 ALL bins.
            selected=(np.arange(size//2+1) if size==128 else np.unique(np.r_[0,size//2,
                [k for b in range(6) for k in (np.flatnonzero(bands==b)[0],np.flatnonzero(bands==b)[len(np.flatnonzero(bands==b))//2],np.flatnonzero(bands==b)[-1])]]))
            theta=2*np.pi*np.arange(size)[:,None]*selected[None,:]/size
            direct=np.stack([np.sum(raw[:3,:,channel,None]*w[None,:,None]*(np.cos(theta)-1j*np.sin(theta))[None],axis=1) for channel in (0,1)],axis=-1)
            fft=np.fft.rfft(raw[:3]*w[None,:,None],axis=1)[:,selected]
            amplitude=float(np.max(np.sum(abs(raw[:3]*w[None,:,None]),axis=1)))
            check('explicit_DFT',fft,direct,amplitude,gate=2e-10)
            if c['label']=='weak_HF':assert z['broad_power_defined'][5].all() and np.max(z['broad_mean_power'])<1e-24
            if c['label']=='mono':assert np.count_nonzero(z['broad_mid_side'][:,:,1])==0
            if c['label']=='inverted_mono':assert np.count_nonzero(z['broad_mid_side'][:,:,0])==0
            r['cases'].append(dict(label=c['label'],all_qualified=True,windows=len(starts),explicit_DFT_bins=len(selected),
                energy_scale=energy,no_absolute_energy_floor=True))
            save(a.out/'report.json',r)
            print('AUDIT_SOUND_METER',c['label'],'PASS',flush=True)
        scaled=load(a.study/'known_scaled_comparison.json')
        check('known_power_gain_dB',scaled['broad']['power_change_dB'],np.full((6,2),20*np.log10(1.7)),1.,gate=2e-10)
        zero=load(a.study/'zero_reference_comparison.json')
        assert all(v is None for row in zero['broad']['power_change_dB'] for v in row)
        r.update(result='independent_extraction_sound_known_verified',all_qualified=True,
            producer_sha256=sha(a.study/'report.json'),meter_not_imported=True,
            no_real_fit_or_new_source_or_C_or_hearing_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
