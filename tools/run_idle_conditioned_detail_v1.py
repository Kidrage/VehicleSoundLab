"""Render all fixed-prior amplitude candidates only after observation gate passes."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_conditioned_detail_v1.voice import render
from idle_material_v1.features import observe

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',renders=[],sources={})
try:
    parent=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe'
    profile=load(parent/'profile.json');observed=load(a.input/'report.json');assert observed['candidate_gate']
    model=load(a.input/'model.json');assert model['positive'] and not model['recorded_timeline']
    for path in [Path(__file__),repo/'research/idle_conditioned_detail_v1_plan.json',repo/'tools/fixed_source_v1/voice.py',
        repo/'tools/idle_modal_v1/modal.py',repo/'tools/idle_texture_v2/dynamics.py',repo/'tools/sustain_osc_v1/oracle.py',
        repo/'tools/idle_material_v1/features.py',repo/'tools/research_archive_v1.py',*sorted((repo/'tools/idle_conditioned_detail_v1').glob('*.py'))]:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    save(a.out/'model.json',model)
    bands=load(repo/'research/idle_texture_v2_recipe.json')['energy_bands_hz']
    for seed in [149921,277139,381611]:
        for amount in [0.,.5,1.]:
            mix,main,detail,gains=render(profile,model,576000,seed,amount)
            assert np.isfinite(mix).all() and abs(mix).max()<1
            label=f'{round(amount*100):03d}_{seed}'
            for bus,data in [('mix',mix),('detail',detail)]:sf.write(a.out/f'{bus}_{label}.wav',data,48000,subtype='FLOAT')
            if amount==0:
                old=sf.read(a.workspace/f'baselines/idle_texture_v2/evidence/trial1/fine_{seed}.wav',always_2d=True)[0]
                assert np.array_equal(old,mix.astype(np.float32).astype(float))
                sf.write(a.out/f'core_{seed}.wav',main,48000,subtype='FLOAT')
            row=dict(seed=seed,amount=amount,peak=float(abs(mix).max()),
                gain_min=gains.min(axis=0).tolist(),gain_max=gains.max(axis=0).tolist(),
                mean_gain_squared=np.mean(gains*gains,axis=0).tolist(),band_power=observe(mix,bands)['mean_power'],
                mix_sha256=sha(a.out/f'mix_{label}.wav'),detail_sha256=sha(a.out/f'detail_{label}.wav'))
            r['renders'].append(row);print(dict(seed=seed,amount=amount,peak=row['peak']),flush=True)
    r.update(result='conditioned_detail_candidates_pending_listening',input_report_sha256=sha(a.input/'report.json'),
        model_sha256=sha(a.out/'model.json'),parent_profile_sha256=sha(parent/'profile.json'),
        core_unchanged=True,zero_FLOAT_exact=True,all_seeds_retained=True,room=False,
        runtime_changed=False,physical_source_identified=False,engine_phase_qualification=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
