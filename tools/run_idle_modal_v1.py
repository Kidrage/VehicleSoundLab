"""Native F2 fixed-idle prototype: independent modes plus resonant detail."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
p.add_argument('--compare-audio',type=Path)
a=p.parse_args(); repo=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(a.workspace/'tools'/x) for x in ('ipm_deps','qp_deps','python_deps')]
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read,sha
from idle_material_v1.features import observe
from idle_modal_v1 import modal,detail


def save(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def power(x,bands): return np.asarray(observe(x,bands)['mean_power'])


a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},seeds=[],runtime_changed=False,shared_phase_DNA=False)
try:
    plan=json.loads((repo/'research/idle_modal_v1_plan.json').read_text(encoding='utf-8'))
    for path in [Path(__file__),repo/'research/idle_modal_v1_plan.json',
        *sorted((repo/'tools/idle_modal_v1').glob('*.py')),repo/'tools/idle_material_v1/features.py',
        repo/'tools/drive_evidence_v1/sources.py',repo/'tools/sustain_osc_v1/oracle.py',
        *sorted((repo/'tools/resonant_detail_v1').glob('*.py'))]:
        dest=a.out/'exact_sources'/path.relative_to(repo); dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest); r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    r['controls']=modal.controls(plan)
    print(json.dumps(dict(stage='known_controls',**r['controls'])),flush=True)
    x,provenance=read(a.workspace,plan['source'],'recording_power')
    assert len(x)==6*48000
    train,holdout=x[:144000],x[144000:]
    bands=plan['bands_hz']; target=power(train,bands); held=power(holdout,bands)
    model=modal.fit(train,48000,plan)
    # Observation trajectories belong in evidence, never in the autonomous
    # voice parameter file, even though render() did not consume them.
    fit_evidence=model.pop('evidence')
    save(a.out/'modal_observations.json',fit_evidence)
    print(json.dumps(dict(stage='modal_fit',modes=len(model['frequencies_hz']),frequencies=model['frequencies_hz'])),flush=True)
    frames=round(plan['seconds']*48000)
    main=modal.render(model,frames,48000)
    initial=power(main,bands)
    ceiling=plan['modal_power_ceiling_fraction']
    scale=min(1.,float(np.sqrt(np.min(ceiling*target/np.maximum(initial,1e-30)))))
    model['amplitude_LR']=(np.asarray(model['amplitude_LR'])*scale).tolist()
    main*=scale; mainpower=power(main,bands)
    models,budget=detail.fit(train,target,mainpower,plan)
    profile=dict(schema='vsl.independent-idle-modal/1',sample_rate=48000,modal=model,
        resonators=models,engine_RPM=None,engine_clock=None,source=provenance,
        source_training_seconds=plan['training_seconds'],recorded_trajectory=False,
        room=False,scope='Experimental independent acoustic modes; not shared-phase DNA or a driving calibration')
    save(a.out/'profile.json',profile)
    sf.write(a.out/'F2_training.wav',train,48000,subtype='FLOAT')
    sf.write(a.out/'F2_holdout.wav',holdout,48000,subtype='FLOAT')
    sf.write(a.out/'modal_only.wav',main,48000,subtype='FLOAT')
    # Every declared seed is kept, no chosen best render or seed-specific gain.
    for seed in plan['seeds']:
        texture=detail.render(models,frames,seed,plan)
        mix=main+texture; measured=power(mix,bands)
        assert np.isfinite(mix).all()
        sf.write(a.out/f'detail_{seed}.wav',texture,48000,subtype='FLOAT')
        sf.write(a.out/f'mix_{seed}.wav',mix,48000,subtype='FLOAT')
        r['seeds'].append(dict(seed=seed,peak=float(abs(mix).max()),
            band_error_training_db=(10*np.log10(measured/target)).tolist(),
            band_error_holdout_db=(10*np.log10(measured/held)).tolist(),
            mix_sha256=sha(a.out/f'mix_{seed}.wav')))
        print(json.dumps(dict(stage='rendered',**r['seeds'][-1])),flush=True)
    if a.compare_audio:
        identical={}
        for path in a.out.glob('*.wav'):
            actual,rate_a=sf.read(path,always_2d=True)
            previous,rate_b=sf.read(a.compare_audio/path.name,always_2d=True)
            same=rate_a==rate_b and np.array_equal(actual,previous)
            identical[path.name]=dict(decoded_samples_exact=same,
                container_bytes_equal=sha(path)==sha(a.compare_audio/path.name))
        assert all(item['decoded_samples_exact'] for item in identical.values())
        r['profile_evidence_separation_audio_identity']=identical
    r.update(result='experimental_native_idle_candidate_rendered_not_listening_accepted',
        plan=plan,provenance=provenance,modes=len(model['frequencies_hz']),modal_ceiling_scale=scale,
        training_power_LR=target.tolist(),holdout_power_LR=held.tolist(),modal_power_LR=mainpower.tolist(),
        budget=budget,profile_sha256=sha(a.out/'profile.json'),
        observation_evidence_sha256=sha(a.out/'modal_observations.json'),
        pole_radius_max=max(v['pole_radius'] for v in models),
        limits=['Independent frequencies can beat and do not guarantee engine-synchronous long-term phase.',
            'Mean spectrum and a measured initial relative phase, not reconstructed combustion/RPM/load or real mechanical source separation.',
            'No recorded PCM/timeline in the profile; synthesized details use new innovations and fixed source-fitted resonators.',
            'Near-mono shared residual approximation; wind/microphone-motion contamination may remain.',
            'Only F2 training6..9s fitted;9..12s is held out, same recording, not an independent vehicle validation.',
            'Source fit and this independent-modal prototype do not waive shared-phase extractor qualification.',
            'No current C/voice bank/UI/driver changes or perceptual improvement claim.'])
except Exception as exc:
    r.update(result='failed',error=repr(exc)); raise
finally: save(a.out/'report.json',r)
