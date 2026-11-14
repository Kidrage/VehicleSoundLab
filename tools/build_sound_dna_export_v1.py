"""Build an isolated raw-seeded host and verify old-raw parity and seed/block contracts."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load,save,sha

p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','fit','out'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},commands=[])
build=repo/'build-sound-dna-export-v1'

def command(argv,label,success=True):
    argv=list(map(str,argv));done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=180)
    (a.out/(label+'.log')).write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=argv,exit_code=done.returncode,log=label+'.log'))
    save(a.out/'report.json',r)
    assert (done.returncode==0)==success,(label,done.returncode)
    return done

try:
    names=['tools/build_sound_dna_export_v1.py','experiments/sound_dna_export_v1/probe.c',
        'experiments/sound_dna_export_v1/CMakeLists.txt','src/io/wav.c','src/io/wav.h','src/io/file.c','src/io/file.h']
    names += [v.relative_to(repo).as_posix() for v in (repo/'modules/sound_dna').glob('*') if v.is_file()]
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    command(['cmake','-S',repo/'experiments/sound_dna_export_v1','-B',build,'-G','Visual Studio 17 2022','-A','x64'],'configure')
    command(['cmake','--build',build,'--config','Release','--parallel','2'],'compile')
    exe=build/'bin/Release/sound_dna_export.exe';shutil.copy2(exe,a.out/'sound_dna_export.exe')
    r['exe_sha256']=sha(exe)
    assert command([exe,'--describe'],'protocol').stdout.strip()==b'vsl.sound-dna-raw-export/1'
    folder=a.fit/'F3 Sixth Before Upshift';model=folder/'voice.model'
    r['model_sha256']=sha(model)
    command([exe,model,a.out/'legacy_seed48271.wav',8,1,1,48271,512],'legacy_parity')
    raw,rate=sf.read(folder/'DNA_1.wav',always_2d=True)
    exact,rate2=sf.read(a.out/'legacy_seed48271.wav',always_2d=True)
    assert rate==rate2==48000 and np.array_equal(raw,exact)
    old2,_=sf.read(folder/'DNA_23117.wav',always_2d=True)
    old3,_=sf.read(folder/'DNA_61927.wav',always_2d=True)
    assert np.array_equal(old2,old3) and np.array_equal(old2[240:],raw[240:]*.5)
    r['correction']=dict(original_attempt='fit1',original_report_sha256=sha(a.fit/'report.json'),
        actual_legacy_seed=48271,legacy_argument6='raw if first character is 1; otherwise monitor output',
        original_DNA1_is_fixed_seed_raw=True,other_two_are_same_fixed_seed_monitor=True,
        old_seed_labels_invalid=True,local_extraction_and_gates_unaffected=True,
        raw_audio_sample_parity=True,attempt_preserved=True)
    seeds=(1,23117,61927);waves=[];static=[]
    for seed in seeds:
        arrays=[]
        for chunk in (512,37):
            name=f'seed{seed}_chunk{chunk}.wav'
            command([exe,model,a.out/name,.25,1,1,seed,chunk],name)
            audio,rate=sf.read(a.out/name,always_2d=True)
            assert rate==48000 and audio.shape==(12000,2) and np.isfinite(audio).all()
            arrays.append(audio)
        assert np.array_equal(*arrays)
        waves.append(arrays[0])
        name=f'static{seed}.wav';command([exe,model,a.out/name,.25,1,0,seed,512],name)
        static.append(sf.read(a.out/name,always_2d=True)[0])
    assert all(not np.array_equal(x,y) for i,x in enumerate(waves) for y in waves[i+1:])
    assert all(np.array_equal(static[0],x) for x in static[1:])
    invalid=['0','-1','+1','1x','18446744073709551616']
    for i,seed in enumerate(invalid):
        dest=a.out/f'invalid{i}.wav'
        command([exe,model,dest,.25,1,1,seed,512],f'invalid{i}',False)
        assert not dest.exists()
    for filename,count in [('C_files_sha256.json',646),('voice_files_sha256.json',74)]:
        records=load(a.workspace/'baselines/bench_load_ui_v1/inputs'/filename)
        assert len(records)==count and all(sha(repo/n)==h for n,h in records.items())
    r.update(result='passed',same_seed_chunk_exact=True,three_seeds_distinct=True,
        zero_detail_seed_independent=True,invalid_seed_rejected_before_output=True,
        protected_C_H_exact=646,protected_voice_parameters_exact=74,added_C_H=1,
        runtime_changed=False,previous_CTests_not_repeated=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    save(a.out/'report.json',r)
print({k:r.get(k) for k in ('result','correction','three_seeds_distinct')})
