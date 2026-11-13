"""Train-only fine spectral texture and fresh amplitude-statistics comparison."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import read,sha
from idle_material_v1.features import observe
from idle_modal_v1.modal import render
from idle_texture_v2 import spectral,dynamics
from sustain_osc_v1.oracle import Gaussian

def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def power(x,plan):return np.asarray(observe(x,plan['energy_bands_hz'])['mean_power'])

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',exact_sources={},seeds=[])
try:
    plan=json.loads((repo/'research/idle_texture_v2_recipe.json').read_text(encoding='utf-8'))
    for path in [Path(__file__),repo/'research/idle_texture_v2_recipe.json',
        *sorted((repo/'tools/idle_texture_v2').glob('*.py')),repo/'tools/idle_modal_v1/modal.py',
        repo/'tools/idle_material_v1/features.py',repo/'tools/drive_evidence_v1/sources.py',
        repo/'tools/sustain_osc_v1/oracle.py']:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['exact_sources'][path.relative_to(repo).as_posix()]=sha(path)
    r['controls']=dict(spectral=spectral.controls(),dynamics=dynamics.controls(plan))
    print(json.dumps(dict(stage='known_controls',**r['controls'])),flush=True)
    source,provenance=read(a.workspace,'F2_tailpipe','recording_power');train=source[:144000]
    parent=a.workspace/'references/analysis/idle_modal_v1/trial4'
    original=json.loads((parent/'profile.json').read_text(encoding='utf-8'))
    frames=plan['seconds']*48000;main=render(original['modal'],frames,48000)
    # Stored FLOAT baseline may differ from the original double signal by float rounding only.
    baseline,_=sf.read(parent/'modal_only.wav',always_2d=True)
    assert abs(main-baseline).max()<2e-8
    target=power(train,plan);mp=power(main,plan)
    kernels,budget=spectral.fit(train,target,mp,plan)
    envelope=dynamics.fit(train,plan);evidence=envelope.pop('evidence')
    save(a.out/'envelope_observations.json',evidence)
    profile=dict(schema='vsl.idle-fine-texture/2',sample_rate=48000,modal=original['modal'],
        kernels=kernels,envelope=envelope,training_seconds=[6,9],recorded_trajectory=False,room=False,
        source=provenance,RPM=None,scope='Independent fixed-idle study; no common-clock qualification')
    save(a.out/'profile.json',profile)
    for seed in plan['seeds']:
        state,normal=dynamics.states(envelope,frames,seed)
        g=dynamics.gains(envelope,state,frames)
        static=np.zeros((frames,2));animated=static.copy();streams=[]
        for i,model in enumerate(kernels):
            rng=Gaussian(seed^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1)))
            n=frames+plan['warmup_frames']
            noise=np.fromiter((rng.next() for _ in range(n)),dtype=float,count=n)
            y=signal.oaconvolve(noise,np.asarray(model['taps']))[plan['warmup_frames']:n]*model['gain']
            stereo=y[:,None]*np.array([[1.,model['right_over_left']]])
            static+=stereo;animated+=stereo*g[:,i,None];streams.append(y)
        np.savez_compressed(a.out/f'states_{seed}.npz',states=state,normal=normal)
        for name,texture in [('fine',static),('dynamic',animated)]:
            mix=main+texture;assert np.isfinite(mix).all() and abs(mix).max()<1
            sf.write(a.out/f'{name}_{seed}.wav',mix,48000,subtype='FLOAT')
            sf.write(a.out/f'{name}_detail_{seed}.wav',texture,48000,subtype='FLOAT')
            r['seeds'].append(dict(seed=seed,method=name,peak=float(abs(mix).max()),
                training_band_error_db=(10*np.log10(power(mix,plan)/target)).tolist(),
                envelope_gain_range=[float(g.min()),float(g.max())],sha256=sha(a.out/f'{name}_{seed}.wav')))
        print(json.dumps(dict(stage='rendered',seed=seed,alpha=envelope['alpha'])),flush=True)
    # First holdout analysis only after the immutable candidate parameters and all seeds are saved.
    held=power(source[144000:],plan)
    for row in r['seeds']:
        y,_=sf.read(a.out/f"{row['method']}_{row['seed']}.wav",always_2d=True)
        row['holdout_band_error_db']=(10*np.log10(power(y,plan)/held)).tolist()
    r.update(result='isolated_fine_and_dynamic_idle_candidates_pending_listening',plan=plan,provenance=provenance,
        original_profile_sha256=sha(parent/'profile.json'),profile_sha256=sha(a.out/'profile.json'),
        budget=budget,training_power_LR=target.tolist(),holdout_power_LR=held.tolist(),
        envelope_alpha=envelope['alpha'],envelope_raw_alpha=envelope['raw_alpha'],
        old_OSC_parameters_exact=original['modal']==profile['modal'],runtime_changed=False,
        limitations=['Same recording holdout, not an independent take.',
            'F2 is effectively mono over most useful bands; no artificial stereo widening.',
            'Spectral texture and slow band-energy proxy retain microphone/wind contamination.',
            'New amplitude statistics are autonomous and not engine-cycle synchronous.',
            'Fixed independent OSC modes can still beat; no measured RPM or load mapping.',
            '8192tap Python rendering is not real-time C qualification; no default promotion.'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],candidates=len(r['seeds']))),flush=True)
