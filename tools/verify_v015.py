"""Build V015 evidence from actual native recording, CLI replay and frozen V014."""
import json
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from runtime_review import ROOT, sha, render, smoke
from review_audit import device, frozen_baselines, read_json
from reference_segments import checked_source
import soundfile as sf
import numpy as np
from PIL import Image

OUT = ROOT/'renders/v0.15.0'
BUILD = ROOT/'build-v015'
EXE = BUILD/'Release/vsl_render.exe'
COUNTS = dict(zip([f'v0.{v}.0' for v in range(1,15)],
    [23,64,81,99,112,161,157,182,190,205,189,156,167,175]))


def run(args):
    return subprocess.run([str(x) for x in args],cwd=ROOT,check=True,capture_output=True,text=True,timeout=60).stdout


def create():
    if (OUT/'verification.json').exists():
        raise SystemExit('Preserve completed V015 artifacts; use --audit to recheck hashes and refresh the audit.')
    OUT.mkdir(parents=True,exist_ok=True)
    hashes = {name:sha(BUILD/'Release'/name) for name in
        ['VehicleSoundLab.exe','vsl_render.exe','vsl_take_render.exe','vsl_spatial_probe.exe']}
    native = smoke(BUILD,OUT,'0.15.0');device(native,'0.15.0')
    for name in ['ui_take_smoke.vsltake','ui_take_smoke.wav','ui_take_smoke.json','ui_take_controls.json',
        'ui_control_roundtrip.ini','ui_legacy_preset.ini','ui_v08_preset.ini','ui_v013_preset.ini']:
        shutil.copy2(ROOT/'renders'/name,OUT/name)
    with Image.open(ROOT/'renders/ui_take_replay.bmp') as im:
        im.save(OUT/'ui_take_controls_locked.png')
    take = read_json(OUT/'ui_take_smoke.json')
    for key in ['saved','loaded','offline_hash_match','final_drive_state_match','device_replay_hash_and_state_match',
        'manual_replay_stop','controls_locked','muted']:
        assert take[key] == 1,key
    assert take['replay_queue_empty']==0 and .95<take['replay_device_seconds']/take['replay_wall_seconds']<1.02
    assert all(read_json(OUT/'ui_take_controls.json').values())
    autosave = max((ROOT/'performances').glob('*.vsltake'),key=lambda p:p.stat().st_mtime)
    assert autosave.read_bytes()==(OUT/'ui_take_smoke.vsltake').read_bytes()
    shutil.copy2(BUILD/'Testing/Temporary/LastTest.log',OUT/'ctest.log')
    assert (OUT/'ctest.log').read_bytes().count(b'Test Passed.')==17
    replay = {}; (OUT/'stems').mkdir(exist_ok=True)
    for channels in [2,12]:
        args = [BUILD/'Release/vsl_take_render.exe',OUT/'ui_take_smoke.vsltake',OUT/f'take_{channels}.wav',
            '--channels',channels,'--trace',OUT/f'take_{channels}.csv','--stems',OUT/f'stems/take_{channels}']
        replay[str(channels)] = dict(command=[str(a) for a in args],stdout=run(args))
        info = sf.info(OUT/f'take_{channels}.wav')
        assert info.subtype=='FLOAT' and info.channels==channels and info.frames==take['frames']
    assert (OUT/'take_2.wav').read_bytes()==(OUT/'ui_take_smoke.wav').read_bytes()
    assert (OUT/'take_2.csv').read_bytes()==(OUT/'take_12.csv').read_bytes()
    stems = sorted((OUT/'stems').glob('take_2_*.wav'));assert len(stems)==10
    for path in stems:
        assert path.read_bytes()==path.with_name(path.name.replace('take_2_','take_12_')).read_bytes()
        assert sf.info(path).subtype=='FLOAT' and sf.info(path).channels==1
    x,rate=sf.read(OUT/'take_2.wav',always_2d=True)
    assert np.isfinite(x).all() and rate==48000
    sf.write(OUT/'audition_take.wav',x*.5,rate,subtype='PCM_24')
    # Exercise Unicode paths in the new serializer/CLI without altering the file.
    unicode_file = OUT/'驾驶操作.vsltake';shutil.copy2(OUT/'ui_take_smoke.vsltake',unicode_file)
    replay['unicode'] = run([BUILD/'Release/vsl_take_render.exe',unicode_file,OUT/'驾驶回放.wav'])
    assert (OUT/'驾驶回放.wav').read_bytes()==(OUT/'take_2.wav').read_bytes()
    legacy={}
    for profile in range(5):
        target=OUT/f'profile_{profile}.wav'
        render(EXE,target,['--profile',str(profile),'--rpm','4000','--load','.65','--seconds','3'],'0.15.0')
        frozen=ROOT/f'renders/v0.14.0/legacy_profile_{profile}_v014.wav'
        assert target.read_bytes()==frozen.read_bytes()
        legacy[str(profile)]=sha(target)
    args=['--scenario','auto','--seconds','30','--width','.8','--propagation','1']
    render(EXE,OUT/'drive_propagation.wav',args,'0.15.0',['--trace',str(OUT/'drive.csv')])
    assert (OUT/'drive_propagation.wav').read_bytes()==(ROOT/'renders/v0.14.0/drive_propagation.wav').read_bytes()
    assert (OUT/'drive.csv').read_bytes()==(ROOT/'renders/v0.14.0/drive_propagation.csv').read_bytes()
    dna = run([sys.executable,ROOT/'tools/check_dna_pipeline.py','--renderer',EXE,'--out',OUT/'dna_check'])
    assert read_json(OUT/'dna_check/dna_pipeline_check.json')['result']=='pass'
    run([sys.executable,ROOT/'tools/check_dna_pipeline.py','--renderer',ROOT/'baselines/v0.14.0/bin/vsl_render.exe','--out',OUT/'dna_frozen_v014'])
    assert (OUT/'dna_check/DNA_中文路径验证.wav').read_bytes()==(OUT/'dna_frozen_v014/DNA_中文路径验证.wav').read_bytes()
    request=urllib.request.Request('https://api.github.com/repos/Kidrage/VehicleSoundSynth/commits/HEAD',headers={'User-Agent':'VehicleSoundLab-local-research'})
    with urllib.request.urlopen(request,timeout=20) as response:
        head=json.load(response)
    upstream=dict(sha=head['sha'],message=head['commit']['message'].splitlines()[0],
        checked_utc=datetime.now(timezone.utc).isoformat(),source=request.full_url,
        snapshot_sha256=sha(ROOT/'research/upstream_v6/code/drive_model.js'),
        unchanged_from_v014=head['sha']=='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',
        local_extension='Deterministic driving input takes; source/control algorithms retained from V014. Not an upstream capture module.')
    (ROOT/'research/upstream_head_v015.json').write_text(json.dumps(upstream,indent=2),encoding='utf-8')
    for name,digest in hashes.items():assert sha(BUILD/'Release'/name)==digest
    result=dict(version='0.15.0',seed=48271,binaries=hashes,device=native,take=take,replay=replay,
        unicode_paths=True,source_stems=10,legacy_templates=legacy,unchanged_30s_drive=True,
        autosave_sha256=sha(autosave),autosave_path=str(autosave.relative_to(ROOT)),
        audition=dict(file='audition_take.wav',gain_db=-6.020599913279624,processing='Fixed gain .5; PCM24; no normalization, denoise, filtering or added fades.'),
        dna_pipeline_stdout=dna,upstream=upstream)
    result['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Native take, replay, all five frozen templates and 30 s drive verified.',flush=True)


def audit():
    r=read_json(OUT/'verification.json');assert r['version']=='0.15.0'
    for name,digest in r['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in r['binaries'].items():assert sha(BUILD/'Release'/name)==digest,name
    # No source-voice or drive implementation changed in this release.
    for folder in ['core','drive','profiles','spatial']:
        for path in (ROOT/'src'/folder).iterdir():
            if not path.is_file():continue
            old=ROOT/'baselines/v0.14.0'/path.relative_to(ROOT)
            if path.name=='types.h' and folder=='core':
                assert path.read_bytes().replace(b'0.15.0',b'0.14.0')==old.read_bytes()
            else:assert sha(path)==sha(old),path
    history=frozen_baselines(COUNTS)
    media={name:checked_source(name) for name in ['A','B']}
    old=read_json(ROOT/'research/goal_progress_v014.json')
    old.update(review_version='0.15.0',implemented_this_iteration=[
        'Fresh-session driving capture at actual audio block input frames; effective DNA and IR embedded',
        'Strict bounded portable protocol, transactional I/O and dedicated auto-save folder',
        'Simple native record/save/replay controls; locked replay and restored live state',
        '17 passing tests; complete native/offline stereo hash and drive-state reconstruction',
        'Stereo/7.1.4 source stems and driving traces match; five templates and 30 s V014 drive byte-identical'],
        subjective_review='No timbre changes. V011/V013/V014 subjective evaluation remains pending; software replay correctness does not establish vehicle realism.',
        evidence=dict(review='research/V015驾驶录制.md',audit='renders/v0.15.0/workspace_audit.json',verification='renders/v0.15.0/verification.json'))
    old['full_objective_audit'][4]['status']+=' V015 additionally captures/reconstructs actual driving inputs and effective assets; this is not completion of the full simulator.'
    (ROOT/'research/goal_progress_v015.json').write_text(json.dumps(old,indent=2),encoding='utf-8')
    sources=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    deliverables=['README.md','AGENTS.md','.gitignore','Launch.cmd','build.ps1','references/segments_v1.json',
        'research/V015驾驶录制.md','research/upstream_head_v015.json','research/goal_progress_v015.json',
        'tools/verify_v015.py','tools/freeze_v015.py','tools/freeze_review.py','tools/runtime_review.py',
        'tools/review_audit.py','tools/reference_segments.py','tools/check_dna_pipeline.py','tools/analyze_audio.py']
    a=dict(result='pass',version='0.15.0',ctest_count=17,approved_media=media,preserved_baselines=history,
        deterministic_take=r['take'],source_stem_count=10,unchanged_templates=5,unchanged_full_drive_trace=True,
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(sources)},
        deliverables={name:sha(ROOT/name) for name in deliverables},
        rendered_artifacts={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='workspace_audit.json'},
        goal_status='active; take capture/replay complete, subjective sound, identified car model and actual 7.1.4 listening remain incomplete')
    (OUT/'workspace_audit.json').write_text(json.dumps(a,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',version='0.15.0',ctests=17,take_frames=r['take']['frames'],events=r['take']['events'],history=history),indent=2))


if __name__=='__main__':
    if '--audit' not in sys.argv:create()
    audit()
