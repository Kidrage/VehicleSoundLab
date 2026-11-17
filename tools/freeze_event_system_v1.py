"""Freeze source, parameter candidates, binaries and exact verification evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    checks=data/'renders/event_system_v1/verification1';verified=json.loads((checks/'verification.json').read_text(encoding='utf-8'))
    assert verified['ui'] and verified['replay_pcm_exact'] and verified['replay_event_notices_exact'] and verified['native_channels']==23
    a.output.mkdir(parents=True,exist_ok=False)
    subprocess.run(['git','diff','--binary','--output='+str(a.output/'working-tree.patch')],cwd=repo,check=True)
    selected=set()
    for args in [('diff','--name-only','-z'),('ls-files','--others','--exclude-standard','-z')]:
        selected.update(x for x in subprocess.check_output(['git',*args],cwd=repo).decode('utf-8').split('\0') if x)
    for folder in ('modules/vehicle_source','modules/vehicle_input','modules/event_synth','modules/event_control',
                   'tools/vehicle_controller','tools/event_authoring','experiments/vehicle_source_v1','experiments/event_synth_v1','voices'):
        selected.update(path.relative_to(repo).as_posix() for path in (repo/folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    for name in sorted(selected):
        source=repo/name
        if not source.is_file():continue
        target=a.output/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    dll=repo/'build-vehicle-source-v2/bin/Release/vsl_source_bridge.dll'
    assert sha(dll)==verified['bridge_sha256'];shutil.copy2(dll,a.output/dll.name)
    for name in ('event_synth_probe','event_synth_checks','event_control_checks'):
        shutil.copy2(repo/'build-event-synth-v1/bin/Release'/(name+'.exe'),a.output/(name+'.exe'))
    for source,label in [(checks,'verification1'),(data/'references/analysis/event_authoring_v1','authoring'),
        (data/'references/analysis/event_sources_v1','source-inspection'),(data/'renders/event_system_v1/launch1','launch-attempt')]:
        if source.is_dir():shutil.copytree(source,a.output/'evidence'/label,ignore=shutil.ignore_patterns('__pycache__'))
    source_log=data/'renders/vehicle_controller_v1/source-event-build1.log'
    shutil.copy2(source_log,a.output/'source-event-build1.log')
    manifest=dict(schema='vsl.event-system-milestone/1',goal_complete=False,timbre_accepted=False,
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        bridge_sha256=verified['bridge_sha256'],voices_sha256=verified['voices_sha256'],event_bank_sha256=verified['event_bank_sha256'],
        available_mask=6,native_channels=23,
        limitations=['Only A mixed-cabin early-start/catch candidates compiled; no approved new afterfire/mechanical voice.',
                     'No new persistent service/window launched: automatic approval rejected restart and independent-port launch.',
                     'No DSP optimization/ADI qualification; full source system and sound acceptance remain incomplete.'],
        files=[dict(path=path.relative_to(a.output).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
               for path in sorted(a.output.rglob('*')) if path.is_file()])
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(a.output),files=len(manifest['files']),bytes=sum(row['bytes'] for row in manifest['files']),goal_complete=False)))


if __name__=='__main__':main()
