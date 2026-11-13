"""Independent sample/periodogram checks of the native-idle prototype."""
import argparse,json,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__); p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True); a=p.parse_args(); repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def powers(x,bands):
    rows=[]
    for j in range(0,len(x)-23999,24000):
        f,p=signal.periodogram(x[j:j+24000],fs=48000,window='hann',detrend=False,axis=0)
        rows.append([p[(f>=lo)&(f<hi)].sum(axis=0)*2 for lo,hi in bands])
    return np.mean(rows,axis=0)

a.out.mkdir(parents=True,exist_ok=False); r=dict(result='running',checks={})
try:
    parent=a.workspace/'references/analysis/idle_modal_v1/trial4'; report=load(parent/'report.json')
    assert report['result']=='experimental_native_idle_candidate_rendered_not_listening_accepted'
    plan=report['plan']; bands=plan['bands_hz']; profile=load(parent/'profile.json')
    assert sha(parent/'profile.json')==report['profile_sha256']
    for name,digest in report['sources'].items(): assert sha(repo/name)==sha(parent/'exact_sources'/name)==digest
    dest=a.out/'exact_sources/tools'; dest.mkdir(parents=True)
    shutil.copy2(__file__,dest/Path(__file__).name)
    r['sources']={Path(__file__).relative_to(repo).as_posix():sha(Path(__file__))}
    r['parent_report_sha256']=sha(parent/'report.json')
    catalog=load(a.workspace/'references/segments_v1.json'); src=catalog['sources']['F2']
    assert sha(a.workspace/src['master'])==report['provenance']['master_sha256']
    with sf.SoundFile(a.workspace/src['master']) as stream:
        stream.seek(6*48000); raw=stream.read(6*48000,always_2d=True)
    train,_=sf.read(parent/'F2_training.wav',always_2d=True); holdout,_=sf.read(parent/'F2_holdout.wav',always_2d=True)
    assert np.array_equal(train,raw[:144000]) and np.array_equal(holdout,raw[144000:])
    target,held=powers(train,bands),powers(holdout,bands)
    assert np.max(abs(target-np.array(report['training_power_LR'])))<1e-15
    assert np.max(abs(held-np.array(report['holdout_power_LR'])))<1e-15
    main,rate=sf.read(parent/'modal_only.wav',always_2d=True); assert rate==48000
    m=profile['modal']; indices=np.array([0,1,191,1023,18001,24000,144000,287999,575999])
    oracle=np.array([[sum(amp[c]*math.cos(2*math.pi*f*int(n)/48000+phase[c])
        for f,amp,phase in zip(m['frequencies_hz'],m['amplitude_LR'],m['initial_phase_LR']))
        for c in range(2)] for n in indices])
    error=float(abs(oracle-main[indices]).max()); assert error<2e-8
    r['checks']['scalar_modal_FS_error']=error
    max_training=max_holdout=0.; max_sum=0.
    for item in report['seeds']:
        seed=item['seed']; mix,rate=sf.read(parent/f'mix_{seed}.wav',always_2d=True)
        texture,_=sf.read(parent/f'detail_{seed}.wav',always_2d=True)
        assert len(mix)==576000 and np.isfinite(mix).all() and rate==48000
        assert sha(parent/f'mix_{seed}.wav')==item['mix_sha256']
        err=float(abs(mix-main-texture).max()); assert err<4e-8; max_sum=max(max_sum,err)
        measured=powers(mix,bands)
        tr=10*np.log10(measured/target); ho=10*np.log10(measured/held)
        assert np.max(abs(tr-np.array(item['band_error_training_db'])))<2e-7
        assert np.max(abs(ho-np.array(item['band_error_holdout_db'])))<2e-7
        max_training=max(max_training,float(abs(tr).max())); max_holdout=max(max_holdout,float(abs(ho).max()))
        assert abs(mix).max()<.95
    # Verify stationary AR scale independently via a polynomial response.
    n=plan['spectral_grid_frames']; w=2*np.pi*np.arange(n)/n; ar_errors=[]
    for model in profile['resonators']:
        coeff=np.array(model['a'])
        denominator=sum(v*np.exp(-1j*w*k) for k,v in enumerate(coeff))
        variance=np.mean(model['sigma']**2/abs(denominator)**2)
        assert abs(variance-1)<1e-9
        ar_errors.append(float(abs(variance-1)))
        assert max(abs(np.roots(coeff)))<plan['maximum_pole_radius']
    # No audio/complex coefficient trajectory is serialized into the voice.
    assert not profile['recorded_trajectory'] and profile['engine_clock'] is None and not profile['room']
    assert 'evidence' not in m and 'local_frequency_paths_hz' not in json.dumps(profile)
    assert sha(parent/'modal_observations.json')==report['observation_evidence_sha256']
    assert len(m['initial_phase_LR'])==len(m['frequencies_hz'])==13
    r.update(result='native_sources_modal_samples_three_seeds_and_AR_scale_independently_checked',
        checks=dict(r['checks'],source_slices_exact=True,all3_seeds_kept=True,
            float_stem_sum_maximum_error=max_sum,maximum_training_band_error_db=max_training,
            maximum_holdout_band_error_db=max_holdout,AR_unit_variance_maximum_error=max(ar_errors)),
        listening_accepted=False,common_phase_qualified=False,runtime_changed=False,profile_has_no_observation_timeline=True,
        limits='This verifies representation and reported spectra, not mechanical naturalness or long-term phase locking.')
except Exception as exc: r.update(result='failed',error=repr(exc)); raise
finally: (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(r,ensure_ascii=False),flush=True)
