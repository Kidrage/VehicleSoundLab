"""Independent linear spectrum and frozen-series aggregation, all failures kept.

No producer meter/statistics/sensitivity imports. Normalized values from a
different FFT are an additional strict diagnostic, not silently reclassified.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','diagnosis','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],maximum_errors={},inputs={},legacy_normalized_failures=[])
    def check(name,x,y,scale,gate=2e-11):
        x,y=np.asarray(x),np.asarray(y)
        assert x.shape==y.shape,(name,x.shape,y.shape)
        if scale==0:
            assert np.count_nonzero(x)==np.count_nonzero(y)==0
            error=0.
        else:error=float(np.max(abs(x-y))/scale) if x.size else 0.
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.))
        assert error<gate,(name,error,gate)
    def stats(gram,ms):
        power=np.stack((gram[:,:,0,0].real,gram[:,:,1,1].real),axis=-1)
        count=len(power)
        mean=np.sum(power,axis=0)/count
        centered=power.reshape(count,12)-mean.ravel()
        covariance=np.array([[sum(centered[k,i]*centered[k,j] for k in range(count))/count
            for j in range(12)] for i in range(12)])
        cv=np.zeros((6,2));defined=mean>0
        for b in range(6):
            for c in range(2):
                if defined[b,c]:cv[b,c]=np.sqrt(covariance[2*b+c,2*b+c])/mean[b,c]
        den=np.sqrt(mean[:,0])*np.sqrt(mean[:,1]);valid=den>0
        coherence=np.zeros(6,complex)
        for b in range(6):
            if valid[b]:coherence[b]=sum(gram[k,b,0,1] for k in range(count))/count/den[b]
        lags=[]
        for lag in range(1,min(9,count)):
            lags.append([[sum(centered[k,i]*centered[k+lag,j] for k in range(count-lag))/(count-lag)
                for j in range(12)] for i in range(12)])
        return dict(mean_power=mean,power_defined=defined,CV=cv,covariance=covariance,
            lag_covariance=np.array(lags),complex_coherence=coherence,coherence_defined=valid,
            mean_mid_side=ms.mean(axis=0))
    try:
        source=load(a.study/'report.json')
        assert source['result']=='extraction_sound_known_measured' and len(source['cases'])==9
        diagnosis=load(a.diagnosis/'report.json')
        assert diagnosis['original_failure']['result']=='failed'
        for path in (a.study/'report.json',a.diagnosis/'report.json'):r['inputs'][str(path)]=sha(path)
        for name,digest in source['sources'].items():assert sha(a.study/'exact_sources'/name)==digest
        for c in source['cases']:
            path=a.study/c['file'];assert sha(path)==c['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as f:z={k:f[k] for k in f.files}
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
            energy=max(float(np.max(np.mean(raw*raw,axis=1))),float(np.max(abs(G))))
            check('broad_Gram',z['broad_Gram'],G,energy)
            check('direct_mid_side',z['broad_mid_side'],MG,energy)
            check('full_Gram',z['full_Gram'],perbin.sum(axis=1)*rate/size,energy)
            expected_time=np.array([(frame*w[:,None]).T@(frame*w[:,None])/np.dot(w,w) for frame in raw])
            check('Parseval_real_part',z['full_Gram'].real,expected_time,energy)
            series=[('broad',G,MG,bands, np.r_[1.,np.full(size//2-1,2.),1.]/(size*np.dot(w,w)))]
            if c['line_diagnostic']:
                bins=4*np.arange(1,289)
                ids=np.searchsorted([3000,6000,8000,10000,14000],64*np.arange(1,289),side='right')
                gain=rate*np.dot(w,w)/w.sum()**2
                LG=np.stack([perbin[:,bins[ids==b]].sum(axis=1)*gain for b in range(6)],axis=1)
                LM=np.stack([msdiag[:,bins[ids==b]].sum(axis=1)*gain for b in range(6)],axis=1)
                check('line_Gram',z['line_Gram'],LG,energy)
                check('line_direct_mid_side',z['line_mid_side'],LM,energy)
                series.append(('line',LG,LM,ids,np.full(len(bins),2/w.sum()**2)))
            case=dict(label=c['label'],operator_and_aggregation_qualified=False,
                normalized_cross_operator=[],windows=len(starts),energy_scale=energy)
            for prefix,gram,mid_side,groups,weights in series:
                frozen=stats(z[prefix+'_Gram'],z[prefix+'_mid_side'])
                independent=stats(gram,mid_side)
                for field in ('power_defined','coherence_defined'):
                    assert np.array_equal(z[prefix+'_'+field],frozen[field])
                    assert np.array_equal(z[prefix+'_'+field],independent[field])
                for field in ('mean_power','mean_mid_side','CV','complex_coherence','covariance','lag_covariance'):
                    own=frozen[field]
                    scale=(energy**2 if field in ('covariance','lag_covariance') else
                        max(1.,float(np.max(abs(own)))) if field=='CV' else
                        1. if field=='complex_coherence' else energy)
                    check(prefix+'_frozen_'+field,z[prefix+'_'+field],own,scale,gate=2e-10)
                    # All original cross-FFT statistic gates are evaluated and
                    # reported, including failures on tiny positive leakage.
                    delta=z[prefix+'_'+field]-independent[field]
                    legacy_scale=(max(1.,float(np.max(abs(independent[field])))) if field=='CV' else scale)
                    normalized=0. if legacy_scale==0 else float(np.max(abs(delta))/legacy_scale)
                    passed=bool(normalized<2e-10)
                    case['normalized_cross_operator'].append(dict(prefix=prefix,field=field,
                        normalized_error=normalized,original_gate=2e-10,passed=passed))
                    if not passed:
                        failing=np.argwhere(abs(delta)>=(2e-10*legacy_scale)).tolist()
                        r['legacy_normalized_failures'].append(dict(label=c['label'],prefix=prefix,
                            field=field,error=normalized,indices=failing,
                            power_resolved=z[prefix+'_power_resolved'].tolist()))
                # Independent scalar arithmetic for the engineering envelope.
                eps=np.finfo(float).eps;gamma=32*size*eps/(1-32*size*eps)
                declared=.5-.5*np.cos(2*np.pi*np.arange(size)/size)
                windowed=raw*declared[None,:,None]
                error=np.array([[gamma*sum(abs(frame[:,ch])) for ch in (0,1)] for frame in windowed])
                errscale=float(np.max(error))
                check(prefix+'_sensitivity_fourier',z[prefix+'_FFT_absolute_sensitivity'],error,errscale)
                uncertainty=np.empty_like(z[prefix+'_power'])
                cross_error=np.empty_like(z[prefix+'_power'][:,:,0])
                for j in range(len(raw)):
                    for b in range(6):
                        e=error[j]*np.sqrt(sum(weights[groups==b]))
                        roots=np.sqrt(z[prefix+'_power'][j,b])
                        uncertainty[j,b]=2*roots*e+e*e
                        cross_error[j,b]=roots[0]*e[1]+roots[1]*e[0]+e[0]*e[1]
                check(prefix+'_sensitivity_power',z[prefix+'_power_uncertainty'],uncertainty,float(np.max(uncertainty)))
                check(prefix+'_sensitivity_cross',z[prefix+'_cross_uncertainty'],cross_error,float(np.max(cross_error)))
                mean=frozen['mean_power'];mean_error=uncertainty.mean(axis=0)
                assert np.array_equal(z[prefix+'_power_resolved'],mean>mean_error)
                assert not bool(z[prefix+'_sensitivity_is_certified_bound'])
                # A compatibility check, never a proof of a certified FFT bound.
                power=np.stack((gram[:,:,0,0].real,gram[:,:,1,1].real),axis=-1)
                assert np.all(abs(z[prefix+'_power']-power)<=2*uncertainty)
                assert np.all(abs(z[prefix+'_Gram'][:,:,0,1]-gram[:,:,0,1])<=2*cross_error)
            selected=(np.arange(size//2+1) if size==128 else np.unique(np.r_[0,size//2,
                [k for b in range(6) for k in (np.flatnonzero(bands==b)[0],np.flatnonzero(bands==b)[len(np.flatnonzero(bands==b))//2],np.flatnonzero(bands==b)[-1])]]))
            theta=2*np.pi*np.arange(size)[:,None]*selected[None,:]/size
            direct=np.stack([np.sum(raw[:3,:,ch,None]*w[None,:,None]*(np.cos(theta)-1j*np.sin(theta))[None],axis=1) for ch in (0,1)],axis=-1)
            fft=np.fft.rfft(raw[:3]*w[None,:,None],axis=1)[:,selected]
            amplitude=float(np.max(np.sum(abs(raw[:3]*w[None,:,None]),axis=1)))
            check('explicit_DFT',fft,direct,amplitude,gate=2e-10)
            if c['label']=='weak_HF':
                assert z['broad_power_resolved'].all() and np.max(z['broad_mean_power'])<1e-24
            if c['label']=='mono':
                assert np.count_nonzero(z['broad_mid_side'][:,:,1])==0
                assert not z['line_power_resolved'][-1].any()
                assert z['broad_power_resolved'].all()
            if c['label']=='inverted_mono':assert np.count_nonzero(z['broad_mid_side'][:,:,0])==0
            case.update(operator_and_aggregation_qualified=True,explicit_DFT_bins=len(selected),
                no_absolute_energy_floor=True,broad_power_resolved=z['broad_power_resolved'].tolist())
            r['cases'].append(case);save(a.out/'report.json',r)
            print('COMPOSED_SOUND_AUDIT',c['label'],'PASS; cumulative legacy failures',len(r['legacy_normalized_failures']),flush=True)
        scaled=load(a.study/'known_scaled_comparison.json')
        check('known_power_gain_dB',scaled['broad']['power_change_dB'],np.full((6,2),20*np.log10(1.7)),1.,gate=2e-10)
        zero=load(a.study/'zero_reference_comparison.json')
        assert all(v is None for row in zero['broad']['power_change_dB'] for v in row)
        r.update(result='independent_extraction_sound_composition_verified',
            operator_and_frozen_series_aggregation_qualified=True,
            legacy_cross_operator_all_statistics_qualified=not r['legacy_normalized_failures'],
            prior_failed_audit_remains_failed=True,producer_sha256=sha(a.study/'report.json'),
            meter_not_imported=True,sensitivity_not_certified=True,
            no_real_fit_or_C_or_hearing_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
