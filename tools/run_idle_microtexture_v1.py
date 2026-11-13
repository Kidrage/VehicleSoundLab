"""Render all declared fast-detail candidates, freeze parameters before check data."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_microtexture_v1.profile import compile_model
from idle_microtexture_v1.voice import render
from idle_material_v1.features import observe
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},renders=[])
try:
    recipe_path=repo/'research/idle_microtexture_v1_recipe.json';recipe=load(recipe_path)
    sources=[Path(__file__),recipe_path,repo/'tools/research_archive_v1.py',repo/'tools/fixed_source_v1/voice.py',
        repo/'tools/modal_texture_v1/envelope.py',repo/'tools/sustain_osc_v1/oracle.py',repo/'tools/idle_modal_v1/modal.py',
        repo/'tools/idle_texture_v2/dynamics.py',repo/'tools/idle_material_v1/features.py',*sorted((repo/'tools/idle_microtexture_v1').glob('*.py'))]
    for path in sources:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    observation=a.workspace/recipe['observation'];assert load(observation/'report.json')['result']=='fixed_idle_short_time_concentration_observed'
    indices=recipe['kernel_indices'];key='energy_'+str(recipe['energy_window_frames'])
    source=np.load(observation/'F2_train.npz')[key][:,indices]
    controls=[np.load(observation/f'F2_train_phase_{seed}.npz')[key][:,indices] for seed in recipe['seeds']]
    # Known shape preserving covariance subtraction and explicit negative-excess rejection.
    known=np.array([[1.,2.],[2.,1.],[3.,2.],[2.,3.],[1.,1.],[3.,3.]])
    _,ev=compile_model(known,[np.ones_like(known)],480);assert min(ev['excess_eigenvalues'])>0
    try:compile_model(np.ones_like(known),[known],480)
    except ValueError:pass
    else:raise AssertionError('Negative excess accepted')
    model,evidence=compile_model(source,controls,480)
    parent=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1/F2_tailpipe'
    profile=load(parent/'profile.json');assert sha(parent/'profile.json')==sha(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    save(a.out/'profile.json',dict(envelope=model,kernel_indices=indices,recorded_trajectory=False,room=False))
    save(a.out/'observations.json',evidence)
    frames=recipe['seconds']*48000;bands=load(repo/'research/idle_texture_v2_recipe.json')['energy_bands_hz']
    for seed in recipe['seeds']:
        for amount in recipe['amounts']:
            mix,main,detail,state,normal=render(profile,model,indices,frames,seed,amount)
            assert np.isfinite(mix).all() and abs(mix).max()<1
            label=f'{round(amount*100):03d}_{seed}'
            for bus,data in [('mix',mix),('detail',detail)]:sf.write(a.out/f'{bus}_{label}.wav',data,48000,subtype='FLOAT')
            if amount==0:
                previous,_=sf.read(a.workspace/f'references/analysis/idle_texture_v2/trial1/fine_{seed}.wav',always_2d=True)
                assert np.array_equal(previous,mix.astype(np.float32).astype(float))
                sf.write(a.out/f'core_{seed}.wav',main,48000,subtype='FLOAT')
                np.savez_compressed(a.out/f'states_{seed}.npz',state=state,normal=normal)
            power=np.array(observe(mix,bands)['mean_power'])
            r['renders'].append(dict(seed=seed,amount=amount,peak=float(abs(mix).max()),band_power=power.tolist(),
                mix_sha256=sha(a.out/f'mix_{label}.wav'),detail_sha256=sha(a.out/f'detail_{label}.wav')))
            print(dict(seed=seed,amount=amount,peak=float(abs(mix).max())),flush=True)
    # Rendering and saved profile are complete before reporting the old check.
    check=np.load(observation/'F2_check.npz')['audio'];train=np.load(observation/'F2_train.npz')['audio']
    targets={name:np.array(observe(x,bands)['mean_power']) for name,x in [('train',train),('check',check)]}
    for row in r['renders']:
        row['band_error_db']={name:(10*np.log10(np.array(row['band_power'])/target)).tolist() for name,target in targets.items()}
    r.update(result='fast_detail_candidates_pending_listening',recipe=recipe,evidence=evidence,
        parent_profile_sha256=sha(parent/'profile.json'),observation_report_sha256=sha(observation/'report.json'),
        zero_FLOAT_exact=True,all_seeds_retained=True,core_frequency_phase_unchanged=True,
        training_only=True,physical_combustion_or_engine_phase_identified=False,runtime_changed=False,room=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
