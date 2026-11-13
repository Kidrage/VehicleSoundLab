"""Reuse one compiler/renderer for separate fixed low-rev recording contexts."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read,sha
from fixed_source_v1 import profile,voice
from idle_texture_v2 import spectral,dynamics
from idle_texture_v2.observation import stereo
from idle_modal_v1 import modal

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},contexts=[])
try:
    plan=load(repo/'research/fixed_source_profiles_v1_plan.json')
    recipe=load(repo/'research/idle_texture_v2_recipe.json');mp=load(repo/'research/idle_modal_v1_plan.json')
    paths=[Path(__file__),repo/'research/fixed_source_profiles_v1_plan.json',
        repo/'research/idle_texture_v2_recipe.json',repo/'research/idle_modal_v1_plan.json',
        *sorted((repo/'tools/fixed_source_v1').glob('*.py')),
        *sorted((repo/'tools/idle_texture_v2').glob('*.py')),repo/'tools/idle_modal_v1/modal.py',
        repo/'tools/idle_material_v1/features.py',repo/'tools/drive_evidence_v1/sources.py',repo/'tools/sustain_osc_v1/oracle.py']
    for path in paths:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    r['controls']=dict(renderer=voice.controls(),modal=modal.controls(mp),spectral=spectral.controls(),
        dynamics=dynamics.controls(recipe))
    print(json.dumps(dict(stage='controls_passed')),flush=True)
    frames=recipe['seconds']*48000
    for item in plan['sources']:
        folder=a.out/item['id'];folder.mkdir()
        audio,provenance=read(a.workspace,item['id'],item['use'])
        start=provenance['seconds'][0]
        lo,hi=[round((t-start)*48000) for t in item['train_seconds']]
        train=audio[lo:hi];preserved=None
        if item['id']=='F2_tailpipe':preserved=load(a.workspace/'references/analysis/idle_texture_v2/trial1/profile.json')['modal']
        model,evidence=profile.compile_profile(train,recipe,mp,frames,preserved_modal=preserved)
        save(folder/'profile.json',dict(model,source=provenance,training_seconds=item['train_seconds']))
        save(folder/'fit_evidence.json',evidence)
        sf.write(folder/'training.wav',train,48000,subtype='FLOAT')
        context=dict(id=item['id'],description=item['description'],training_seconds=item['train_seconds'],
            holdout_seconds=item['holdout_seconds'],modes=len(model['modal']['frequencies_hz']),
            profile_sha256=sha(folder/'profile.json'),source_stereo=stereo(train,dict(recipe,bands_hz=recipe['energy_bands_hz'])),seeds=[])
        for seed in recipe['seeds']:
            for name,amount in [('fine',0.),('dynamic',1.)]:
                mix,main,texture=voice.render(model,frames,seed,amount=amount)
                assert np.isfinite(mix).all()
                sf.write(folder/f'{name}_{seed}.wav',mix,48000,subtype='FLOAT')
                actual,_=sf.read(folder/f'{name}_{seed}.wav',always_2d=True)
                row=dict(seed=seed,method=name,peak=float(abs(mix).max()),
                    training_band_error_db=(10*np.log10(profile.band_power(mix,recipe)/
                        np.asarray(evidence['training_power_LR']))).tolist(),sha256=sha(folder/f'{name}_{seed}.wav'))
                if preserved is not None:
                    old,_=sf.read(a.workspace/f'references/analysis/idle_texture_v2/trial1/{name}_{seed}.wav',always_2d=True)
                    row['frozen_F2_samples_exact']=bool(np.array_equal(actual,old));assert row['frozen_F2_samples_exact']
                context['seeds'].append(row)
            print(json.dumps(dict(stage='rendered',context=item['id'],seed=seed,modes=context['modes'])),flush=True)
        # All candidate parameters/seeds saved before holdout measurement.
        lo,hi=[round((t-start)*48000) for t in item['holdout_seconds']]
        held=audio[lo:hi];sf.write(folder/'holdout.wav',held,48000,subtype='FLOAT')
        hp=profile.band_power(held,recipe)
        for row in context['seeds']:
            y,_=sf.read(folder/f"{row['method']}_{row['seed']}.wav",always_2d=True)
            row['holdout_band_error_db']=(10*np.log10(profile.band_power(y,recipe)/hp)).tolist()
        context['holdout_power_LR']=hp.tolist();r['contexts'].append(context)
    r.update(result='two_separate_context_profiles_same_autonomous_kernel_pending_listening',
        runtime_changed=False,shared_phase_qualified=False,measured_RPM=False,
        limits=['F2 LP-610 and A Performante remain distinct recording contexts; not two accepted full-range cars.',
            'A low-rev recording is not verified warm idle; short same-recording holdout is not independent validation.',
            'Residual stereo is common excitation plus band gains, not full complex stereo covariance.',
            'Independent modal phases may drift/beat; amplitude proxy is not combustion-synchronous.',
            'Ratio changes OSC pitch only; fixed-Hz resonators remain fixed. No RPM/load calibration or C adoption.'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
