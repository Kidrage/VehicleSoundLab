"""Verify the actual C full recipe against frozen offline mixtures and stems."""
import argparse,csv,json,re,shutil,subprocess,sys,time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--build',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--contract-proof',type=Path,help='Reuse exact unchanged C sources and passing build/49-test logs')
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from resonant_detail_v1.voice import render

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.resonant-source-verification/1',result='running',source_sha256={},input_sha256={},commands=[],comparisons=[],routing=[])

def bind(path):
    path=Path(path);r['input_sha256'][str(path)]=sha(path);return path

def run(argv,expected=0):
    started=time.perf_counter()
    proc=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=180)
    log=a.out/f'command_{len(r["commands"]):02}.log';log.write_bytes(proc.stdout+proc.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit_code=proc.returncode,expected=expected,
                             seconds=time.perf_counter()-started,log=log.name,sha256=sha(log)))
    assert proc.returncode==expected,(argv,proc.returncode,log)
    return proc

def frozen(name,relative):
    base=a.workspace/'baselines'/name
    manifest=json.loads(bind(base/'manifest.json').read_text(encoding='utf-8'))
    row=next(v for v in manifest['files'] if v['path']==relative)
    path=bind(base/relative);assert sha(path)==row['sha256'],path
    return path

def wave(path):
    x,rate=sf.read(path,always_2d=True);assert rate==48000;return x

try:
    index=bind(repo/'handoff/C文件索引.csv');shutil.copy2(index,a.out/'prior_C_index.csv')
    with index.open(encoding='utf-8-sig') as f:prior=list(csv.DictReader(f))
    prior=[v for v in prior if not v['文件'].startswith(('modules/resonant_source/','experiments/resonant_source_v1/'))]
    assert len(prior)==492
    for row in prior:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    paths=[Path(__file__),repo/'handoff/CMakeLists.txt',repo/'tools/resonant_detail_v1/voice.py',
           repo/'tools/resonant_detail_v1/envelope.py',repo/'tools/sustain_osc_v1/oracle.py']
    for folder in ('modules/resonant_source','experiments/resonant_source_v1','modules/resonant_detail',
                   'modules/dna_scene','modules/sound_dna','modules/phase_texture','modules/stereo_bed'):
        paths.extend(v for v in (repo/folder).iterdir() if v.is_file() and (v.suffix in ('.c','.h') or v.name=='CMakeLists.txt'))
    for path in paths:
        target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);r['source_sha256'][path.relative_to(repo).as_posix()]=sha(path)
    pattern=rb'100% tests passed(?:, 0 tests failed)? out of 49'
    if a.contract_proof:
        proof=json.loads(a.contract_proof.read_text(encoding='utf-8'))
        assert proof['Ctests_passed']==49
        for name,digest in proof['source_sha256'].items():
            assert sha(a.contract_proof.parent/'exact_sources'/name)==digest,name
            if name!=Path(__file__).relative_to(repo).as_posix():assert sha(repo/name)==digest,name
        for row in proof['commands']:
            log=a.contract_proof.parent/row['log'];assert sha(log)==row['sha256']
            if row['argv'][0] in ('cmake','ctest'):
                assert row['exit_code']==0
                shutil.copy2(log,a.out/('reused_'+row['log']))
                if row['argv'][0]=='ctest':assert re.search(pattern,log.read_bytes())
        r['reused_contract_proof']=dict(file=str(a.contract_proof),sha256=sha(a.contract_proof))
    else:
        run(['cmake','-S',repo/'handoff','-B',a.build,'-G','Visual Studio 17 2022','-A','x64'])
        run(['cmake','--build',a.build,'--config','Release','--parallel','4'])
        done=run(['ctest','--test-dir',a.build,'-C','Release','--parallel','4','--output-on-failure'])
        assert re.search(pattern,done.stdout)
    r['Ctests_passed']=49
    bind(a.build/'CMakeCache.txt');shutil.copy2(a.build/'CMakeCache.txt',a.out/'CMakeCache.after_build.txt')
    probe=a.build/'bin/Release/VslResonantSource_probe.exe';shutil.copy2(probe,a.out/probe.name)
    probe=a.out/probe.name;r['probe_sha256']=sha(probe)
    if a.contract_proof:assert r['probe_sha256']==proof['probe_sha256']
    model_index=json.loads(bind(repo/'voices/resonant_detail_c_v1/index.json').read_text(encoding='utf-8'))
    raw=a.out/'raw';raw.mkdir()
    limits=dict(DNA_stem_maximum_FS=2e-7,LF_raw_maximum_FS=1e-7,detail_maximum_FS=1e-9,mix_maximum_FS=3e-7)
    r['predeclared_limits']=limits
    for spec in model_index['profiles']:
        name=spec['name'];model=json.loads(bind(repo/spec['original']).read_text(encoding='utf-8'))
        assert sha(repo/spec['original'])==spec['original_sha256']
        dna=bind(repo/model['original_DNA']['file']);assert sha(dna)==model['original_DNA']['sha256']
        detail=bind(repo/spec['file']);assert sha(detail)==spec['sha256']
        moving=name=='moving_35';group='resonant_detail_v1' if moving else 'idle_resonant_v1'
        prefix='evidence' if moving else 'evidence/idle_resonant_v1'
        label='replace_35' if moving else ('add_only' if name=='idle_add' else 'replace35')
        main=frozen(group,f'{prefix}/fit1/{label}_{"dna" if moving else "DNA"}.wav')
        main=wave(main)
        low_spec=model.get('independent_LF');low=bind(repo/low_spec['file']) if low_spec else '-'
        if low_spec:assert sha(low)==low_spec['sha256']
        low_raw=wave(frozen('coherent_low_v1','evidence/raw/measured.wav'))[:len(main)] if moving else np.zeros_like(main)
        low_scale=low_spec['scale'] if low_spec else 0
        gains=np.array(spec['recipe'].get('detail_amplitude_gain',spec['recipe'].get('detail_gain')))
        ratios=np.array(model['kernel'].get('stereo_R_over_L',model.get('stereo_R_over_L')))
        plan=dict(warmup_frames=model['kernel']['warmup_frames'],cycle_frames=model['kernel']['cycle_frames'])
        for seed in (8121907,23117,61927):
            file=raw/f'{name}_{seed}_2.f64'
            args=[probe,dna,low,detail,file,spec['recipe']['harmonic_power_reduction'],seed,len(main),2,1]
            run(args)
            actual=np.fromfile(file,dtype='<f8').reshape(len(main),13);assert np.isfinite(actual).all()
            bands=render(model['filters'],len(main),seed,plan)
            expected_detail=np.column_stack((bands@gains,bands@(gains*ratios)))
            reference=wave(frozen(group,f'{prefix}/render1/raw/{label}_{seed}_mix.wav'))
            assert len(reference)==len(main)
            errors=dict(DNA_stem_maximum_FS=float(abs(actual[:,2:4]-main).max()),
                        LF_raw_maximum_FS=float(abs(actual[:,4:6]-low_raw).max()),
                        detail_maximum_FS=float(abs(actual[:,8:10]-expected_detail).max()),
                        mix_maximum_FS=float(abs(actual[:,10:12]-reference).max()))
            for key,value in errors.items():assert value<limits[key],(name,seed,key,value)
            assert np.array_equal(actual[:,:2],actual[:,10:12]*.5)
            assert float(abs(actual[:,:2]).max())<.95
            clock=np.mod(np.arange(len(main))*model['acoustic_root_hz']/48000,1)
            phase_error=float(np.max(abs((actual[:,-1]-clock+.5)%1-.5)))
            assert phase_error<1e-10,(name,phase_error)
            row=dict(profile=name,seed=seed,frames=len(main),errors=errors,source_phase_error_cycles=phase_error,
                     peak_FS=float(abs(actual[:,:2]).max()),file=file.relative_to(a.out).as_posix(),sha256=sha(file))
            r['comparisons'].append(row)
            if seed==8121907:
                twelve=raw/f'{name}_{seed}_12.f64';run([*args[:4],twelve,*args[5:8],12,1])
                full=np.fromfile(twelve,dtype='<f8').reshape(len(main),23)
                assert np.array_equal(actual[:,:2],full[:,:2]) and np.count_nonzero(full[:,2:12])==0
                assert np.array_equal(actual[:,2:],full[:,12:])
                r['routing'].append(dict(profile=name,front_stems_phase_exact=True,remaining10zero=True,
                    file=twelve.relative_to(a.out).as_posix(),sha256=sha(twelve)))
                # Export a native-C stereo file at the same master gain for later host checks.
                sf.write(a.out/f'{name}_C.wav',actual[:,:2],48000,subtype='FLOAT')
            print(json.dumps(dict(profile=name,seed=seed,errors=errors,phase_error=phase_error)),flush=True)
    r.update(result='full_C_mixture_and_contracts_pass',prior_C_H_unchanged=492,new_C_H=8,
             no_new_fitting=True,one_source_phase=True,default_or_native_or_driver_or_take_changed=False,
             human_listening_acceptance=False,physical_7_1_4_or_device_or_longrun=False,
             limits=['Matches held offline recipes within float-stage rounding, not new naturalness acceptance',
                     'Same three existing contexts; idle thermal state and engine RPM remain unknown',
                     'Fixed-Hz resonators and .9..1.1 pitch range are not a full RPM/load map',
                     '2/12 preserves recording FL/FR only; no physical source separation or immersive upmix',
                     'No new native host,driver,take adapter,device or longrun validation'])
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],comparisons=len(r['comparisons']),Ctests=r.get('Ctests_passed'))))
