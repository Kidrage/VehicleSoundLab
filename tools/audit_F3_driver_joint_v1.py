"""Independent bus reconstruction, Welch/CSD, DFT and joint features."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','capture','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy import signal
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],windows=0,DFT_complex_values=0,max_matrix_error_FS2=0,max_DFT_error=0,max_statistic_error=0)
    try:
        m=load(a.study/'report.json');assert m['result']=='existing_one_driver_joint_budgets_measured'
        for n,h in m['sources'].items():assert sha(a.study/'exact_sources'/n)==sha(repo/n)==h
        for n,h in m['inputs'].items():assert sha(n)==h
        cfg=load(a.study/'exact_sources/research/F3_driver_joint_v1_plan.json');g=cfg['gates']
        plan=load(a.workspace/'baselines/F3_joint_envelopes_v1/source/research/F3_joint_envelopes_v1_plan.json');spec=plan['measurement']
        n,hop,size,rate=[spec[k] for k in ['window_samples','hop_samples','fft_samples','rate']]
        window=signal.windows.hann(n,sym=False);hz=np.arange(size//2+1)*rate/size
        bands=[np.flatnonzero((hz>=lo)&(hz<hi)) for lo,hi in spec['bands_hz']]
        bins=np.array([int(b[j]) for b in bands for j in [0,len(b)//2,-1]])
        angle=2*np.pi*bins[:,None]*np.arange(n)/size;trig=np.cos(angle)-1j*np.sin(angle)
        kw=dict(fs=rate,window='hann',nperseg=n,noverlap=0,nfft=size,detrend=False,scaling='density',axis=1)
        def close(got,expected):
            error=abs(got-expected);assert np.all(error<=g['matrix_absolute_FS2']+g['matrix_relative']*abs(expected))
            r['max_matrix_error_FS2']=max(r['max_matrix_error_FS2'],float(error.max()))
        # Known signed interference is tested before any recorded engine.
        # Exact half scaling preserves FFT proportionality at every bin,
        # including finite-window sidelobes; no ideal infinite-tone shortcut.
        from driver_joint_v1.budget import measure
        t=np.arange(144000)/rate
        dna=np.column_stack([.08*np.cos(2*np.pi*3750*t)+.04*np.cos(2*np.pi*9000*t),.06*np.cos(2*np.pi*3750*t+.2)+.03*np.cos(2*np.pi*9000*t-.4)])
        for gain in [0,.5,-.5]:
            layers=np.zeros((len(t),6,2));layers[:,0]=dna;layers[:,2]=gain*dna
            test=measure(dna+gain*dna,layers,spec)
            close(test['P_other'],gain*gain*test['P_dna']);close(test['cross_DNA_other'],gain*test['P_dna'])
            close(test['P_tap_sum'],(1+gain)**2*test['P_dna'])
            if gain<0:assert np.min(test['signed_cross_eigenvalues'])<0
        r['known_signed_interference_controls']=3
        for row in m['cases']:
            d=np.load(a.study/row['label']/'arrays.npz');assert sha(a.study/row['label']/'arrays.npz')==row['arrays_sha256']
            base=a.capture/row['label'];original,rate0=sf.read(base/'stereo512_out.wav',always_2d=True,dtype='float64')
            stems,rate1=sf.read(base/'stereo512_layers.wav',always_2d=True,dtype='float64')
            first=cfg['trace']['warmup_frames'];assert rate0==rate1==rate
            assert np.array_equal(d['audio'],original[first:]) and np.array_equal(d['layers'],stems[first:].reshape(-1,6,2))
            raw,raw_rate=sf.read(base/'stereo512_raw.wav',always_2d=True,dtype='float64')
            env=np.fromfile(base/'stereo512_envelope.f64',dtype='<f8')[first:]
            assert raw_rate==rate and np.array_equal(raw[first:],d['raw']) and np.array_equal(env,d['envelope'])
            assert abs(d['raw']*env[:,None]-d['layers'][:,0]).max()<=g['bus_sum_absolute_FS']
            dna=d['layers'][:,0];other=np.zeros_like(dna)
            for layer in range(1,6):other+=d['layers'][:,layer]
            summed=dna+other
            starts=np.arange(0,len(summed)-n+1,hop);assert np.array_equal(starts,d['window_starts'])
            inputs=[dna,other,d['audio'],summed,d['raw']];measured=[]
            for wave in inputs:
                frames=wave[starts[:,None]+np.arange(n)]
                _,density=signal.welch(frames,**kw);_,cross=signal.csd(frames[:,:,1],frames[:,:,0],**kw)
                P=np.empty((len(starts),8,2,2),complex)
                for b,indices in enumerate(bands):
                    P[:,b,0,0],P[:,b,1,1]=(density[:,indices].sum(axis=1)*rate/size).T
                    P[:,b,0,1]=cross[:,indices].sum(axis=1)*rate/size;P[:,b,1,0]=P[:,b,0,1].conjugate()
                measured.append(P)
                ft=np.fft.rfft(frames*window[None,:,None],n=size,axis=1)[:,bins]
                direct=np.stack([(frames[:,:,c]*window)@trig.T for c in range(2)],axis=-1)
                error=float(abs(ft-direct).max());assert error<=g['independent_DFT_absolute']
                r['max_DFT_error']=max(r['max_DFT_error'],error);r['DFT_complex_values']+=direct.size
            for P,key in zip(measured,['P_dna','P_other','P_canonical','P_tap_sum','P_raw']):close(d[key],P)
            X=np.empty_like(measured[0])
            for i in range(2):
                for j in range(2):
                    _,csd=signal.csd(other[starts[:,None]+np.arange(n),j],dna[starts[:,None]+np.arange(n),i],**kw)
                    for b,indices in enumerate(bands):X[:,b,i,j]=csd[:,indices].sum(axis=1)*rate/size
            close(X,d['cross_DNA_other']);close(X+X.swapaxes(-1,-2).conj(),d['signed_cross'])
            close(measured[0]+measured[1]+X+X.swapaxes(-1,-2).conj(),measured[3])
            for prefix,key in [('', 'P_canonical'),('DNA_', 'P_dna'),('RAW_', 'P_raw')]:
                power=d[key].diagonal(axis1=-2,axis2=-1).real;floor=plan['features']['log_floor_FS2']
                features=np.array([[10*math.log10(max(float(p),floor)) for p in w.flat] for w in power])
                assert np.max(abs(features-d[prefix+'log_power_dB']))<=g['independent_statistics_absolute']
                times=np.array([(int(s)+n/2)/rate for s in starts]);dt=times-math.fsum(times)/len(times)
                means=np.array([math.fsum(col)/len(col) for col in features.T])
                slopes=np.array([math.fsum(float(t*x) for t,x in zip(dt,col))/math.fsum(float(t*t) for t in dt) for col in features.T])
                assert abs(np.stack([means,slopes])-d[prefix+'trend_coefficients']).max()<=g['independent_statistics_absolute']
                for name,v in [('centered',features-means),('affine_residual',features-means-dt[:,None]*slopes)]:
                    cv=np.array([[math.fsum(float(x*y) for x,y in zip(left,right))/len(v) for right in v.T] for left in v.T])
                    error=float(abs(cv-d[prefix+name+'_covariance']).max());assert error<=g['independent_statistics_absolute']
                    r['max_statistic_error']=max(r['max_statistic_error'],error)
                    for j,lag in enumerate(plan['features']['lags_windows']):
                        lg=np.array([[math.fsum(float(x*y) for x,y in zip(left,right))/(len(v)-lag) for right in v[lag:].T] for left in v[:-lag].T])
                        error=float(abs(lg-d[prefix+name+'_lag_products'][j]).max());assert error<=g['independent_statistics_absolute']
                        r['max_statistic_error']=max(r['max_statistic_error'],error)
            if 'source_context' in row:
                path=a.study/row['label']/'source_comparison.npz';assert sha(path)==row['comparison_sha256']
                comparison=np.load(path)
                source=np.load(a.workspace/'baselines/F3_joint_envelopes_v1/evidence/measure1'/row['source_context']/'arrays.npz')
                expected=source['affine_residual_covariance']-d['affine_residual_covariance']
                assert np.array_equal(expected,comparison['covariance_difference'])
                assert abs(np.linalg.eigvalsh(expected)-comparison['covariance_difference_eigenvalues']).max()<=1e-10
            r['windows']+=len(starts);r['cases'].append(dict(label=row['label'],original_captures_exact=True,all_signed_matrices_and_scalar_statistics=True))
            save(a.out/'report.json',r);print('PASS independent driver joint budget',row['label'],flush=True)
        r.update(result='independent_driver_joint_audit_passed',producer_report_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),additional_modulation_qualified=False)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(a.out/'report.json',r)


if __name__=='__main__':main()
