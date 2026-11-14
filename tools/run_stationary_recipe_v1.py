"""Fit and actually render stationary variants with the existing C kernels."""
import argparse, os, shutil, subprocess, sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for name in ['workspace', 'out', 'dna-probe', 'detail-probe']:
    p.add_argument('--'+name, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for name in ['OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS']: os.environ[name] = '2'
import numpy as np
import soundfile as sf
from research_archive_v1 import load, save, sha
from idle_texture_v1.profile import load as DNA_load, attenuate
from sound_dna.profile import export
from stationary_recipe_v1.parameters import compile_detail, encode
from resonant_detail_v1.controls import run as known_controls
from resonant_detail_v1.voice import render as detail_oracle
from residual_osc_v1.spectrum import matrices, error

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', inputs={}, sources={}, commands=[], anchors=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def command(argv, log):
    done = subprocess.run(list(map(str, argv)), cwd=repo, capture_output=True, timeout=180)
    (a.out/log).write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=list(map(str, argv)), exit_code=done.returncode,
                              log=log, sha256=sha(a.out/log)))
    save(a.out/'report.json', r)
    if done.returncode: raise RuntimeError(log)


try:
    names=['tools/run_stationary_recipe_v1.py','tools/stationary_recipe_v1/parameters.py',
           'research/stationary_recipe_v1_plan.json','tools/research_archive_v1.py',
           'tools/idle_texture_v1/profile.py','tools/sound_dna/profile.py',
           'tools/residual_osc_v1/spectrum.py','tools/sustain_osc_v1/oracle.py']
    names += [x.relative_to(repo).as_posix() for x in (repo/'tools/resonant_detail_v1').glob('*.py')]
    for n in names:
        dest=a.out/'exact_sources'/n; dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/n,dest); r['sources'][n]=sha(repo/n)
    plan=load(consume(repo/'research/stationary_recipe_v1_plan.json'))
    kernel=load(consume(repo/'research/resonant_detail_v1_plan.json'))
    # Known recurrence, analytic frequency response and measured noise power
    # before any new stationary spectrum is fitted.
    r['controls']=known_controls(kernel)
    manifest=load(consume(a.workspace/'baselines/exterior_anchors_v1/manifest.json'))
    digests={x['path']:x['sha256'] for x in manifest['files']}
    registry=load(consume(repo/'references/segments_v1.json'))['sources']['A']
    for key in ['raw','master']:
        assert sha(consume(a.workspace/registry[key]))==registry[key+'_sha256']
    index=load(consume(repo/'voices/exterior_anchors_v1/index.json'))
    for exe in [a.dna_probe,a.detail_probe]: consume(exe)
    for i,name in enumerate(plan['anchors']):
        folder=a.out/name; folder.mkdir()
        source=repo/'voices/exterior_anchors_v1'/(name+'.model')
        entry=next(v for v in index['voices'] if v['name']==name)
        assert sha(consume(source))==entry['model_sha256']
        frozen_name='evidence/anchors_v2/'+name+'/fixed_reference_float.wav'
        reference_path=a.workspace/'baselines/exterior_anchors_v1'/frozen_name
        assert sha(consume(reference_path))==digests[frozen_name]
        reference,rate=sf.read(reference_path,always_2d=True); assert rate==48000
        base,root=DNA_load(source)
        modified,gain=attenuate(base,root,plan['replacement_power'],plan['transition_hz'])
        export(folder/'withdraw35.model',modified,root)
        dna={}
        for label,path in [('original',source),('withdraw35',folder/'withdraw35.model')]:
            destination=folder/(label+'.wav')
            command([a.dna_probe,path,destination,plan['seconds'],1,1,1],f'DNA_{i}_{label}.log')
            dna[label],rate=sf.read(destination,always_2d=True); assert rate==48000
        assert all(np.array_equal(base[key][gain==1],modified[key][gain==1]) for key in ['mean','basis','root'])
        model=compile_detail(reference,dna['withdraw35'][plan['crop_frames']:],kernel)
        encode(folder/'detail.rdetail',model,root,kernel['warmup_frames'])
        sf.write(folder/'reference.wav',reference,48000,subtype='FLOAT')
        row=dict(name=name,source=entry,root_hz=root,model=model,
                 detail_sha256=sha(folder/'detail.rdetail'),renders=[])
        r['anchors'].append(row);save(folder/'model.json',row);save(a.out/'report.json',r)
        for seed in plan['detail_seeds']:
            raw=folder/f'detail_{seed}.f64'
            # The raw kernel probe begins with zero filter state. Its profile's
            # warmup is metadata for callers, not an automatic probe action.
            warm=kernel['warmup_frames']
            command([a.detail_probe,folder/'detail.rdetail',raw,warm+plan['seconds']*48000,
                     seed,-warm*root/48000],f'detail_{i}_{seed}.log')
            values=np.fromfile(raw,dtype='<f8').reshape(-1,len(model['filters'])+2)[warm:]
            if seed==plan['detail_seeds'][0]:
                expected=detail_oracle(model['filters'],plan['seconds']*48000,seed,kernel)
                err=float(np.max(abs(expected-values[:,2:])))
                assert err<plan['gates']['C_detail_oracle_FS'],err
                row['C_detail_oracle_FS']=err
            mixed=dna['withdraw35']+values[:,:2]
            peak=float(abs(mixed).max())
            assert np.isfinite(mixed).all() and peak*plan['output_gain']<plan['gates']['peak_after_common_gain']
            sf.write(folder/f'candidate_{seed}.wav',mixed,48000,subtype='FLOAT')
            sf.write(folder/f'detail_{seed}.wav',values[:,:2],48000,subtype='FLOAT')
            comparison=error(matrices(reference),matrices(mixed[plan['crop_frames']:]))
            row['renders'].append(dict(seed=seed,peak_FS=peak,metrics=comparison,
                mixed_sha256=sha(folder/f'candidate_{seed}.wav')))
        save(folder/'model.json',row); save(a.out/'report.json',r)
        print(dict(name=name,root=root,oracle=row['C_detail_oracle_FS'],negative_bands=model['negative_debt_bands']),flush=True)
    r.update(result='four_stationary_candidates_rendered',new_fitting=True,source_recordings=1,
             new_engines=0,periodic_envelope=False,room=False,PCM_timeline_in_profile=False,
             pending_idle_modified=False,moving35_modified=False,human_accepted=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
