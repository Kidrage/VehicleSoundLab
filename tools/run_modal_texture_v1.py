"""Train-only amplitude proxy on the preserved F2 core; retain every seed/amount."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--known',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from modal_texture_v1.analysis import observe,compile_statistics
from modal_texture_v1.voice import render
from modal_texture_v1.envelope import gains
from fixed_source_v1.voice import render as render_fixed
from idle_material_v1.features import observe as power_observe
from research_archive_v1 import load,save,sha


a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},seeds=[],holdout_read=False,
    C_changed=False,phase_modulation=False,frequency_modulation=False,physical_AM_identified=False)
try:
    plan=load(repo/'research/modal_texture_v1_plan.json');known=load(a.known/'report.json')
    assert known['result']=='known_local_model_limits_and_amplitude_proxy_checked' and known['controls_passed']
    files=[Path(__file__),repo/'research/modal_texture_v1_plan.json',repo/'research/idle_texture_v2_recipe.json',repo/'tools/research_archive_v1.py',
        *sorted((repo/'tools/modal_texture_v1').glob('*.py')),
        repo/'tools/fixed_source_v1/voice.py',repo/'tools/idle_modal_v1/modal.py',
        repo/'tools/idle_texture_v2/dynamics.py',repo/'tools/idle_material_v1/features.py',
        repo/'tools/sustain_osc_v1/oracle.py']
    for path in files:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
        if name.as_posix() in known['sources']:assert sha(path)==known['sources'][name.as_posix()]
    parent=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1/F2_tailpipe'
    frozen=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe'
    for name in ['training.wav','profile.json']:assert sha(parent/name)==sha(frozen/name)
    x,rate=sf.read(parent/'training.wav',always_2d=True);assert rate==48000 and len(x)==144000
    base=load(parent/'profile.json');modal=base['modal']
    measured=observe(x,modal['frequencies_hz'],plan)
    envelope,evidence,centered=compile_statistics(measured,plan)
    profile=dict(schema='vsl.modal-texture-study/1',sample_rate=48000,modal=modal,envelope=envelope,
        recorded_trajectory=False,room=False,RPM=None,
        scope='Amplitude-only independent fixed-context study, not physical AM or common-phase DNA')
    save(a.out/'profile.json',profile);save(a.out/'observations.json',evidence)
    np.savez_compressed(a.out/'source_observations.npz',coefficients=measured['coefficients'],
        DC=measured['DC'],starts=measured['starts'],centered_log_magnitude=centered,
        singular_values=measured['singular_values'])
    print(json.dumps(dict(stage='source_statistics',condition=measured['condition_number'],**evidence)),flush=True)
    bands=load(repo/'research/idle_texture_v2_recipe.json')['energy_bands_hz']
    target=np.asarray(power_observe(x,bands)['mean_power']);frames=plan['seconds']*48000
    for seed in plan['seeds']:
        old_mix,old_main,detail=render_fixed(base,frames,seed,amount=0)
        baseline=a.workspace/f'references/analysis/idle_texture_v2/trial1/fine_{seed}.wav'
        assert sha(baseline)==sha(a.workspace/f'baselines/idle_texture_v2/evidence/trial1/fine_{seed}.wav')
        expected,_=sf.read(baseline,always_2d=True)
        assert np.array_equal(old_mix.astype(np.float32).astype(float),expected)
        sf.write(a.out/f'fixed_detail_{seed}.wav',detail,48000,subtype='FLOAT')
        for amount in plan['amounts']:
            main,state,normal=render(modal,envelope,frames,48000,seed,amount)
            if amount==0:assert np.array_equal(main,old_main)
            mix=main+detail;assert np.isfinite(mix).all() and abs(mix).max()<1
            label=f'{round(amount*100):03d}';sf.write(a.out/f'mix_{label}_{seed}.wav',mix,48000,subtype='FLOAT')
            sf.write(a.out/f'core_{label}_{seed}.wav',main,48000,subtype='FLOAT')
            if amount==0:assert np.array_equal(sf.read(a.out/f'mix_{label}_{seed}.wav',always_2d=True)[0],expected)
            gain=gains(envelope,state,frames,amount)
            actual=np.asarray(power_observe(mix,bands)['mean_power'])
            r['seeds'].append(dict(seed=seed,amount=amount,peak=float(abs(mix).max()),
                gain_range=[float(gain.min()),float(gain.max())],
                training_band_error_db=(10*np.log10(actual/target)).tolist(),
                mix_sha256=sha(a.out/f'mix_{label}_{seed}.wav'),core_sha256=sha(a.out/f'core_{label}_{seed}.wav')))
            print(json.dumps(dict(stage='render',seed=seed,amount=amount,peak=float(abs(mix).max()))),flush=True)
        np.savez_compressed(a.out/f'states_{seed}.npz',state=state,normal=normal)
    r.update(result='amplitude_only_fixed_idle_candidates_pending_listening',plan=plan,
        known_report_sha256=sha(a.known/'report.json'),training_sha256=sha(parent/'training.wav'),
        parent_profile_sha256=sha(parent/'profile.json'),profile_sha256=sha(a.out/'profile.json'),
        source_design_condition=measured['condition_number'],evidence=evidence,
        modal_parameters_unchanged=modal==base['modal'],baseline_zero_FLOAT_exact=True,
        residual_identical_across_amounts=True,all_seeds_retained=True,
        limits=['Windowed magnitude is a mixed-recording proxy, not isolated combustion AM.',
            'Known FM produces1.13% apparent log-amplitude std in one fixture; it is not a universal error bound.',
            'Training observations overlap and are not independent trials.',
            'The0.12log-std ceiling and0.5/1 strengths are explicit engineering voicing choices.',
            'Current frequencies/phases and fixed-source spectral texture are preserved; source phase/RPM/load are not newly identified.',
            'No new C, runtime profile, driver state, UI default or spatial processing.'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],renders=len(r['seeds']))),flush=True)
