"""Check clock/DFT sensitivity and whether the cap contrast actually changes audio."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--analysis',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),repo/'tools/drive_evidence_v1/sources.py']
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.magnitude-timescale-verification/1',result='running',
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    analysis_report_sha256=sha(args.analysis/'report.json'),detuned_tone_controls=[],
    actual_clock_dft=[],trials=[])
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def geometric(omega,n):
    if abs(omega)<1e-12:return complex(n)
    return np.exp(.5j*omega*(n-1))*np.sin(n*omega/2)/np.sin(omega/2)


try:
    a=json.loads((args.analysis/'report.json').read_text(encoding='utf-8'));assert a['result']=='pass'
    for source,digest in a['source_sha256'].items():assert sha(args.analysis/'exact_sources'/source)==digest
    for path,digest in a['input_sha256'].items():assert sha(path)==digest,path
    # Exact finite-window response, including the conjugate negative-frequency
    # term. No model or analysis-module call is used for this independent oracle.
    n=1024;index=np.arange(n);k=171
    for error in (0,.001,.003):
        actual_omega=2*np.pi*k*(1+error)/n;bin_omega=2*np.pi*k/n
        phases=np.array([.3,-.4]);amplitudes=np.array([.11,.07])
        audio=amplitudes[None,:]*np.cos(actual_omega*index[:,None]+phases[None,:])
        actual=np.fft.rfft(audio,axis=0)[k]*2/n
        expected=amplitudes/n*(np.exp(1j*phases)*geometric(actual_omega-bin_omega,n)+
            np.exp(-1j*phases)*geometric(-actual_omega-bin_omega,n))
        relative=float(np.max(abs(actual-expected)/abs(expected)))
        assert relative<1e-10,relative
        report['detuned_tone_controls'].append(dict(relative_clock_error=error,complex_relative_error=relative,
            observed_magnitude_error_db_LR=(20*np.log10(abs(actual)/amplitudes)).tolist(),
            meaning='Known fixed-amplitude oscillator, fixed analysis bin; not a measurement of real clock error'))
    for row in a['clock_controls']:
        path=args.analysis/row['file'];assert sha(path)==row['sha256']
        audio,rate=sf.read(path,always_2d=True);assert rate==48000
        starts=np.arange(0,len(audio)-1024+1,256);errors=[]
        for frame in sorted({0,len(starts)//2,len(starts)-1}):
            for harmonic in (5,37,103,171):
                window=audio[starts[frame]:starts[frame]+n]
                phase=2*np.pi*harmonic*index/n
                direct=(np.cos(phase)-1j*np.sin(phase))@window*2/n
                fft=np.fft.rfft(window,axis=0)[harmonic]*2/n
                errors.append(float(np.max(abs(direct-fft)/np.maximum(abs(fft),1e-20))))
        assert max(errors)<1e-10,max(errors)
        report['actual_clock_dft'].append(dict(relative_clock_error=row['clock_fractional_error'],
            maximum_complex_relative_error=max(errors)))
    oldroot=args.workspace/'baselines/temporal_texture_v1'
    for trial in a['trials']:
        old=oldroot/f"evidence/magnitude1/magnitude_{trial['seed']}_1.wav"
        path=args.analysis/trial['path'];assert sha(path)==trial['sha256']
        left,fs=sf.read(old,always_2d=True);right,rate=sf.read(path,always_2d=True)
        assert rate==fs==48000 and left.shape==right.shape
        maximum=float(abs(left-right).max())
        assert maximum<1e-7,maximum
        report['trials'].append(dict(seed=trial['seed'],file_bytes_equal=sha(old)==sha(path),
            float_samples_equal=bool(np.array_equal(left,right)),maximum_float_difference=maximum,
            rms_difference=float(np.sqrt(np.mean((left-right)**2))),
            decision='No meaningful synthesis change; raising the cap is not a fix for this fitted model'))
    # Same short target's multi-lag factor statistics, independently projected
    # from frozen directions; population AR1 rho^lag is only a benchmark.
    frozen=args.workspace/'baselines/residual_motion_v1/evidence/fit1/reference.wav'
    reference,rate=sf.read(frozen,always_2d=True);assert rate==48000
    archive=np.load(oldroot/'evidence/magnitude1/candidate_moments.npz')
    starts=np.arange(0,len(reference)-n+1,256)
    z=np.array([np.fft.rfft(reference[at:at+n],axis=0)[1:301]*2/n for at in starts])
    logs=np.log(np.maximum(abs(z),np.maximum(archive['rms']*1e-6,1e-20)[None,:]))
    centered=(logs-logs.mean(axis=0)).reshape(len(starts),-1)
    basis=archive['basis'].transpose(1,0,2).reshape(12,-1)
    energies=np.sum(basis*basis,axis=1);scores=centered@basis.T/energies[None,:]
    factor_rows=[]
    for factor in range(12):
        values=scores[:,factor];rho=float(archive['rho'][factor]);lags=[]
        for lag in (1,2,4,8,16,32,64):
            observed=float(values[lag:]@values[:-lag]/(values[:-lag]@values[:-lag]))
            lags.append(dict(lag_frames=lag,lag_seconds=lag*256/48000,
                observed_finite_block_ratio=observed,population_AR1_benchmark=rho**lag,
                paired_observations=len(values)-lag))
        cycles=values[:len(values)//4*4].reshape(-1,4)
        cycle_mean=cycles.mean(axis=1)
        factor_rows.append(dict(factor=factor,rho=rho,
            within_four_hop_variance=float(np.mean((cycles-cycle_mean[:,None])**2)),
            cycle_mean_squared=float(np.mean(cycle_mean**2)),lags=lags))
    report.update(result='pass',factor_lag_observations=factor_rows,
        interpretation='One-hop AR1 does not retain this target\'s multi-lag structure; no stationary/causal engine inference or formal significance claim',
        runtime_changes=False,human_accepted=False,
        candidate_decision='No new listening candidate; cap contrast is numerically unchanged; keep original frozen review')
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=report['result'],trials=report['trials'],
    maximum_clock_DFT_error=max(r['maximum_complex_relative_error'] for r in report['actual_clock_dft']))))
