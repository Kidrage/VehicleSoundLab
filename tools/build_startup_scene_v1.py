"""Compile a same-A cabin settle DNA and exercise the unchanged unified C chain."""
import argparse,json,shutil,subprocess,sys
from fractions import Fraction
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
import soundfile as sf
from drive_evidence_v1.sources import sha
from sound_dna.windowed import estimate
from sound_dna.profile import export
from residual_osc_v1.spectrum import matrices
a.out.mkdir(parents=True,exist_ok=False)
for sub in ('bin','renders','exact_sources'):(a.out/sub).mkdir()
r=dict(result='running',commands=[],source_sha256={},human_accepted=False,fast_catch_fitted=False)

def run(cmd):
    cmd=list(map(str,cmd));print(json.dumps(dict(running=cmd[:4])),flush=True)
    done=subprocess.run(cmd,cwd=repo,capture_output=True,timeout=300)
    log=f'command_{len(r["commands"]):02}.log';(a.out/log).write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=cmd,returncode=done.returncode,log=log,sha256=sha(a.out/log)))
    assert done.returncode==0,log
    return done.stdout

try:
    previous=json.loads((repo/'research/startup_drive_v1_summary.json').read_text(encoding='utf-8'))
    for name,digest in previous['current_source_sha256'].items():
        if name.endswith(('.c','.h')):assert sha(repo/name)==digest,name
    r['prior455_C_H_unchanged']=True
    root=a.workspace/'references/analysis/startup_catch_v1/slow2';proof=json.loads((root/'report.json').read_text(encoding='utf-8'))
    assert proof['result']=='slow_observation_complete' and all(v['passed'] for v in proof['pairs'])
    assert len(proof['controls'])==7
    choice=proof['candidates'][0];assert choice['reference']==2 and choice['independent_agreement']['passed']
    assert sha(root/choice['npz'])==choice['sha256']
    data=np.load(root/choice['npz']);where=data['positions'];select=(where>=38.48)&(where<=39.51)
    normalized=data['normalized'][select];where=where[select]
    base=float(np.median(1/(1024*np.diff(where))))
    model,statistics=estimate(normalized,256,12)
    path=a.out/'A start cabin settle.model';export(path,model,base)
    r['profile']=dict(path=path.name,sha256=sha(path),base_hz=base,statistics=statistics,
        source_seconds=[float(where[0]),float(where[-1])],phase_choice=choice['phase'],
        meaning='Local A startup settling cabin observation, not fast catch or physical source separation')
    sf.write(a.out/'normalized_reference_float.wav',normalized,48000,subtype='FLOAT')
    ratio=Fraction(46.875/base).limit_denominator(10000)
    fixed=signal.resample_poly(normalized,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))
    sf.write(a.out/'fixed_reference_float.wav',fixed,48000,subtype='FLOAT')
    sources=[Path(__file__)]
    for folder in ('src','modules','experiments'):
        sources.extend(x for x in (repo/folder).rglob('*') if x.is_file() and (x.suffix in ('.c','.h','.in') or x.name=='CMakeLists.txt'))
    sources.extend([repo/'CMakeLists.txt',repo/'handoff/CMakeLists.txt',repo/'tools/sound_dna/profile.py',
        repo/'tools/sound_dna/windowed.py',repo/'tools/sound_dna/statistics.py'])
    sources.extend((repo/'tools/startup_catch_v1').glob('*.py'))
    for source in dict.fromkeys(sources):
        name=source.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);r['source_sha256'][name]=sha(source)
    build=repo/'build-startup-scene-v1'
    run(['cmake','-S',repo/'experiments/startup_scene_v1','-B',build,'-A','x64'])
    run(['cmake','--build',build,'--config','Release','--target','startup_scene_probe','--parallel','4'])
    scene=build/'Release/startup_scene_probe.exe';shutil.copy2(scene,a.out/'bin'/scene.name);scene=a.out/'bin'/scene.name
    fixed_probe=repo/'build-startup-drive-v1/bin/Release/VslSoundDna_probe.exe'
    old_build=json.loads((a.workspace/'references/analysis/startup_drive_v1/build2/report.json').read_text(encoding='utf-8'))
    assert sha(fixed_probe)==old_build['binaries']['bin\\Release\\VslSoundDna_probe.exe']
    shutil.copy2(fixed_probe,a.out/'bin'/fixed_probe.name);fixed_probe=a.out/'bin'/fixed_probe.name
    r['binary_sha256']={x.name:sha(x) for x in (a.out/'bin').iterdir()}
    r['fixed']=[]
    bands=[(30,120),(120,300),(300,600),(600,1200),(1200,3000),(3000,8000)]
    target=matrices(fixed,bands)
    for pitch in (.9,1.,1.1):
        file=a.out/'renders'/f'fixed_{pitch:.1f}.wav';run([fixed_probe,path,file,8,pitch,1,1])
        y,rate=sf.read(file,always_2d=True);assert rate==48000 and y.shape==(384000,2) and np.isfinite(y).all()
        assert not np.array_equal(y[:192000],y[192000:])
        row=dict(pitch=pitch,sha256=sha(file),peak=float(np.max(abs(y))),side_mid_dB=float(10*np.log10(np.mean(((y[:,0]-y[:,1])*.5)**2)/np.mean(((y[:,0]+y[:,1])*.5)**2))))
        if pitch==1:
            actual=matrices(y,bands)
            row['band_power_difference_dB']=[dict(hz=left['hz'],LR=(10*np.log10(np.array(right['power'])/left['power'])).tolist()) for left,right in zip(target,actual)]
        r['fixed'].append(row)
    starter=repo/'voices/startup_drive_v1/A cabin motion.start';r['starter_sha256']=sha(starter)
    for channels in (2,12):
        for amount in (0,.5):
            prefix=a.out/'renders'/f'scene_{channels}_{amount:.1f}'
            run([scene,path,starter,prefix,amount,channels])
    r['driver_checks']=[]
    for amount in (0,.5):
        stereo,_=sf.read(a.out/'renders'/f'scene_2_{amount:.1f}_mix.wav',always_2d=True)
        surround,_=sf.read(a.out/'renders'/f'scene_12_{amount:.1f}_mix.wav',always_2d=True)
        assert np.array_equal(stereo,surround[:,:2]) and np.max(abs(surround[:,2:]))==0
        dna,_=sf.read(a.out/'renders'/f'scene_2_{amount:.1f}_dna.wav',always_2d=True)
        start,_=sf.read(a.out/'renders'/f'scene_2_{amount:.1f}_startup.wav',always_2d=True)
        error=float(np.max(abs(stereo-.25*(dna+start))));assert error<1e-8
        r['driver_checks'].append(dict(startup_amount=amount,front_equal=True,other10_zero=True,single_mix_error=error))
    for suffix in ('raw.wav','dna.wav','trace.csv'):
        left=a.out/'renders'/('scene_2_0.0_'+suffix);right=a.out/'renders'/('scene_2_0.5_'+suffix)
        assert left.read_bytes()==right.read_bytes(),suffix
        for amount in (0,.5):
            assert (a.out/'renders'/f'scene_2_{amount:.1f}_{suffix}').read_bytes()==(a.out/'renders'/f'scene_12_{amount:.1f}_{suffix}').read_bytes()
    for name,digest in r['source_sha256'].items():assert sha(repo/name)==digest,name
    voices=repo/'voices/startup_settle_v1';voices.mkdir(exist_ok=True)
    destination=voices/path.name
    if destination.exists():assert destination.read_bytes()==path.read_bytes()
    else:shutil.copy2(path,destination)
    r.update(result='same_A_cabin_candidate_rendered',controller='unchanged existing C driver',
        mapping='anchor acoustic base / existing engineering idle RPM; not measured physical calibration',
        no_PCM_or_recorded_timeline=True,device_checked=False,UI_integrated=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],profile=r['profile'],fixed=r['fixed'],driver_checks=r['driver_checks'])))
