"""Validate actual firing denial, native lifecycle, strict takes and source layout."""
import csv
import json
import shutil
import subprocess
from runtime_review import ROOT,sha,rms
from review_audit import device
import numpy as np
import soundfile as sf
from PIL import Image

OUT=ROOT/'renders/v0.17.0'
DIAG=ROOT/'renders/firing_permission_v1'
BUILD=ROOT/'build-v017/Release'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def run(args):
    return subprocess.run(list(map(str,args)),cwd=ROOT,check=True,capture_output=True,text=True,timeout=90).stdout


def rows(path):
    with path.open() as f:return list(csv.DictReader(f))


def create():
    if (OUT/'verification.json').exists() or (ROOT/'baselines/v0.17.0').exists():raise SystemExit('Preserve completed V017.')
    native=read(OUT/'ui_smoke.json');device(native,'0.17.0')
    for key in ['character_controls','character_preset_roundtrip','character_legacy_preset','character_active_on_device',
        'propagation_control','propagation_preset_roundtrip','propagation_active_on_device']:assert native[key],key
    take_report=read(OUT/'ui_take_smoke.json');take=take_report['result']
    assert take_report['character_state_match']==take_report['device_character_state_match']==1
    for key in ['saved','loaded','offline_hash_match','final_drive_state_match','device_replay_hash_and_state_match',
        'manual_replay_stop','controls_locked','muted']:assert take[key]==1,key
    assert take['replay_queue_empty']==0 and .95<take['replay_device_seconds']/take['replay_wall_seconds']<1.02
    assert all(read(OUT/'ui_take_controls.json').values())
    for path in OUT.glob('*.bmp'):
        with Image.open(path) as image:image.save(path.with_suffix('.png'))
    log=ROOT/'build-v017/Testing/Temporary/LastTest.log';assert log.read_bytes().count(b'Test Passed.')==19
    assert b'fired_event_permission' in log.read_bytes();shutil.copy2(log,OUT/'ctest.log')
    default={}
    for profile in range(5):
        files=[]
        for tag in ['v016','v017']:
            path=OUT/f'{tag}_default_profile_{profile}.wav'
            run([ROOT/f'build-{tag}/Release/vsl_render.exe',path,'--profile',profile,'--rpm','4000','--load','.65','--seconds','3'])
            files.append(path)
        assert files[0].read_bytes()==files[1].read_bytes()
        default[str(profile)]=sha(files[1])
    comparisons={};auditions={}
    changed_columns={'fired_strikes','mechanical_stored_energy','character_structure'}
    for scenario in ['shutdown','cut','steady']:
        records={tag:read(DIAG/f'{tag}_{scenario}.json') for tag in ['v016','v017']}
        old=records['v016'];new=records['v017'];assert new['disallowed_fired_strikes']==0
        if scenario!='steady':assert old['disallowed_fired_strikes']>0
        assert old['rotational_strikes_without_fire_permission']==new['rotational_strikes_without_fire_permission']
        assert old['character_events']==new['character_events']
        traces=[rows(DIAG/f'{tag}_{scenario}.csv') for tag in ['v016','v017']]
        assert len(traces[0])==len(traces[1])==800
        assert all(all(a[k]==v for k,v in b.items() if k not in changed_columns) for a,b in zip(*traces))
        differences={}
        for suffix,label,boost in [('', 'full',1),('_mechanical','mechanical',10**(24/20))]:
            arrays=[]
            for tag in ['v016','v017']:
                x,sr=sf.read(DIAG/f'{tag}_{scenario}{suffix}.wav',always_2d=True)
                assert sr==48000 and len(x)==192000 and np.isfinite(x).all();arrays.append(x)
            assert np.array_equal(arrays[0][:96000],arrays[1][:96000])
            if scenario=='steady':assert np.array_equal(*arrays)
            delta=arrays[1]-arrays[0]
            peak=float(abs(delta).max())
            differences[label]=dict(difference_peak=peak,difference_rms_dbfs=rms(delta) if peak else None,
                difference_to_original_rms_db=rms(delta)-rms(arrays[0]) if peak else None,pre_transition_float_equal=True)
            if scenario!='steady':
                gain=.5*boost;assert max(float(abs(x*gain).max()) for x in arrays)<.85
                entry={}
                for tag,x in zip(['v016','v017'],arrays):
                    fade=np.ones(len(x));fade[:240]=np.arange(240)/239;fade[-240:]=np.arange(239,-1,-1)/239
                    y=x*gain*fade[:,None];path=OUT/f'audition_{scenario}_{label}_{tag}.wav';sf.write(path,y,48000,subtype='PCM_24')
                    actual,_=sf.read(path,always_2d=True);assert abs(actual-y).max()<=2**-23+1e-12
                    entry[tag]=dict(file=path.name,sha256=sha(path),gain_db=float(20*np.log10(gain)),
                        solo_boost_relative_to_full_db=0 if label=='full' else 24,endpoint_fade_ms=5)
                auditions[scenario+'_'+label]=entry
        comparisons[scenario]=dict(records=records,unchanged_trace_columns=sorted(set(traces[0][0])-changed_columns),
            allowed_trace_difference_columns=sorted(changed_columns),differences=differences)
    stem_folder=OUT/'stems';stem_folder.mkdir(exist_ok=True);take_path=OUT/'ui_take_smoke.vsltake'
    for channels in [2,12]:
        run([BUILD/'vsl_take_render.exe',take_path,OUT/f'take_{channels}.wav','--channels',channels,
            '--trace',OUT/f'take_{channels}.csv','--stems',stem_folder/f'take_{channels}'])
    assert (OUT/'take_2.wav').read_bytes()==(OUT/'ui_take_smoke.wav').read_bytes()
    assert (OUT/'take_2.csv').read_bytes()==(OUT/'take_12.csv').read_bytes()
    stem_count=0
    for path in stem_folder.glob('take_2_*.wav'):
        assert path.read_bytes()==path.with_name(path.name.replace('take_2_','take_12_')).read_bytes();stem_count+=1
    assert stem_count==10
    for exe,path in [(BUILD/'vsl_take_render.exe',ROOT/'renders/v0.16.0/ui_take_smoke.vsltake'),
        (ROOT/'build-v016/Release/vsl_take_render.exe',take_path)]:
        target=OUT/'incompatible.wav';p=subprocess.run([str(exe),str(path),str(target)],cwd=ROOT,capture_output=True)
        assert p.returncode==2 and not target.exists()
    preserved={};changed={}
    expected_changes={'CMakeLists.txt','AGENTS.md','build.ps1','src/core/types.h','src/core/mechanical_modal.c','src/core/character.c',
        'src/drive/fueling.c','src/drive/fueling.h','src/app/main.c','src/app/take_smoke.c','tests/test_mechanical.c'}
    old_manifest=read(ROOT/'baselines/v0.16.0/manifest.json')
    for item in old_manifest['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','Launch.cmd','Launch-character.cmd','build.ps1','AGENTS.md']:
            digest=sha(ROOT/name)
            if digest==item['sha256']:preserved[name]=digest
            else:changed[name]=dict(v016=item['sha256'],v017=digest)
    assert set(changed)==expected_changes,(set(changed)^expected_changes)
    assert len(preserved)+len(changed)==144
    native_versions={}
    for version,tag in [('0.15.0','v015'),('0.16.0','v016')]:
        historical=read(ROOT/f'renders/v{version}/verification.json')
        for name,digest in historical['binaries'].items():assert sha(ROOT/f'build-{tag}/Release'/name)==digest
        native_versions[version]=historical['binaries']
    for name in ['src/core/dna.c','src/core/high_orders.c','src/core/exhaust_spectrum.c','src/profiles/high_orders.c']:
        assert sha(ROOT/name)==sha(ROOT/'baselines/v0.11.0'/name)
    history={p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))};assert len(history)==28
    result=dict(version='0.17.0',seed=48271,ctest_count=19,device=native,take=take_report,
        unchanged_default_templates=default,firing_permission_comparisons=comparisons,auditions=auditions,
        layout_source_stems_identical=stem_count,strict_V016_V017_take_boundary=True,
        V016_contract_files_unchanged=preserved,V016_contract_files_intentionally_changed=changed,
        previous_native_binaries_unchanged=native_versions,previous_snapshot_manifest_identities=history,
        binaries={p.name:sha(p) for p in sorted(BUILD.iterdir()) if p.suffix in ['.exe','.lib']},
        diagnostic_inputs={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(DIAG.iterdir()) if p.is_file()},
        diagnostic_probes={p.relative_to(ROOT).as_posix():sha(p) for p in
            [ROOT/'build-diagnose-firing-permission-v016/Release/firing_permission_probe.exe',
             ROOT/'build-diagnose-firing-permission-v017/Release/firing_permission_probe.exe']},
        audition_processing='Fixed .5 gain, or .5 times24dB explicitly labelled mechanical solo boost;5ms linear endpoints;PCM24. No normalization, denoise, compression or HP.',
        subjective='Native event-permission correctness fix. It does not establish the principal electronic-timbre cause or perceptual improvement; existing character recipe stays optional.')
    result['files']={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(result='pass',version='0.17.0',ctests=19,unchanged_source_contracts=len(preserved),intentionally_changed_contracts=len(changed),
        scenarios={k:dict(old=v['records']['v016']['disallowed_fired_strikes'],new=v['records']['v017']['disallowed_fired_strikes'],
            mix_difference_db=v['differences']['full']['difference_to_original_rms_db']) for k,v in comparisons.items()},
        device_ratio=native['device_seconds']/native['wall_seconds'],stereo_714_source_stems=10),indent=2))


def audit():
    result=read(OUT/'verification.json');assert result['version']=='0.17.0'
    for name,digest in result['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in result['binaries'].items():assert sha(BUILD/name)==digest,name
    for group in ['diagnostic_inputs','diagnostic_probes']:
        for name,digest in result[group].items():assert sha(ROOT/name)==digest,name
    sources=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    names=['README.md','AGENTS.md','.gitignore','Launch.cmd','Launch-character.cmd','Launch-current.cmd','build.ps1',
        'research/V017燃烧事件许可.md','research/goal_progress_v017.json','research/v6_control_snapshot.json',
        'tools/verify_v017.py','tools/freeze_v017.py','tools/freeze_review.py','tools/runtime_review.py','tools/review_audit.py',
        'tools/v016_probe.c','experiments/firing_permission_v1/CMakeLists.txt','experiments/firing_permission_v1/probe.c']
    names+=list(result['diagnostic_inputs'])+list(result['diagnostic_probes'])
    audit=dict(result='pass',version='0.17.0',ctest_count=19,
        source_code={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(sources)},
        deliverables={name:sha(ROOT/name) for name in sorted(set(names))},
        rendered_artifacts={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='workspace_audit.json'},
        goal_status='active; native event gate fixed, calibrated timbre and array listening incomplete')
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print('V017 source/deliverable audit passed. Broad goal remains active.')


if __name__=='__main__':
    import sys
    if '--audit' in sys.argv:audit()
    else:create()
