"""Bind the successful full build to legacy WAV checks and real muted device IO."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--proof',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def save():
    (a.out/'report.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


r=dict(result='running',commands=[],legacy=[],timbre_accepted=False,native_UI_interaction_or_visual_verified=False)


def run(label,argv):
    argv=list(map(str,argv));started=time.perf_counter()
    done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=240)
    log=a.out/(label+'.log');log.write_bytes(done.stdout+done.stderr)
    row=dict(label=label,argv=argv,exit=done.returncode,seconds=time.perf_counter()-started,log_sha256=sha(log))
    r['commands'].append(row);save();print(json.dumps(row),flush=True)
    if done.returncode:raise RuntimeError(str(log))


try:
    shutil.copy2(__file__,a.out/'executed_audit.py')
    proof=load(a.proof/'report.json');assert proof['result']=='passed' and proof['tests']==59 and proof['phase']=='all'
    for name,digest in proof['sources'].items():assert sha(repo/name)==sha(a.proof/'exact_sources'/name)==digest,name
    r.update(build_proof_sha256=sha(a.proof/'report.json'),source_sha256=sha(Path(__file__)))
    binary=repo/'build-idle-drive-v1/bin/Release';(a.out/'bin').mkdir()
    for name in ['VslAtlasMonitor.exe','idle_drive_device.exe','VslAtlasDrive_probe.exe','idle_owned_checks.exe','idle_control_checks.exe']:
        shutil.copy2(binary/name,a.out/'bin'/name)
    r['binaries']={path.name:sha(path) for path in (a.out/'bin').iterdir()}
    old=a.workspace/'references/analysis/drive_resonance_v1/before1';snapshot=load(old/'snapshot.json')
    folder=a.out/'legacy';folder.mkdir()
    for case in snapshot['cases']:
        options=case['options']+(['--stereo-bed','1'] if case['name'].startswith('E_') else [])
        run(case['name'],[a.out/'bin/VslAtlasDrive_probe.exe',*case['models'][:2],folder/case['name'],*options])
        original=sorted((old/'renders').glob(case['name']+'_*.wav'));assert len(original)==28
        for path in original:
            assert sha(path)==snapshot['files'][path.relative_to(old).as_posix()]
            assert path.read_bytes()==(folder/path.name).read_bytes(),path.name
        name=case['name']+'_trace.csv';assert (old/'renders'/name).read_bytes()==(folder/name).read_bytes()
        r['legacy'].append(dict(case=case['name'],WAV_bytes_exact=28,driver_CSV_exact=True));save()
    device=a.out/'device';device.mkdir()
    run('muted_device',[a.out/'bin/idle_drive_device.exe',device])
    observed=load(device/'device.json');assert observed['result']=='pass' and observed['schema']==9 and observed['fields']==30
    assert observed['frames']==384123 and observed['record_hash']==observed['play_hash']
    assert observed['external_models_destroyed'] and observed['two_twelve_front_and_source_exact']
    assert observed['record_queue_empty']==observed['play_queue_empty']==0
    r.update(result='typed_idle_owned_controls_legacy_audio_and_muted_device_verified',tests=59,
        device=observed,device_report_sha256=sha(device/'device.json'),source_timbre_refitted=False,
        default_executable_replaced=False,actual_F2_RPM_calibrated=False,physical_7_1_4_verified=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save()
