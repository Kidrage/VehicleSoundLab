"""Compile three source-supported bridge voices and render with original C kernels."""
import argparse, os, shutil, subprocess, sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out','controls','dna-probe','detail-probe']:
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from drive_evidence_v1.sources import read
from stationary_bridge_v1.extract import targets,compile_anchor
from sound_dna.profile import export
from idle_texture_v1.profile import attenuate
from stationary_recipe_v1.parameters import compile_detail,encode
from resonant_detail_v1.controls import run as detail_controls
from resonant_detail_v1.voice import render as detail_oracle
from residual_osc_v1.spectrum import matrices,error

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',inputs={},sources={},commands=[],anchors=[],rejected=[])
def consume(path):r['inputs'][str(path)]=sha(path);return path
def run(argv,label):
    done=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=180)
    log=a.out/(label+'.log');log.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit_code=done.returncode,log=log.name,sha256=sha(log)))
    save(a.out/'report.json',r)
    if done.returncode:raise RuntimeError(log)
try:
    names=['tools/run_stationary_bridge_v1.py','tools/stationary_bridge_v1/extract.py',
           'research/stationary_bridge_v1_plan.json','tools/research_archive_v1.py',
           'tools/stationary_recipe_v1/parameters.py','tools/idle_texture_v1/profile.py',
           'tools/residual_osc_v1/spectrum.py','tools/drive_evidence_v1/sources.py',
           'tools/exterior_clock_v1/warp.py']
    for package in ['sound_dna','resonant_detail_v1']:
        names += [x.relative_to(repo).as_posix() for x in (repo/'tools'/package).glob('*.py')]
    for name in sorted(set(names)):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    plan=load(consume(repo/'research/stationary_bridge_v1_plan.json'))
    checks=load(consume(a.controls/'verification.json'));assert checks['result']=='pass'
    for name,h in checks['source_sha256'].items():assert sha(repo/'tools'/name)==h
    kernel=load(consume(repo/'research/resonant_detail_v1_plan.json'))
    r['detail_controls_before_source']=detail_controls(kernel)
    parent=a.workspace/'baselines/exterior_anchors_v1'
    manifest=load(consume(parent/'manifest.json'));digests={v['path']:v['sha256'] for v in manifest['files']}
    frozen='evidence/anchors_v2/build.json';assert sha(consume(parent/frozen))==digests[frozen]
    old=load(parent/frozen)
    index=load(consume(repo/'voices/exterior_anchors_v1/index.json'))
    desired=targets([v['base_hz'] for v in index['voices'][1:]])
    audio,provenance=read(a.workspace,plan['source'],'exterior_dynamic_observation')
    r['source']=provenance
    for key in ['raw','master']:
        source=load(repo/'references/segments_v1.json')['sources']['A'];consume(a.workspace/source[key])
    consume(a.dna_probe);consume(a.detail_probe)
    for i,(name,target) in enumerate(zip(plan['names'],desired)):
        folder=a.out/name;folder.mkdir()
        model,reference,normalized,positions,info=compile_anchor(audio,provenance['seconds'][0],old['paths']['fall']['rows'],target,plan)
        # Save the actual source result before applying the unchanged gates.
        # Reject unsupported extractions individually; never search aperture,
        # phase reference or strength just to qualify the requested geometry.
        root=info['root_hz']
        sf.write(folder/'normalized.wav',normalized,48000,subtype='FLOAT')
        sf.write(folder/'reference.wav',reference,48000,subtype='FLOAT')
        first,stop=[round((t-provenance['seconds'][0])*48000) for t in info['phase']['source_seconds']]
        sf.write(folder/'raw_source.wav',audio[first:stop],48000,subtype='FLOAT')
        np.savez_compressed(folder/'coordinates.npz',source_seconds=positions)
        save(folder/'extraction.json',dict(name=name,**info))
        if (info['statistics']['observation_frames']<plan['gates']['minimum_observations'] or
            min(v for c in info['heldout_coherence'].values() for v in c)<=plan['gates']['heldout_carrier_coherence']):
            r['rejected'].append(dict(name=name,**info,reason='Original aperture/carrier qualification failed; no model or detail published'))
            save(a.out/'report.json',r)
            print(dict(name=name,rejected=True,heldout=info['heldout_coherence']),flush=True)
            continue
        export(folder/'voice.model',model,root)
        modified,gain=attenuate(model,root,plan['replacement_power'],plan['transition_hz'])
        export(folder/'withdraw35.model',modified,root)
        dna={}
        for label in ['original','withdraw35']:
            path=folder/('voice.model' if label=='original' else 'withdraw35.model')
            run([a.dna_probe,path,folder/(label+'.wav'),plan['seconds'],1,1,1],f'DNA_{i}_{label}')
            dna[label],rate=sf.read(folder/(label+'.wav'),always_2d=True);assert rate==48000
        detail=compile_detail(reference,dna['withdraw35'][plan['crop_frames']:],kernel)
        encode(folder/'detail.rdetail',detail,root,kernel['warmup_frames'])
        row=dict(name=name,**info,DNA_sha256=sha(folder/'voice.model'),detail_sha256=sha(folder/'detail.rdetail'),detail_model=detail,renders=[])
        r['anchors'].append(row);save(a.out/'report.json',r)
        for seed in plan['seeds']:
            warm=kernel['warmup_frames'];raw=folder/f'detail_{seed}.f64'
            run([a.detail_probe,folder/'detail.rdetail',raw,warm+plan['seconds']*48000,seed,-warm*root/48000],f'detail_{i}_{seed}')
            values=np.fromfile(raw,dtype='<f8').reshape(-1,len(detail['filters'])+2)[warm:]
            if seed==plan['seeds'][0]:
                expected=detail_oracle(detail['filters'],plan['seconds']*48000,seed,kernel)
                row['C_detail_oracle_FS']=float(np.max(abs(expected-values[:,2:])))
                assert row['C_detail_oracle_FS']<plan['gates']['C_detail_oracle_FS']
            mixed=dna['withdraw35']+values[:,:2]
            assert np.isfinite(mixed).all() and abs(mixed).max()*plan['output_gain']<plan['gates']['maximum_peak_after_gain']
            metrics=error(matrices(reference),matrices(mixed[plan['crop_frames']:]))
            maximum=max(abs(v) for b in metrics for v in b['power_delta_db'])
            sf.write(folder/f'candidate_{seed}.wav',mixed,48000,subtype='FLOAT')
            sf.write(folder/f'detail_{seed}.wav',values[:,:2],48000,subtype='FLOAT')
            row['renders'].append(dict(seed=seed,metrics=metrics,maximum_LR_band_error_db=maximum))
            save(a.out/'report.json',r)
            assert maximum<plan['gates']['maximum_LR_band_power_error_db'],(name,seed,maximum)
        save(folder/'model.json',row)
        print(dict(name=name,root=root,heldout=info['heldout_coherence'],max_error_db=max(v['maximum_LR_band_error_db'] for v in row['renders'])),flush=True)
    roots=sorted([v['base_hz'] for v in index['voices'][1:]]+[v['root_hz'] for v in r['anchors']])
    connected=all(b*.9<a*1.1 for a,b in zip(roots,roots[1:]))
    r.update(result='qualified_bridge_voices_rendered',detail_support_roots=roots,geometric_support_connected=connected,
             remaining_support_gaps_hz=[[x*1.1,y*.9] for x,y in zip(roots,roots[1:]) if x*1.1<y*.9],
             requested_new_anchors=3,qualified_new_anchors=len(r['anchors']),
             human_accepted=False,native_default_changed=False,pending_idle_changed=False,new_real_engines=0)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
