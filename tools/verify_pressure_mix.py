"""Independent event sums, exact nonuniform Fourier controls, immutable evidence."""
import json
import shutil
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf
from pressure_mix_response import bandlimited,lagrange_weights,NODES

OUT=ROOT/'renders/pressure_mix_v1'
SNAP=ROOT/'baselines/pressure_mix_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def direct_samples(events,meta,samples,indices):
    sr=meta['sample_rate'];d=meta['right_delay_seconds']*sr;integer=int(d);fraction=d-integer
    y=np.zeros((len(indices),2))
    for bank in range(2):
        ev=events[events['bank']==bank];event_time=ev['frame']/sr-ev['elapsed']
        offsets=[(0,1)] if bank==0 else [(integer,1-fraction),(integer+1,fraction)]
        for offset,weight in offsets:
            ages=(indices[:,None]-offset)/sr-event_time[None,:]
            active=ages>=0;ages=np.maximum(ages,0);raw=np.zeros(ages.shape)
            for i,mode in enumerate(meta['modes']):
                amplitude=ev['gain']*mode['weight']*(1+ev['shape']*(i-1)*meta['shape_spread'])
                raw+=amplitude[None,:]*np.exp(-ages/mode['decay_seconds'])*np.sin(2*np.pi*mode['hz']*ages)
            y[:,bank]+=weight*np.sum(raw*active,axis=1)
    return y*samples[indices,2,None]


def controls():
    # Exact nonuniform Fourier sum: independently evaluates every base-rate bin
    # for three fractional events, without gridding or a sampled recurrence.
    sr=48000;n=4800;period=n+2*sr;padding=sr
    meta=dict(sample_rate=sr,frames=n,right_delay_seconds=.00038,shape_spread=.35,
        modes=[dict(hz=1050,decay_seconds=.0014,weight=.85),
               dict(hz=2900,decay_seconds=.00065,weight=.52),dict(hz=6100,decay_seconds=.00032,weight=.24)])
    events=np.array([(203,0,.02,.13,.3/sr),(2222,1,.018,-.2,.7/sr),(3999,0,.023,.01,.43/sr)],
        dtype=[('frame','f8'),('bank','f8'),('gain','f8'),('shape','f8'),('elapsed','f8')])
    gain=.4+.1*np.sin(np.arange(n)*2*np.pi/n)
    observed,params=bandlimited(events,meta,gain,period,16)
    f=np.arange(period//2+1)*sr/period;w=2*np.pi*f;spec=np.zeros((len(f),2),complex)
    for event in events:
        t=(event['frame']+padding)/sr-event['elapsed'];h=np.zeros(len(f),complex)
        for i,mode in enumerate(meta['modes']):
            alpha=1/mode['decay_seconds'];omega=2*np.pi*mode['hz']
            # Algebraically independent positive/negative complex-pole form.
            transfer=(1/(alpha+1j*(w-omega))-1/(alpha+1j*(w+omega)))/(2j)
            h+=mode['weight']*(1+event['shape']*(i-1)*meta['shape_spread'])*transfer
        spec[:,int(event['bank'])]+=event['gain']*h*np.exp(-1j*w*t)
    raw=np.fft.irfft(spec,n=period,axis=0)[padding:padding+n]*sr
    exact=raw.copy();delay=sr*meta['right_delay_seconds'];integer=int(delay);fraction=delay-integer
    exact[:,1]=0;exact[integer:,1]=(1-fraction)*raw[:-integer,1];exact[integer+1:,1]+=fraction*raw[:-integer-1,1]
    exact*=gain[:,None]
    error=float(abs(observed-exact).max());assert error<2e-12,error
    # Verify local interpolation error against the analytic remainder at every
    # fractional position and a grid of frequencies. Avoid large global phases.
    maximum=0.;max_fraction_of_bound=0.
    fractions=np.linspace(0,1,129)[1:-1];weights=lagrange_weights(fractions)
    for theta in np.linspace(0,np.pi/16,257)[1:]:
        actual=weights@np.exp(-1j*theta*NODES);expected=np.exp(-1j*theta*fractions)
        error_vector=abs(actual-expected)
        bound=np.sqrt(2)*theta**8/40320*abs(np.prod(fractions[:,None]-NODES,axis=1))
        # 5e-15 accounts for rounding when the theoretical bound is sub-ULP.
        assert np.all(error_vector<=bound+5e-15)
        maximum=max(maximum,float(error_vector.max()))
        max_fraction_of_bound=max(max_fraction_of_bound,float(np.max(error_vector/(bound+5e-15))))
    return dict(exact_nonuniform_Fourier_control_max_sample_error=error,grid_parameters=params,
        local_interpolation_max_complex_error=maximum,
        local_interpolation_error_to_bound_plus_rounding_max=max_fraction_of_bound,
        scope='Controls verify continuous transfer,amplitude/phase,FFT scaling,fractional event deposition,bank delay and gain. Finite-padding convergence is separately empirical.')


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():raise SystemExit('Preserve completed pressure_mix_v1.')
    result=read(OUT/'results.json')
    for name,digest in result['sources'].items():assert sha(ROOT/name)==digest,name
    for name,digest in result['files'].items():assert sha(OUT/name)==digest,name
    checks=controls();direct={};metrics={}
    for name,row in result['runs'].items():
        folder=OUT/name;meta=row['meta'];n=meta['frames'];sr=meta['sample_rate']
        events=np.genfromtxt(folder/'observed_events.csv',delimiter=',',names=True)
        samples=np.fromfile(folder/'observed_samples.f64',dtype='<f8').reshape(n,3)
        indices=np.unique(np.r_[np.linspace(0,n-1,513).astype(int),
            events['frame'][::max(1,len(events)//128)].astype(int)])
        exact=direct_samples(events,meta,samples,indices)
        error=float(abs(exact-samples[indices,:2]).max());assert error<2e-12,(name,error)
        a,_=sf.read(folder/'native.wav',always_2d=True);b,_=sf.read(folder/'replaced.wav',always_2d=True)
        observed=[]
        for start in [0,n-sr]:
            reference=a[start:]-a[start:].mean(axis=0);delta=b[start:]-a[start:];delta-=delta.mean(axis=0)
            ratio=10*np.log10(np.mean(delta*delta,axis=0)/np.mean(reference*reference,axis=0))
            observed.append(ratio.tolist())
        assert np.max(abs(np.array(observed[0])-row['full_mix']['bands']['AC']['difference_over_original_db']))<1e-9
        native_hash=read(folder/'native_meta.json');observed_hash=read(folder/'observed_meta.json')
        assert native_hash['take_audio_hash']==native_hash['render_audio_hash']==observed_hash['render_audio_hash']
        direct[name]=dict(samples_tested=len(indices),finite_event_sum_max_error=error)
        metrics[name]=dict(full_clip_AC_difference_over_original_db=observed[0],
            final_one_second_AC_difference_over_original_db=observed[1],
            pressure_added_full_clip_rms=np.sqrt(np.mean(samples[:,:2]**2,axis=0)).tolist(),
            native_full_clip_rms=np.sqrt(np.mean(a*a,axis=0)).tolist(),
            pressure_added_DC=samples[:,:2].mean(axis=0).tolist(),
            limits='Pressure source RMS is pre-scene; full mix RMS is post-scene/master. Their ratio is not a routed source contribution.')
    native=read(ROOT/'baselines/v0.17.0/manifest.json');preserved={}
    for item in native['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','AGENTS.md','build.ps1','Launch.cmd','Launch-character.cmd','Launch-current.cmd']:
            assert sha(ROOT/name)==item['sha256'],name;preserved[name]=item['sha256']
    binaries=read(ROOT/'renders/v0.17.0/verification.json')['binaries']
    for name,digest in binaries.items():assert sha(ROOT/'build-v017/Release'/name)==digest,name
    history={p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))};assert len(history)==30
    names=set(result['sources'])|{'tools/verify_pressure_mix.py','tools/runtime_review.py',
        'research/压力层完整混音核查V1.md','research/goal_progress_pressure_mix_v1.json','README.md'}
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'build-experiment-pressure-mix').glob('observed_*.c'))
    verification=dict(result='pass',study='pressure_mix_v1',analytic_controls=checks,
        independent_finite_event_sums=direct,independent_metrics=metrics,
        native_contracts_unchanged=preserved,native_binaries_unchanged=binaries,
        previous_manifest_identities=history,sources={name:sha(ROOT/name) for name in sorted(names)},
        artifacts={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},
        scope='Actual event-driven pressure-only Nyquist-projection counterfactual. Native engine unchanged; no causal implementation or subjective acceptance.')
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2,allow_nan=False),encoding='utf-8')
    SNAP.mkdir()
    for name in sorted(names):
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            target=SNAP/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    files=[dict(path=p.relative_to(SNAP).as_posix(),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest=dict(study='pressure_mix_v1',base_runtime='0.17.0 unchanged',files=files,
        status='Frozen offline pressure-only counterfactual with actual native takes. No native or voicing promotion.',
        storage='Native headers referenced through immutable baselines/v0.17.0; linked library,scheduler copies,probe,analysis,inputs,raw outputs and verification retained.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    assert all(sha(SNAP/item['path'])==item['sha256'] for item in files)
    complete=dict(result='pass',snapshot_files=len(files),manifest_sha256=sha(SNAP/'manifest.json'),
        verification_sha256=sha(OUT/'verification.json'),native_contracts_unchanged=len(preserved),
        maximum_direct_event_sum_error=max(x['finite_event_sum_max_error'] for x in direct.values()),
        maximum_exact_Fourier_control_error=checks['exact_nonuniform_Fourier_control_max_sample_error'])
    (OUT/'freeze_complete.json').write_text(json.dumps(complete,indent=2),encoding='utf-8')
    print(json.dumps(complete,indent=2))


if __name__=='__main__':main()
