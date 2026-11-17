"""Independently audit B raw PCM, time-energy shape, finite FFT powers and C output."""
import argparse
from pathlib import Path
import numpy as np
import soundfile as sf
from research_archive_v1 import sha,load,save


def fft_power(x):
    if x.ndim==1:x=x[:,None]
    n=2048;window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    starts=range(0,len(x)-n+1,n//2)
    cells=np.stack([x[k:k+n]*window[:,None] for k in starts])
    z=np.fft.rfft(cells,axis=1);power=np.mean(abs(z)**2,axis=(0,2))/(48000*np.dot(window,window))
    power[1:-1]*=2
    return np.fft.rfftfreq(n,1/48000),power


def t90(x):
    if x.ndim==1:x=x[:,None]
    cumulative=np.cumsum(np.sum(x*x,axis=1))
    return int(np.searchsorted(cumulative,cumulative[-1]*.9))/48000


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    work=data/'references/analysis/B_startup_context_v1';r=load(a.candidate/'report.json')
    source=Path(r['source']['path']);assert sha(source)==r['source']['sha256']
    manifest=load(repo/'references/segments_v1.json')['sources']['B']
    assert sha(data/manifest['video'])==manifest['video_sha256']
    def raw(first,last):
        with sf.SoundFile(source) as stream:
            assert stream.samplerate==48000
            stream.seek(round(first*48000));return stream.read(round(last*48000)-round(first*48000),dtype='float64',always_2d=True)
    timeline_rows=[]
    for run in ('overview1','overview2','fine1','setup1','initial-fine1'):
        for case in load(work/run/'report.json')['cases']:
            folder=work/run/case['name'];origin=case['source'];assert sha(origin['path'])==manifest['master_sha256']
            expected=raw(*origin['source_seconds']);original,rate=sf.read(folder/'original.wav',always_2d=True)
            monitor,mr=sf.read(folder/'monitor.wav',always_2d=True)
            assert rate==mr==48000 and np.array_equal(original,expected) and np.array_equal(monitor,expected*.25)
            assert case['monitor_gain']==.25 and not case['physical_identity_confirmed']
            for frame in case['frames']:
                assert sha(folder/frame['file'])==frame['sha256']
                assert abs(frame['requested_video_seek_seconds']-frame['source_audio_seconds']-.036291667)<2e-14
            timeline_rows.append(dict(run=run,case=case['name'],frames=len(case['frames']),original_PCM_exact=True))
    # Compute original full-band contrasts directly; names in the generic probe
    # are parameter roles, not chronological ordering for the catch job.
    contrasts=[]
    for name in ('crank','catch'):
        q=load(work/(name+'-probe1')/'report.json');x=raw(*q['source']['source_seconds'])
        for bg in q['backgrounds']:
            b=raw(*bg['source']['source_seconds'])
            actual=float(10*np.log10(np.mean(x*x)/np.mean(b*b)))
            assert abs(actual-bg['full_contrast_db'])<1e-11
            contrasts.append(dict(case=name,role=bg['name'],seconds=bg['source']['source_seconds'],contrast_db=actual))
    max_error=0.;shape=[];qualified=[]
    for case in r['cases']:
        job=case['profile']['source_job'];x=raw(*job['seconds']);b=raw(*job['background_seconds'])
        reference,rate=sf.read(work/case['name']/'reference.wav',always_2d=True)
        assert rate==48000 and np.array_equal(x,reference)
        f,px=fft_power(x);_,pb=fft_power(b);debt=np.maximum(0,px-pb)
        for seed in case['seeds']:
            y,yr=sf.read(a.candidate/f"{case['name']}-seed{seed['seed']}-C.wav")
            assert yr==48000 and np.isfinite(y).all() and len(y)==45600
            fy,py=fft_power(y[:len(x)]);assert np.array_equal(f,fy)
            for band in seed['bands']:
                lo,hi=band['hz'];use=(f>=lo)&(f<hi)
                target=float(debt[use].sum()*48000/2048);actual=float(py[use].sum()*48000/2048)
                assert np.isclose(target,band['target_power'],rtol=2e-11,atol=1e-24)
                # Producer Welch receives actual C float32 PCM; SciPy retains
                # float32 power, while this independent NumPy FFT is float64.
                # Account for eight float32 epsilons, not a sound-fit tolerance.
                rounding=8*np.finfo(np.float32).eps
                assert np.isclose(actual,band['generated_power'],rtol=rounding,atol=1e-24)
                max_error=max(max_error,abs(target-band['target_power']),abs(actual-band['generated_power']))
                assert abs(10*np.log10(actual/target)-band['error_db'])<10*np.log10(1/(1-rounding))+1e-10
                assert abs(10*np.log10(actual/target))<3.
            actual_t90=t90(y[:len(x)])
            assert actual_t90==seed['temporal']['t10_t50_t90_seconds'][2]
            shape.append(dict(case=case['name'],seed=seed['seed'],t90_seconds=actual_t90,
                t90_error_seconds=abs(actual_t90-t90(x))))
            qualified.append(max(abs(band['error_db']) for band in seed['bands'])<3.)
        assert t90(x)==case['reference_temporal']['t10_t50_t90_seconds'][2]
    old=[v['t90_error_seconds'] for v in shape if v['case']=='crank-author1']
    held=[v['t90_error_seconds'] for v in shape if v['case']=='crank-hold-author1']
    assert max(held)<min(old) and max(held)<.04 and all(qualified)
    assert r['catch_refused'] and r['catch']['document'] is None and not r['catch'].get('last_version')
    assert not (work/'catch-author1/profile.json').exists()
    assert load(work/'catch-author1/report.json')['status']=='analysis_only'
    # Existing runtime and calibrated voices must remain exact. This is a
    # read-only comparison against the earlier completed V9 release evidence.
    frozen=data/'baselines/state_dna_controller_v1/delivery1/evidence/ui3/exact_sources'
    previous=load(repo/'research/vehicle_system_workbench_v1_verification.json')
    for name in previous['runtime_C_H_unchanged']:assert sha(repo/name)==sha(frozen/name),name
    voices=sorted((repo/'voices').rglob('*'));voices=[v for v in voices if v.is_file()]
    assert len(voices)==89
    for path in voices:assert sha(path)==sha(frozen/path.relative_to(repo)),path
    dll=repo/'build-vehicle-source-v9/bin/Release/vsl_source_bridge.dll'
    assert sha(dll)==previous['bridge_sha256']
    assert r['source_free_reimport_PCM_exact'] and r['direct_job_and_workbench_parameters_exact']
    from event_authoring.native import Renderer
    held_profile=r['cases'][1]['profile']['parameters'];assert held_profile['gated']==1
    released,release_report=Renderer(repo).render(held_profile,'crank',dict(seconds=.95,hold_seconds=.35))
    assert np.count_nonzero(released[:16800])>0 and np.count_nonzero(released[18000:])==0
    release_file=a.output.with_suffix('.release.wav');assert not release_file.exists()
    sf.write(release_file,released,48000,subtype='FLOAT')
    result=dict(schema='vsl.B-startup-independent-audit/1',result='passed',timeline_cases=timeline_rows,
        raw_audio_and_monitor_exact=True,video_and_frames_hash_verified=True,
        contrasts=contrasts,independent_numpy_fft_max_absolute_power_error=max_error,
        temporal=shape,held_t90_error_max_seconds=max(held),ungated_t90_error_min_seconds=min(old),
        all_four_seed_six_band_errors_below_3db=True,catch_refusal_preserved=True,
        scipy_float32_vs_numpy_float64_power_rounding_bound=8*float(np.finfo(np.float32).eps),
        runtime_C_H_unchanged=len(previous['runtime_C_H_unchanged']),voices_unchanged=len(voices),
        source_bridge_unchanged=sha(dll),timbre_accepted=False,goal_complete=False)
    result['actual_C_release_check']=dict(hold_seconds=.35,silent_from_seconds=.375,
        render=release_report,file=str(release_file),sha256=sha(release_file))
    save(a.output,result);print(dict(result='passed',timeline_frames=sum(v['frames'] for v in timeline_rows),
        max_held_t90_error=max(held),max_power_error=max_error),flush=True)


if __name__=='__main__':main()
