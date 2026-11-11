"""Validate opt-in native character integration; preserve completed reviews."""
import csv
import json
import shutil
import subprocess
import sys
from runtime_review import ROOT,sha,render
from review_audit import read_json,device
from reference_segments import checked_source
import numpy as np
import soundfile as sf
from PIL import Image

OUT=ROOT/'renders/v0.16.0'
BUILD=ROOT/'build-v016/Release'
CASES={
    'low':('fixed',5,1200,.18),'mid':('fixed',5,4000,.85),'high':('fixed',5,8000,.85),
    'neutral':('neutral',8,850,.18),'lift':('lift',7.5,5000,.85),'drive':('auto',30,850,.18)}

def run(args,timeout=90):
    p=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,text=True,check=True,timeout=timeout)
    return p.stdout

def trace_equal(new,old):
    with new.open() as f:a=list(csv.DictReader(f))
    with old.open() as f:b=list(csv.DictReader(f))
    assert len(a)==len(b)
    assert all(all(x[k]==v for k,v in y.items()) for x,y in zip(a,b))
    return len(a)

def create():
    if (OUT/'verification.json').exists():raise SystemExit('Preserve completed V016 verification.')
    OUT.mkdir(parents=True,exist_ok=True)
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    if '--resume' not in sys.argv:
        subprocess.run([str(BUILD/'VehicleSoundLab.exe'),'--smoke-test'],cwd=ROOT,startupinfo=startup,check=True,timeout=45)
    native=read_json(OUT/'ui_smoke.json');device(native,'0.16.0')
    for key in ['character_controls','character_preset_roundtrip','character_legacy_preset','character_active_on_device',
        'propagation_control','propagation_preset_roundtrip','propagation_active_on_device']:assert native[key],key
    take_report=read_json(OUT/'ui_take_smoke.json');take=take_report['result']
    assert take_report['character_state_match']==take_report['device_character_state_match']==1
    for key in ['saved','loaded','offline_hash_match','final_drive_state_match','device_replay_hash_and_state_match',
        'manual_replay_stop','controls_locked','muted']:assert take[key]==1,key
    assert take['replay_queue_empty']==0 and .95<take['replay_device_seconds']/take['replay_wall_seconds']<1.02
    assert all(read_json(OUT/'ui_take_controls.json').values())
    for path in OUT.glob('*.bmp'):
        with Image.open(path) as image:image.save(path.with_suffix('.png'))
    log=ROOT/'build-v016/Testing/Temporary/LastTest.log';assert log.read_bytes().count(b'Test Passed.')==18
    shutil.copy2(log,OUT/'ctest.log')
    print('18 CTests and actual muted device/control/reconstruction checks pass.',flush=True)
    history=read_json(ROOT/'renders/v0.15.0/verification.json')
    unchanged={}
    for profile in range(5):
        path=OUT/f'default_profile_{profile}.wav'
        render(BUILD/'vsl_render.exe',path,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],'0.16.0')
        assert path.read_bytes()==(ROOT/f'renders/v0.15.0/profile_{profile}.wav').read_bytes()
        unchanged[str(profile)]=sha(path)
    render(BUILD/'vsl_render.exe',OUT/'default_drive.wav',['--scenario','auto','--seconds','30','--width','.8','--propagation','1'],
        '0.16.0',['--trace',str(OUT/'default_drive.csv')])
    assert (OUT/'default_drive.wav').read_bytes()==(ROOT/'renders/v0.15.0/drive_propagation.wav').read_bytes()
    trace_equal(OUT/'default_drive.csv',ROOT/'renders/v0.15.0/drive.csv')
    print('Five default templates and 30 s driving audio match frozen V015 byte-for-byte.',flush=True)
    comparisons={};(OUT/'stems').mkdir(exist_ok=True)
    for name,(scenario,seconds,rpm,load) in CASES.items():
        variants={'base':(0,0),'combined':(.65,.65)}
        if name=='mid':variants.update(pressure=(1,0),structure=(0,1))
        comparisons[name]={}
        for tag,(pressure,structure) in variants.items():
            prefix=OUT/f'{name}_{tag}';take_path=prefix.with_suffix('.vsltake');wav=prefix.with_suffix('.wav');trace=prefix.with_suffix('.csv')
            run([BUILD/'vsl_character_probe.exe',take_path,scenario,seconds,rpm,load,pressure,structure])
            run([BUILD/'vsl_take_render.exe',take_path,wav,'--trace',trace])
            a,sr=sf.read(wav,always_2d=True);b,old_sr=sf.read(ROOT/f'renders/character_v1/{name}_{tag}.wav',always_2d=True)
            assert sr==old_sr==48000 and a.shape==b.shape and np.isfinite(a).all() and abs(a).max()<.95
            error=float(abs(a-b).max());settled_error=float(abs(a[24000:]-b[24000:]).max())
            # Native strengths ramp from zero with the existing 18 ms parameter follower.
            # The frozen offline host starts at fixed amounts. Bound the startup-only
            # discrepancy explicitly and require agreement after 0.5 seconds.
            assert error<1e-6 and settled_error<1e-7,(name,tag,error,settled_error)
            if tag=='base':assert wav.read_bytes()==(ROOT/f'renders/character_v1/{name}_frozen.wav').read_bytes()
            # Frozen experiment logs every control period; take CLI logs host chunks.
            # The capture probe supplies the same exact control-period observation frames.
            rows=trace_equal(take_path.with_suffix('.vsltake.csv'),ROOT/f'renders/character_v1/{name}_{tag}.csv')
            comparisons[name][tag]=dict(max_float_error_vs_frozen_experiment=error,after_half_second_error=settled_error,
                trace_rows=rows,take_sha256=sha(take_path),native_parameter_smoothing_seconds=.018)
        print('frozen recipe comparison:',name,comparisons[name],flush=True)
    take_path=OUT/'ui_take_smoke.vsltake'
    for channels in [2,12]:
        run([BUILD/'vsl_take_render.exe',take_path,OUT/f'take_{channels}.wav','--channels',channels,
            '--trace',OUT/f'take_{channels}.csv','--stems',OUT/f'stems/take_{channels}'])
    assert (OUT/'take_2.wav').read_bytes()==(OUT/'ui_take_smoke.wav').read_bytes()
    assert (OUT/'take_2.csv').read_bytes()==(OUT/'take_12.csv').read_bytes()
    for path in (OUT/'stems').glob('take_2_*.wav'):
        assert path.read_bytes()==path.with_name(path.name.replace('take_2_','take_12_')).read_bytes()
    x,rate=sf.read(OUT/'take_2.wav',always_2d=True);sf.write(OUT/'audition_native_take.wav',x*.5,rate,subtype='PCM_24')
    # Version boundary is strict in both directions. Old files remain usable with V015.
    for exe,path in [(BUILD/'vsl_take_render.exe',ROOT/'renders/character_v1/high.vsltake'),
        (ROOT/'baselines/v0.15.0/bin/vsl_take_render.exe',take_path)]:
        p=subprocess.run([str(exe),str(path),str(OUT/'incompatible.wav')],capture_output=True)
        assert p.returncode==2 and not (OUT/'incompatible.wav').exists()
    unicode_path=OUT/'驾驶细节.vsltake';shutil.copy2(take_path,unicode_path)
    run([BUILD/'vsl_take_render.exe',unicode_path,OUT/'驾驶细节.wav'])
    assert (OUT/'驾驶细节.wav').read_bytes()==(OUT/'take_2.wav').read_bytes()
    run([BUILD/'vsl_render.exe',OUT/'scene_check.wav','--rpm','4000','--seconds','.2',
        '--pressure-texture','.731','--structure-transfer','.437','--scene',OUT/'scene.json'])
    scene=read_json(OUT/'scene.json');assert scene['parameters']['pressure_texture']==.731 and scene['parameters']['structure_transfer']==.437
    for option in ['--pressure-texture','--structure-transfer']:
        for value in ['nan','inf','-0.01','1.01','0.5junk','']:
            p=subprocess.run([str(BUILD/'vsl_render.exe'),str(OUT/'invalid.wav'),option,value],capture_output=True)
            assert p.returncode==1 and not (OUT/'invalid.wav').exists()
    preserved={}
    for name in ['core/dna.c','core/high_orders.c','core/exhaust_spectrum.c','profiles/high_orders.c']:
        path=ROOT/'src'/name;assert path.read_bytes()==(ROOT/'baselines/v0.11.0/src'/name).read_bytes();preserved[name]=sha(path)
    for folder in ['drive','spatial']:
        for path in (ROOT/'src'/folder).iterdir():
            if path.is_file():assert path.read_bytes()==(ROOT/'baselines/v0.15.0'/path.relative_to(ROOT)).read_bytes()
    for name,digest in history['binaries'].items():assert sha(ROOT/'build-v015/Release'/name)==digest
    assert (ROOT/'Launch.cmd').read_bytes()==(ROOT/'baselines/v0.15.0/Launch.cmd').read_bytes()
    result=dict(version='0.16.0',seed=48271,ctest_count=18,device=native,take=take_report,
        unchanged_default_templates=unchanged,unchanged_30s_drive=True,preserved_V011=preserved,
        recipe_comparisons=comparisons,layout_source_stems=10,strict_cross_version_rejection=True,
        audition_processing='Fixed .5 gain; PCM24; no normalization/denoise/filter/additional fades.',
        binaries={p.name:sha(p) for p in sorted(BUILD.glob('*.exe'))},
        subjective='Unaccepted experiment. Latest feedback asks for combustion and mechanical detail; no claimed realism improvement.')
    result['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Native controls/takes, frozen voicing, strict versions and ten stereo/7.1.4 sources verified.',flush=True)

def audit():
    r=read_json(OUT/'verification.json');assert r['version']=='0.16.0'
    for name,digest in r['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in r['binaries'].items():assert sha(BUILD/name)==digest,name
    history={}
    for folder in sorted((ROOT/'baselines').iterdir()):
        if folder.name=='v0.16.0' or not (folder/'manifest.json').exists():continue
        manifest=read_json(folder/'manifest.json')
        for item in manifest['files']:assert sha(folder/item['path'])==item['sha256'],str(folder/item['path'])
        history[folder.name]=len(manifest['files'])
    assert len(history)==18
    media={name:checked_source(name) for name in ['A','B']}
    experiment_binaries=read_json(ROOT/'renders/character_v1/results.json')['binaries']
    for name,digest in experiment_binaries.items():assert sha(ROOT/name)==digest,name
    sources=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    names=['README.md','AGENTS.md','.gitignore','Launch.cmd','Launch-character.cmd','build.ps1','references/segments_v1.json',
        'research/V016原生燃烧与机械细节.md','research/goal_progress_v016.json','research/upstream_head_v015.json',
        'tools/v016_probe.c','tools/verify_v016.py','tools/freeze_v016.py','tools/freeze_review.py',
        'tools/runtime_review.py','tools/review_audit.py','tools/reference_segments.py']
    a=dict(result='pass',version='0.16.0',ctest_count=18,approved_media=media,preserved_baselines=history,
        preserved_experiment_binaries=experiment_binaries,
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(sources)},
        deliverables={name:sha(ROOT/name) for name in names},
        rendered_artifacts={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='workspace_audit.json'},
        goal_status='active; optional live candidate integrated. New subjective acceptance and per-car identification remain incomplete.')
    (OUT/'workspace_audit.json').write_text(json.dumps(a,indent=2),encoding='utf-8')
    print('V016 audit pass; 18 historical snapshots preserved.',flush=True)

if __name__=='__main__':
    if '--audit' not in sys.argv:create()
    audit()
