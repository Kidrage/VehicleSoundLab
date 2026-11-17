"""Freeze the actual authoring/vehicle milestone; keep incomplete goal status."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''):digest.update(chunk)
    return digest.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab');evidence=data/'renders/event_designer_v1'
    author=json.loads((evidence/'verification4/verification.json').read_text(encoding='utf-8'))
    vehicle=json.loads((evidence/'flow2/verification.json').read_text(encoding='utf-8'))
    assert author['result']==vehicle['result']=='passed' and author['generated_C_header_compiles_and_parameters_exact']
    assert author['test_server_closed'] and vehicle['replay_pcm_exact'] and vehicle['replay_notices_exact']
    source_dll=repo/'build-vehicle-source-v3/bin/Release/vsl_source_bridge.dll'
    author_dll=repo/'build-event-synth-v1/bin/Release/vsl_event_author_bridge.dll'
    assert sha(source_dll)==vehicle['bridge_sha256'] and sha(author_dll)==author['renderer_sha256']
    assert b'100% tests passed' in (evidence/'source-final-build.log').read_bytes()
    old=data/'baselines/event_system_v1/delivery2/repo/voices'
    frozen=list(old.rglob('*'));voice_files=[f for f in frozen if f.is_file()]
    assert len(voice_files)==89 and all(sha(f)==sha(repo/'voices'/f.relative_to(old)) for f in voice_files)
    a.output.mkdir(parents=True,exist_ok=False)
    subprocess.run(['git','diff','--binary','--output='+str(a.output/'working-tree.patch')],cwd=repo,check=True)
    selected=set()
    for args in [('diff','--name-only','-z'),('ls-files','--others','--exclude-standard','-z')]:
        selected.update(x for x in subprocess.check_output(['git',*args],cwd=repo).decode('utf-8').split('\0') if x)
    for folder in ('modules/vehicle_source','modules/vehicle_input','modules/event_synth','modules/event_control',
                   'tools/vehicle_controller','tools/event_authoring','tools/event_designer','tools/sound_designer',
                   'experiments/vehicle_source_v1','experiments/event_synth_v1','voices'):
        selected.update(path.relative_to(repo).as_posix() for path in (repo/folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    for name in sorted(selected):
        source=repo/name
        if source.is_file():
            target=a.output/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for source in (source_dll,author_dll,author_dll.with_name('event-author-build.json')):
        shutil.copy2(source,a.output/source.name)
    # Keep authoritative passing runs and failed reports. Compiler intermediates are reproducible.
    for name in ('verification1','verification2','verification3','verification4','flow1','flow2','examples1'):
        shutil.copytree(evidence/name,a.output/'evidence'/name,ignore=shutil.ignore_patterns('build','__pycache__'))
    for source in evidence.glob('*.log'):shutil.copy2(source,a.output/'evidence'/source.name)
    examples=json.loads((evidence/'examples1/examples.json').read_text(encoding='utf-8'))
    for project in examples['projects']:
        shutil.copytree(project['folder'],a.output/'examples'/project['id'],ignore=shutil.ignore_patterns('__pycache__'))
    manifest=dict(schema='vsl.event-designer-delivery/1',created=datetime.now(timezone.utc).isoformat(),
        goal_complete=False,timbre_accepted=False,base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        source_bridge_abi=4,source_bridge_sha256=vehicle['bridge_sha256'],author_bridge_sha256=author['renderer_sha256'],
        native_channels=23,unchanged_voice_files=89,voices_sha256=vehicle['voices_sha256'],
        previous_goal_turn='no implementation progress: source/render boundary confirmation only',
        this_goal_turn='progress: event workbench, C preview, per-engine profiles, recipe/take replay, verification and delivery',
        limitations=['Real startup candidates await hearing; other five event types lack validated material profiles.',
            'Synthetic afterfire verification fixture is not shipped in the global bank.',
            'G1/G2/G3 metadata reviewed only; user download approval is pending.',
            'No persistent updated UI launched: prior automatic approval rejected launch/restart with blocked by policy.',
            'First browser verifier source was not separately frozen; original failure reports and final sources are retained.',
            'No deep DSP optimization, ADI timing qualification or completed full-lifecycle sound acceptance.'],
        files=[dict(path=f.relative_to(a.output).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(a.output.rglob('*')) if f.is_file()])
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in manifest['files']:assert sha(a.output/row['path'])==row['sha256']
    print(json.dumps(dict(output=str(a.output),files=len(manifest['files']),bytes=sum(r['bytes'] for r in manifest['files']),goal_complete=False)))


if __name__=='__main__':main()
