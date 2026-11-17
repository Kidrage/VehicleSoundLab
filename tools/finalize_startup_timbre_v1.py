"""Freeze the actual startup source, editing workflow, failures and native output."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess

from event_authoring.native import Renderer
from startup_response_evidence_v1 import sha,verify


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    evidence=data/'renders/startup_timbre_v1';analysis=data/'references/analysis/startup_timbre_v1'
    kernel=read(evidence/'kernel1/report.json');regression=read(evidence/'regression1/report.json')
    delivery=read(evidence/'delivery1/report.json');workbench=read(evidence/'workbench3/report.json')
    ui=read(evidence/'ui1/report.json');web=read(evidence/'web2/report.json')
    assert all(r['result']=='passed' for r in (kernel,regression,delivery,workbench,ui,web))
    assert len(regression['cases'])==27 and len(kernel['material'])==8 and len(kernel['known'])==8
    assert ui['final_state']['underflows']==ui['restart_final_state']['underflows']==0
    assert delivery['continuous_19_channels_exact'] and delivery['after_3_seconds_all_23_channels_exact']
    for folder in ('regression1','delivery1','ui1'):
        verify(repo,read(evidence/folder/'source_binding.json'))
    renderer=Renderer(repo);assert renderer.identity==kernel['renderer_sha256']
    binaries={
        'source-v6':repo/'build-vehicle-source-v6/bin/Release/vsl_source_bridge.dll',
        'source-v5':repo/'build-vehicle-source-v5/bin/Release/vsl_source_bridge.dll',
        'author-v2':repo/'build-event-synth-v2/bin/Release/vsl_event_author_bridge.dll',
        'author-v1':repo/'build-event-synth-v1/bin/Release/vsl_event_author_bridge.dll'}
    expected=[kernel[k] for k in ('source_bridge_sha256','old_source_bridge_sha256','renderer_sha256','old_renderer_sha256')]
    assert list(map(sha,binaries.values()))==expected
    previous=data/'baselines/startup_abort_v1/delivery1';voice_files=[]
    for path in sorted((repo/'voices').rglob('*')):
        if path.is_file():
            name=path.relative_to(repo);assert sha(path)==sha(previous/'repo'/name),str(name)
            voice_files.append(name.as_posix())
    assert len(voice_files)==89
    checks={}
    for filename,count in [('event-build1.log',2),('source-build1.log',3)]:
        content=(analysis/filename).read_text(encoding='utf-8')
        assert '100% tests passed out of '+str(count) in content and '***Failed' not in content
        checks[filename]=dict(sha256=sha(analysis/filename),tests=count)
    reviewed=read(analysis/'review1/report.json')
    for name,digest in reviewed['files'].items():assert sha(analysis/'review1'/name)==digest,name
    for item in delivery['projects']['projects']:
        assert sha(item['parameters'])==item['profile_sha256']
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    report=dict(schema='vsl.startup-timbre-milestone/1',result='passed',previous_goal_turn='no_progress',
        current_goal_turn='progress',kernel=kernel,regression=regression,delivery=delivery,
        workbench=workbench,ui=ui,web=web,required_CTests=checks,voices_unchanged=voice_files,
        binaries={name:dict(path=str(path),sha256=sha(path)) for name,path in binaries.items()},
        review_url='http://127.0.0.1:8789/references/analysis/startup_timbre_v1/review1/index.html',
        finalizer_sha256=sha(__file__),documentation_sha256=sha(repo/'handoff/启动音色校准与控制台V6.md'),
        archive=str(a.output),goal_complete=False,timbre_accepted=False,
        unresolved=['Startup hearing','Real full-band afterfire and other event timbres','Remaining state/source coverage'],
        persistent_updated_launch=False,reason='Prior automatic approval rejected persistent launch/restart: blocked by policy',
        prior_failures=['gain-only response1','workbench1 reload race','workbench2 WAV timestamp comparison','ctest-unbuilt-targets.log'],
        note='Audit is a separate file; do not rewrite frozen files after creating the manifest.')
    (repo/'research/startup_timbre_v1_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    a.output.mkdir(parents=True,exist_ok=False)
    subprocess.run(['git','diff','--binary','--output='+str(a.output/'working-tree.patch')],cwd=repo,check=True)
    names=set()
    for command in [('diff','--name-only','-z'),('ls-files','--others','--exclude-standard','-z')]:
        names.update(name for name in subprocess.check_output(['git',*command],cwd=repo).decode('utf-8').split('\0') if name)
    names.update(row['path'] for row in read(evidence/'delivery1/source_binding.json')['files'])
    for name in sorted(names):
        source=repo/name
        if source.is_file():
            target=a.output/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for source,name in [(evidence,'evidence'),(analysis,'analysis')]:
        shutil.copytree(source,a.output/name,ignore=shutil.ignore_patterns('__pycache__'))
    for row in delivery['projects']['projects']:
        shutil.copytree(row['project_folder'],a.output/'editable-projects'/row['id'])
    for name,path in binaries.items():
        target=a.output/'binaries'/name/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    shutil.copy2(repo/'build-event-synth-v2/bin/Release/event-author-build.json',a.output/'binaries/author-v2/event-author-build.json')
    manifest=dict(schema='vsl.startup-timbre-freeze/1',created=datetime.now(timezone.utc).isoformat(),
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),goal_complete=False,timbre_accepted=False,
        files=[dict(path=f.relative_to(a.output).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(a.output.rglob('*')) if f.is_file()])
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='frozen',files=len(manifest['files']),bytes=sum(r['bytes'] for r in manifest['files']),output=str(a.output))))


if __name__=='__main__':main()
