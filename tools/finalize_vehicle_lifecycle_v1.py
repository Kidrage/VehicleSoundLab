"""Bind and archive lifecycle/UI/replay evidence without declaring timbre complete."""
import argparse
import ast
from collections import Counter
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1024**2),b''):digest.update(part)
    return digest.hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    root=data/'renders/vehicle_lifecycle_v1';previous=data/'baselines/event_designer_v1/delivery1'
    verified=read(root/'verification3/verification.json');ui=read(root/'ui2/report.json')
    edge=read(root/'replay_edges2/report.json');host=read(root/'host_replay2/report.json')
    web=read(root/'web2/report.json');endurance=read(root/'endurance1/report.json')
    assert all(row['passed'] for row in verified['checks'])
    assert ui['result']==web['result']==endurance['result']=='passed'
    assert all(host_case['passed'] for host_case in host['cases']) and edge['exact_notices'] and edge['exact_pcm']
    assert endurance['generated_seconds']==320 and endurance['one_engine_instance'] and not endurance['clock_reset']
    assert ui['event_notices_in_saved_take']==4 and ui['final_state']['underflows']==0
    for name in ('mix.wav','native.wav','telemetry.csv'):
        assert sha(root/'verification2'/name)==sha(root/'verification3'/name),name
    assert sha(repo/'tools/vehicle_controller/take.py')==edge['take_sha256']
    for name in ('tools/vehicle_controller/ui.py','tools/vehicle_controller/host.py','tools/vehicle_controller/take.py',
                 'tools/vehicle_scenarios/scenario.py'):
        assert sha(repo/name)==sha(root/'ui2/exact_sources'/name),name
    tree=ast.parse((repo/'tools/vehicle_controller/ui.py').read_text(encoding='utf-8'))
    window=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Window')
    assert max(Counter(n.name for n in window.body if isinstance(n,ast.FunctionDef)).values())==1
    view=data/'references/analysis/vehicle_lifecycle_v1/review2';view_data=read(view/'manifest.json')
    assert sha(view/'mix.wav')==sha(root/'verification3/mix.wav')
    with (root/'verification3/telemetry.csv').open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    expected=[[float(r['seconds']),float(r['rpm']),float(r['speed_mps'])*3.6,int(r['gear']),
               r['lifecycle_name'],r['operating_name'],float(r['throttle_request']),float(r['brake_request']),
               float(r['idle_weight']),int(r['overruns'])] for r in rows[::4]]
    assert expected==view_data['telemetry']
    old_manifest=read(previous/'manifest.json');dll=repo/'build-vehicle-source-v3/bin/Release/vsl_source_bridge.dll'
    assert sha(dll)==verified['bridge_sha256']==old_manifest['source_bridge_sha256']
    unchanged=[]
    for source in sorted((repo/'voices').rglob('*')):
        if source.is_file():
            relative=source.relative_to(repo);assert sha(source)==sha(previous/'repo'/relative)
            unchanged.append(relative.as_posix())
    assert len(unchanged)==89
    report=dict(schema='vsl.vehicle-lifecycle-milestone/1',date=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='no progress: repeated source/render boundary confirmation, no implementation change',
        this_goal_turn='progress: full lifecycle demo/UI, actual event recording, dense-control replay fixes, native/endurance verification and original-source context evidence',
        goal_complete=False,timbre_accepted=False,bridge_sha256=verified['bridge_sha256'],
        voices_sha256=verified['voices_sha256'],event_bank_sha256=verified['event_bank_sha256'],unchanged_voice_files=unchanged,
        capture=dict(folder=str(root/'verification3'),checks=verified['checks'],frames=verified['frames'],
            pcm_sha256=verified['pcm_sha256'],native_reconstruction_error=verified['native_reconstruction_error'],
            latest_capture_mix_native_and_telemetry_exact_previous=True),
        dense_replay=edge,host_replay=host,ui=ui,web=web,endurance=endurance,
        review=dict(path=str(view/'index.html'),url='http://127.0.0.1:8789/references/analysis/vehicle_lifecycle_v1/review2/index.html',
            actual_http_status=200,app_open_result='queued',matches_current_capture=True),
        materials=dict(context_report=str(data/'references/analysis/event_sources_v1/contexts1/report.json'),
            global_bank_modified=False,new_downloads=False,new_fits=False,
            F3_103_465='Unclassified cabin driving transient, +7.0164dB measured contrast. Physical event type not confirmed.',
            G1_G2_G3='User review pending; metadata only, not downloaded'),
        failures_retained=[str(root/'replay_edges1/report.json'),str(root/'host_replay1/report.json'),str(root/'ui1')],
        limitations=['Only unaccepted real-A mixed-cabin crank/catch event profiles are available.',
            'Afterfire, shift, engage, disengage and stop one-shot material profiles remain unavailable.',
            'Startup/idle transition listening question is pending. No new hearing acceptance inferred.',
            'Offline 320s repeated cycles do not establish device soak, real afterfire concurrency or ADI qualification.',
            'ui1 has no terminal report/traceback; saved take and screenshots retained, host failure separately reproduced.',
            'Persistent launch/restart was previously rejected by automatic approval: blocked by policy. No workaround used.',
            'No core DSP change, deep optimization, spatial work, new commit or push.'])
    (repo/'research/vehicle_lifecycle_v1_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    a.output.mkdir(parents=True,exist_ok=False)
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    subprocess.run(['git','diff','--binary','--output='+str(a.output/'working-tree.patch')],cwd=repo,check=True)
    selected=set()
    for args in [('diff','--name-only','-z'),('ls-files','--others','--exclude-standard','-z')]:
        selected.update(s for s in subprocess.check_output(['git',*args],cwd=repo).decode('utf-8').split('\0') if s)
    for name in ('tools/vehicle_controller','tools/vehicle_scenarios','tools/event_authoring','tools/event_designer',
                 'tools/sound_designer','modules/vehicle_source','modules/vehicle_input','modules/event_control',
                 'modules/event_synth','experiments/vehicle_source_v1','experiments/event_synth_v1','voices'):
        selected.update(p.relative_to(repo).as_posix() for p in (repo/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for name in sorted(selected):
        source=repo/name
        if source.is_file():
            target=a.output/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    shutil.copy2(dll,a.output/dll.name)
    shutil.copytree(root,a.output/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(view,a.output/'review')
    shutil.copytree(data/'references/analysis/event_sources_v1/contexts1',a.output/'source_contexts')
    shutil.copy2(previous/'manifest.json',a.output/'previous_delivery_manifest.json')
    manifest=dict(schema='vsl.vehicle-lifecycle-delivery/1',created=datetime.now(timezone.utc).isoformat(),
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        goal_complete=False,timbre_accepted=False,bridge_sha256=verified['bridge_sha256'],
        voices_sha256=verified['voices_sha256'],event_bank_sha256=verified['event_bank_sha256'],
        previous_manifest_sha256=sha(previous/'manifest.json'),limitations=report['limitations'],
        files=[dict(path=p.relative_to(a.output).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
               for p in sorted(a.output.rglob('*')) if p.is_file()])
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in manifest['files']:assert sha(a.output/row['path'])==row['sha256']
    print(json.dumps(dict(output=str(a.output),files=len(manifest['files']),bytes=sum(r['bytes'] for r in manifest['files']),
        goal_complete=False,unchanged_voice_files=len(unchanged)),ensure_ascii=False))


if __name__=='__main__':main()
