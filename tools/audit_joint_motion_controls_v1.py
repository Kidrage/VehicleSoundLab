"""Independent finite-band spectra, scalar features and known/C wave checks."""
import argparse
import cmath
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def fixture_points(plan, row, indices):
    cfg = plan['known']
    rows = []
    for at in indices:
        t = int(at)/48000
        left, right = [], []
        if row['family'] == 'zero':
            rows.append([0.,0.])
            continue
        if row['family'] == 'dense':
            tones = []
            for h in range(1,cfg['dense_harmonics']+1):
                initial = cfg['dense_root_rise_start'] if row['motion'] == 'rising' else cfg['dense_root_static']
                q = (cfg['dense_root_rise_stop']-initial)/cfg['seconds'] if row['motion'] == 'rising' else 0.
                al = .12/math.pow(h,.75)
                phi = .13*h+.013*h*h
                tones.append((initial*h,q*h,al,al*.7*(1+.15*math.sin(.37*h)),phi,phi+.2*math.sin(.23*h),64*h))
        else:
            tones = []
            for j,(f,amp,phi) in enumerate(zip(cfg['safe_hz'],cfg['safe_amplitude'],[.2,-.4,.65,-.8])):
                q = 100. if row['motion']=='rising' and row['family']=='safe' else 0.
                tones.append((f,q,amp,.7*amp,0.,phi,f))
            if row['family'] == 'edge':
                for f,phi in zip(cfg['edge_hz'],[.3,-.7,.9,-.2]):
                    q = cfg['edge_rise_hz_per_s'] if row['motion']=='rising' else 0.
                    amp = cfg['edge_amplitude']
                    tones.append((f,q,amp,.7*amp,0.,phi,f))
        for f,q,al,ar,pl,pr,reference in tones:
            group = sum(reference>=v for v in [6000,8000,10000])
            if row['modulation'] == 'common':
                el=er=1+.4*math.cos(2*math.pi*4*t)
            elif row['modulation'] == 'differential':
                el=1+.25*math.cos(2*math.pi*(2+group)*t+.3*group)
                er=1+.2*math.sin(2*math.pi*(3+group)*t+.5*group)
            else:
                el=er=1.
            base=2*math.pi*(f*t+.5*q*t*t)
            left.append(al*el*cmath.exp(1j*(base+pl)).real)
            right.append(ar*er*cmath.exp(1j*(base+pr)).real)
        rows.append([math.fsum(left),math.fsum(right)])
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    repo=Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy import signal
    from local_atlas_v1.oracle import clock,selection,sparse
    from idle_texture_v1.profile import load as model_load
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],windows=0,DFT_complex_values=0,max_matrix_error_FS2=0.,
           max_DFT_error=0.,max_statistic_error=0.,max_known_sparse_wave_error_FS=0.,max_C_sparse_error_FS=0.)
    try:
        m=load(a.study/'report.json')
        assert m['result'] in ['known_motion_and_AM_observed','frozen_C_source_motion_texture_ablations_observed']
        for name,h in m['sources'].items():
            assert sha(repo/name)==sha(a.study/'exact_sources'/name)==h
        for name,h in m['inputs'].items():
            assert sha(name)==h
        plan=load(a.study/'exact_sources/research/joint_motion_controls_v1_plan.json')
        native=load(a.workspace/'baselines/F3_joint_envelopes_v1/source/research/F3_joint_envelopes_v1_plan.json')
        g=plan['gates'];spec=native['measurement']
        n,hop,size,rate=[spec[k] for k in ['window_samples','hop_samples','fft_samples','rate']]
        window=signal.windows.hann(n,sym=False)
        hz=np.arange(size//2+1)*rate/size
        bands=[np.flatnonzero((hz>=lo)&(hz<hi)) for lo,hi in spec['bands_hz']]
        bins=np.array([int(b[j]) for b in bands for j in [0,len(b)//2,-1]])
        angle=2*np.pi*bins[:,None]*np.arange(n)/size
        trig=np.cos(angle)-1j*np.sin(angle)
        kw=dict(fs=rate,window='hann',nperseg=n,noverlap=0,nfft=size,detrend=False,scaling='density',axis=1)
        for row in m['cases']:
            path=a.study/row['label']/'arrays.npz'
            assert sha(path)==row['arrays_sha256']
            d=np.load(path);audio=d['audio']
            if m['stage']=='known':
                indices=np.unique(np.linspace(0,len(audio)-1,96).astype(int))
                expected=np.array(fixture_points(plan,row,indices))
                error=float(abs(audio[indices]-expected).max())
                assert error<=g['known_sparse_wave_absolute_FS'],(row['label'],error)
                r['max_known_sparse_wave_error_FS']=max(r['max_known_sparse_wave_error_FS'],error)
            else:
                folder=a.study/row['label'];prefix=folder/'C_source'
                for suffix,h in row['C_files_sha256'].items():
                    assert sha(prefix.with_suffix(suffix))==h
                wave,sr=sf.read(prefix.with_suffix('.wav'),dtype='float64',always_2d=True)
                assert sr==48000 and np.array_equal(wave[plan['real']['analysis_first']:],audio)
                events=np.loadtxt(a.study/row['trace'],skiprows=1)
                roots,phases,phase_end=clock(events,len(wave))
                models=[model_load(a.study/p)[0] for p in row['models']]
                base=np.array([model_load(a.study/p)[1] for p in row['models']])
                metadata=load(prefix.with_suffix('.json'))
                trace=np.genfromtxt(prefix.with_suffix('.csv'),delimiter=',',names=True)
                loc=trace['frame'].astype(int)
                assert abs(trace['root_hz']-roots[loc]).max()<=g['clock_root_phase_absolute']
                assert abs(trace['phase_in']-phases[loc]).max()<=g['clock_root_phase_absolute']
                after=np.r_[phases[1:],phase_end]
                assert abs(trace['phase_out']-after[loc]).max()<=g['clock_root_phase_absolute']
                lo,hi,blend,coverage=selection(roots,base)
                assert np.array_equal(trace['lower'],lo[loc]) and np.array_equal(trace['upper'],hi[loc])
                assert np.array_equal(trace['coverage'],coverage[loc]) and abs(trace['blend']-blend[loc]).max()<1e-12
                changes=np.flatnonzero(lo[1:]!=lo[:-1])+1
                indices=set(np.linspace(0,len(wave)-1,36).astype(int))
                for at in [0,1,239,240,95999,96000,96001,239999]+changes.tolist():
                    indices.update(range(max(0,at-1),min(len(wave),at+2)))
                indices=sorted(indices)
                if not row['detail']:
                    models=[{k:(np.zeros_like(v) if k in ('basis','root') else v) for k,v in model.items()} for model in models]
                expected,updates=sparse(models,base,metadata['offsets'],row['seed'],roots,phases,indices)
                error=abs(wave[indices]-expected)
                bound=.5001*np.spacing(abs(expected.astype('float32'))).astype(float)+2e-9
                assert np.all(error<=bound),(row['label'],float((error-bound).max()))
                assert metadata['texture_updates']==[updates]*3
                r['max_C_sparse_error_FS']=max(r['max_C_sparse_error_FS'],float(error.max()))
            starts=np.arange(0,len(audio)-n+1,hop)
            assert np.array_equal(starts,d['window_starts'])
            frames=audio[starts[:,None]+np.arange(n)]
            _,density=signal.welch(frames,**kw)
            _,cross=signal.csd(frames[:,:,1],frames[:,:,0],**kw)
            P=np.empty((len(starts),8,2,2),complex)
            for b,band in enumerate(bands):
                P[:,b,0,0],P[:,b,1,1]=(density[:,band].sum(axis=1)*rate/size).T
                P[:,b,0,1]=cross[:,band].sum(axis=1)*rate/size
                P[:,b,1,0]=P[:,b,0,1].conj()
            error=abs(P-d['P'])
            assert np.all(error<=g['matrix_absolute_FS2']+g['matrix_relative']*abs(P))
            r['max_matrix_error_FS2']=max(r['max_matrix_error_FS2'],float(error.max()))
            fft=np.fft.rfft(frames*window[None,:,None],n=size,axis=1)[:,bins]
            direct=np.stack([(frames[:,:,c]*window)@trig.T for c in [0,1]],axis=-1)
            error=float(abs(fft-direct).max())
            assert error<=g['DFT_absolute']
            r['max_DFT_error']=max(r['max_DFT_error'],error);r['DFT_complex_values']+=direct.size
            power=d['P'].diagonal(axis1=-2,axis2=-1).real
            features=np.array([[10*math.log10(max(float(x),native['features']['log_floor_FS2'])) for x in w.flat] for w in power])
            assert abs(features-d['log_power_dB']).max()<=g['statistics_absolute']
            t=np.array([(int(s)+n/2)/rate for s in starts]);t-=math.fsum(t)/len(t)
            means=np.array([math.fsum(col)/len(col) for col in features.T])
            slope=np.array([math.fsum(float(x*y) for x,y in zip(t,col))/math.fsum(float(x*x) for x in t) for col in features.T])
            assert abs(np.stack([means,slope])-d['trend_coefficients']).max()<=g['statistics_absolute']
            for name,v in [('centered',features-means),('affine_residual',features-means-t[:,None]*slope)]:
                covariance=np.array([[math.fsum(float(x*y) for x,y in zip(left,right))/len(v) for right in v.T] for left in v.T])
                error=float(abs(covariance-d[name+'_covariance']).max())
                assert error<=g['statistics_absolute']
                r['max_statistic_error']=max(r['max_statistic_error'],error)
                for j,lag in enumerate(native['features']['lags_windows']):
                    lagged=np.array([[math.fsum(float(x*y) for x,y in zip(left,right))/(len(v)-lag) for right in v[lag:].T] for left in v[:-lag].T])
                    error=float(abs(lagged-d[name+'_lag_products'][j]).max())
                    assert error<=g['statistics_absolute']
                    r['max_statistic_error']=max(r['max_statistic_error'],error)
            hf=d['affine_residual_covariance'][8:,8:]
            assert abs(float(np.trace(hf))-row['HF_covariance_trace_dB2'])<1e-10
            fraction=float(np.linalg.eigvalsh(hf)[-1]/np.trace(hf)) if np.trace(hf)>g['PC1_covariance_trace_floor_dB2'] else None
            assert fraction==row['HF_PC1_fraction']
            r['cases'].append(dict(label=row['label'],windows=len(starts),original_wave_and_features_verified=True))
            r['windows']+=len(starts)
            save(a.out/'report.json',r)
            print('PASS independent motion/AM observation',row['label'],flush=True)
        r.update(result='independent_motion_observation_audit_passed',producer_report_sha256=sha(a.study/'report.json'),
                 auditor_sha256=sha(__file__),stage=m['stage'],modulation_or_timbre_qualified=False)
    except Exception as exc:
        r.update(result='failed',error=repr(exc))
        raise
    finally:
        save(a.out/'report.json',r)


if __name__=='__main__':
    main()
