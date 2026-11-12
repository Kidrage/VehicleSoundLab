"""Fit and verify an opt-in startup texture; preserve executed sources and attempts."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read,sha
from residual_osc_v1.spectrum import matrices
from residual_osc_v1.fit import export

a.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),repo/'tools/analyze_startup_layers_v1.py',repo/'tools/drive_evidence_v1/sources.py',
       repo/'tools/residual_osc_v1/spectrum.py',repo/'tools/residual_osc_v1/fit.py',repo/'CMakeLists.txt']
for folder in ['src','modules','experiments']:
    paths += [x for x in (repo/folder).rglob('*') if x.is_file() and (x.suffix in ('.c','.h') or x.name=='CMakeLists.txt')]
index_path=repo/'handoff/C文件索引.csv'
prior_index=a.workspace/'baselines/stereo_bed_v1/docs/C文件索引.csv'
with prior_index.open(encoding='utf-8-sig',newline='') as f:
    index_rows=list(csv.reader(f))[1:]
paths += [index_path]+[repo/row[0] for row in index_rows]
paths=list(dict.fromkeys(paths))
for path in paths:
    dst=a.out/'exact_sources'/path.relative_to(repo);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dst)
shutil.copy2(prior_index,a.out/'prior_C_index.csv')
r=dict(schema='vsl.startup-texture-verification/1',result='running',commands=[],
       source_sha256={x.relative_to(repo).as_posix():sha(x) for x in paths},
       default_driver_changed=False,human_accepted=False,physical_source_separated=False)
bands=list(zip([300,400,520,660,800,960,1140,1340,1560,1820,2120,2500,3000,3700,4600,6000],
               [400,520,660,800,960,1140,1340,1560,1820,2120,2500,3000,3700,4600,6000,8000]))


def run(cmd):
    cmd=[str(v) for v in cmd];print(json.dumps({'running':cmd[:4]}),flush=True)
    result=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=600)
    name=f'command_{len(r["commands"]):02}.log';(a.out/name).write_bytes(result.stdout+result.stderr)
    r['commands'].append(dict(argv=cmd,returncode=result.returncode,log=name,sha256=sha(a.out/name)))
    assert result.returncode==0,name
    return result.stdout


try:
    prior=json.loads((repo/'research/stereo_bed_v1_summary.json').read_text(encoding='utf-8'))
    assert sha(prior_index)==prior['c_index_sha256']
    old_c={row[0]:row[-1] for row in index_rows}
    assert len(old_c)==448
    for path,digest in old_c.items():assert sha(repo/path)==digest,path
    r['prior_C_H_byte_unchanged']=len(old_c)
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    first,stop=36.65,37.12
    target=x[round((first-33)*48000):round((stop-33)*48000)]
    rows=[];observed=matrices(target,bands)
    for row in observed:
        rho=complex(*row['cross'])/np.sqrt(np.prod(row['power']))
        assert abs(rho)<=1+1e-12
        rows.append(dict(hz=row['hz'],power=row['power'],coherence=[rho.real,rho.imag]))
    # Independent signed-quadrature control: csd(L,R) must give +imaginary rho.
    t=np.arange(48000)/48000
    control=np.column_stack([np.cos(2*np.pi*750*t),-np.sin(2*np.pi*750*t)])
    moment=matrices(control,[(600,900)])[0]
    rho=complex(*moment['cross'])/np.sqrt(np.prod(moment['power']))
    assert abs(rho-1j)<1e-5
    r['known_signed_quadrature_error']=abs(rho-1j)
    halves=[matrices(y,bands) for y in np.array_split(target,2)]
    r['training_half_power_difference_dB']=[(10*np.log10(np.array(b['power'])/a['power'])).tolist()
                                            for a,b in zip(*halves)]
    model=a.out/'A_cabin_early.start';spectrum=a.out/'spectrum.residual'
    export(spectrum,rows)
    model.write_text('VSL_START_TEXTURE 1 0.005 0.035\n'+spectrum.read_text(encoding='ascii'),encoding='ascii')
    r['profile']=dict(path=str(model),sha256=sha(model),seconds=[first,stop],bands=rows,
        attack_seconds=.005,release_seconds=.035,
        timing='Engineering fades only, not measured physical crank/catch timing',
        meaning='Total observed300..8000Hz early-cabin texture, not additive residual debt or an isolated starter')
    # Literal pinned upstream structure, not execution of external BEAP implementations.
    upstream=a.workspace/'references/analysis/upstream_route_v1/fetch1/text/patchers/v10_engine_start_v3_beap~.maxpat'
    patch=json.loads(upstream.read_text(encoding='utf-8-sig'))['patcher']
    nodes={row['box']['id']:row['box'] for row in patch['boxes']}
    edges={tuple(row['patchline']['source']+row['patchline']['destination']) for row in patch['lines']}
    expected={'obj-75':'lores~ 520 0.72','obj-76':'reson~ 3.4 92 4.2','obj-82':'reson~ 1.8 740 9.',
              'obj-84':'svf~ 1700 0.7','obj-92':'reson~ 2.0 123 6.'}
    # Store literal values first; all fixed voicing in the patch remains authored design.
    r['upstream']=dict(path=str(upstream),sha256=sha(upstream),
        nodes={k:nodes[k].get('text') for k in expected},
        controls={k:nodes[k]['text'] for k in ['obj-29','obj-35','obj-41','obj-47','obj-53','obj-59']},
        labels={k:nodes[k].get('text') for k in ['obj-24','obj-30','obj-36','obj-42','obj-48','obj-54']},
        execution='Static literal graph only; neither BEAP internals nor Max audio executed')
    for node,value in expected.items():assert nodes[node].get('text')==value
    for e in [('obj-75',0,'obj-77',0),('obj-76',0,'obj-77',1),('obj-77',0,'obj-78',0),
              ('obj-28',0,'obj-78',1),('obj-40',0,'obj-83',1),('obj-46',0,'obj-86',1),('obj-52',0,'obj-93',1)]:
        assert e in edges
    (a.out/'upstream_v10_start.maxpat').write_bytes(upstream.read_bytes())
    build=repo/'build-start-texture-v1'
    run(['cmake','-S',repo/'experiments/start_texture_v1','-B',build,'-A','x64'])
    run(['cmake','--build',build,'--config','Release','--parallel','4'])
    ctest=run(['ctest','--test-dir',build,'-C','Release','--parallel','4','--output-on-failure'])
    r['ctest_summary']=ctest.decode('utf-8',errors='replace').splitlines()[-4:]
    (a.out/'bin').mkdir();(a.out/'renders').mkdir()
    probe=build/'Release/start_texture_probe.exe';shutil.copy2(probe,a.out/'bin'/probe.name);probe=a.out/'bin'/probe.name
    r['probe_sha256']=sha(probe)
    traces={};r['renders']=[]
    for seed in (48271,62017,78283):
        for mode in ('new','held') if seed!=48271 else ('old','new','held'):
            prefix=a.out/'renders'/f'{mode}_{seed}'
            run([probe,model,mode,prefix.with_suffix('.wav'),prefix.with_name(prefix.name+'_raw.wav'),prefix.with_suffix('.csv'),4,seed])
            audio,rate=sf.read(prefix.with_suffix('.wav'),always_2d=True)
            assert rate==48000 and len(audio)==192000 and np.isfinite(audio).all()
            with prefix.with_suffix('.csv').open() as f:trace=list(csv.DictReader(f))
            if mode in ('old','new'):
                key=[tuple(row[k] for k in ['frame','lifecycle','rpm','start_events','gate']) for row in trace]
                if traces:assert key==traces['driver']
                traces['driver']=key
                assert max(int(row['start_events']) for row in trace)==2
                assert {int(row['lifecycle']) for row in trace}>={0,1,2,3,4,5}
            r['renders'].append(dict(mode=mode,seed=seed,frames=len(audio),peak=float(np.max(abs(audio))),sha256=sha(prefix.with_suffix('.wav'))))
    r['driver_trace_equal_old_new_all_seeds']=True
    for seed in (48271,62017,78283):
        raw=a.out/'renders'/f'new_{seed}_raw.wav'
        assert raw.read_bytes()==(a.out/'renders'/f'held_{seed}_raw.wav').read_bytes()
        if seed==48271:assert raw.read_bytes()==(a.out/'renders'/f'old_{seed}_raw.wav').read_bytes()
    r['raw_source_identical_across_gates']=True
    # Hold a gate for3.25s; inspect separately from the driver's shorter engineered crank.
    r['held_moments']=[]
    for seed in (48271,62017,78283):
        audio,_=sf.read(a.out/'renders'/f'held_{seed}.wav',always_2d=True)
        moments=matrices(audio[round(.4*48000):round(3.3*48000)],bands)
        errors=[]
        for target_row,actual in zip(rows,moments):
            rho=complex(*actual['cross'])/np.sqrt(np.prod(actual['power']))
            errors.append(dict(hz=actual['hz'],power_dB=(10*np.log10(np.array(actual['power'])/target_row['power'])).tolist(),
                               coherence_error=abs(rho-complex(*target_row['coherence']))))
        r['held_moments'].append(dict(seed=seed,measure_seconds=[.4,3.3],errors=errors))
    for path,digest in r['source_sha256'].items():assert sha(repo/path)==digest,path
    r.update(result='isolated_candidate_verified',sample_playback=False,controller='unchanged existing lifecycle',
        current_UI_integrated=False,whole_startup_restored=False,
        limits=['Only early300..8000Hz mixed cabin texture is modeled',
                'No catching combustion, low rumble, room or exterior conversion in this candidate',
                'Cloud reproduces broad stereo statistics, not tonal ridges or time evolution',
                'No naturalness, long-run device, or hardware12 acceptance'])
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:r[k] for k in ['result','prior_C_H_byte_unchanged','driver_trace_equal_old_new_all_seeds','ctest_summary']},ensure_ascii=True))
