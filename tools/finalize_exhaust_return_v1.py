"""Freeze exact sources, local E event, negative evidence and full-cycle replay."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from startup_response_evidence_v1 import sha, verify


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    evidence=data/'renders/exhaust_return_v1';analysis=data/'references/analysis/exhaust_return_v1'
    review=read(analysis/'review1/report.json');cycle=read(evidence/'cycle2/verification.json')
    ui=read(evidence/'verification3/report.json');material=read(evidence/'material1/report.json')
    web=read(evidence/'web1/report.json');cycle_web=read(evidence/'cycle-web4/report.json')
    file_web=read(evidence/'cycle-file-web1/report.json');context_check=read(evidence/'context-check2/report.json')
    assert all(x['result']=='passed' for x in (ui,material,web,cycle_web,file_web,context_check))
    assert cycle['passed'] and all(r['passed'] for r in cycle['checks']) and cycle['final_state']['lifecycle']==0
    assert len(cycle['afterfire_starts'])==1 and ui['automatic_afterfire_starts']==4 and ui['final_state']['underflows']==0
    assert material['all_four_tested_seeds_within_3db'] and not review['physical_identity_confirmed']
    assert sha(evidence/'cycle-web4/executed_verification.cjs')==cycle_web['verifier_sha256']==sha(repo/'tools/verify_exhaust_cycle_web_v1.cjs')
    for label,report in (('verification3',ui),('cycle2',cycle)):
        folder=evidence/label;assert sha(folder/'source_binding.json')==report['source_binding_sha256']
        binding=read(folder/'source_binding.json');verify(repo,binding)
        for row in binding['files']:assert sha(folder/'exact_sources'/row['path'])==row['sha256'],row['path']
    assert sha(analysis/'review1/executed_build.py')==sha(repo/'tools/build_exhaust_return_v1.py')
    assert sha(evidence/'cycle2/executed_build.py')==sha(repo/'tools/build_exhaust_return_cycle_v1.py')
    for name,digest in review['files'].items():assert sha(analysis/'review1'/name)==digest,name
    assert sha(analysis/'review1/app.js')==sha(repo/'tools/exhaust_return_review_web_v1.js')
    for name in ('app.js','style.css','index.html'):
        assert sha(analysis/'cycle-review2'/name)==sha(repo/'tools/vehicle_scenarios/web'/name)
    context=read(analysis/'context1/report.json')
    assert context['backgrounds'][0]['observation']==read(analysis/'fit1/profile.json')['observation']
    assert not context['fit_performed'] and abs(context['sample_peak_seconds']-13.309145833333334)<1e-12
    assert sha(analysis/'review1/event-profile.json')==sha(analysis/'cycle-review2/event-profile.json')
    previous=data/'baselines/startup_response_v1/delivery1'
    unchanged={}
    for folder in ('src','modules','voices'):
        files=[p for p in (repo/folder).rglob('*') if p.is_file() and
               (folder=='voices' or p.suffix in ('.c','.h'))]
        for path in files:assert sha(path)==sha(previous/'repo'/path.relative_to(repo)),str(path)
        unchanged[folder]=len(files)
    assert unchanged['voices']==89
    binaries={name:repo/path for name,path in (
        ('source-v4','build-vehicle-source-v4/bin/Release/vsl_source_bridge.dll'),
        ('event-author','build-event-synth-v1/bin/Release/vsl_event_author_bridge.dll'))}
    assert sha(binaries['source-v4'])==review['bridge_sha256']==cycle['bridge_sha256']
    assert sha(binaries['event-author'])==material['renderer_sha256']
    assert sha(binaries['source-v4'])==sha(previous/'binaries/source-v4/vsl_source_bridge.dll')
    assert sha(binaries['event-author'])==sha(previous/'binaries/event-author-preserved/vsl_event_author_bridge.dll')
    report=dict(schema='vsl.exhaust-return-milestone/1',created=datetime.now(timezone.utc).isoformat(),
        previous_goal_turn='no progress: source-only MCPS scope confirmation',
        this_goal_turn='progress: reusable two-background probe, scoped E event into actual C automatic lift, full32s lifecycle, controller visibility, HTTP seek repair and verified replay',
        goal_complete=False,timbre_accepted=False,physical_identity_confirmed=False,
        source_bridge_sha256=sha(binaries['source-v4']),author_bridge_sha256=sha(binaries['event-author']),
        unchanged_since_startup_delivery=unchanged,voice_bank_sha256=review['voices_sha256'],
        source_job=review['source_job'],project=review['project'],context_probe=context,
        single_event_and_lift=review,material=material,ui=ui,cycle=cycle,
        web=web,cycle_web=cycle_web,file_web=file_web,context_check=context_check,
        review_url='http://127.0.0.1:8789/references/analysis/exhaust_return_v1/review1/index.html',
        cycle_url='http://127.0.0.1:8789/references/analysis/exhaust_return_v1/cycle-review2/index.html',
        global_bank_changed=False,new_downloads=False,spatial_processing=False,compute_optimization=False,
        limitations=[
            'E candidate only1.2..14kHz acoustic increment, no LF/full-band reconstruction or confirmed afterfire identity/listening.',
            'Single-event C inserted at crop start; original transient peak is about24ms later, not onset/waveform alignment.',
            'A crank/catch are still unaccepted mixed-cabin acoustic candidates; formal bank remains mask6.',
            '32s C pedal trajectory is engineering demonstration, not video RPM/fuel telemetry reproduction.',
            'Formal engage/disengage/shift/stop and full-band afterfire profiles remain unavailable.',
            'Four-seed fit/bounded muted device checks do not prove all-seed quality, long-run realtime or ADI MCPS.',
            'Original E_screen1/E_detail1 adhoc implementation was not saved; context1 newly reproduces13.31 only with retained source.',
            'cycle-web1 real HTTP seek failure retained; web2 verifier failed to await adopted track; web3 corrected test passes.',
            'Early failed browser verifier scripts were not snapshotted; their reports/screenshots survive. Final web4 stores exact executed verifier.',
            'context-check1 Windows GBK decode failure retained as text; context-check2 explicitly UTF8 passes.',
            'Persistent updated launch/restart remains unexecuted after earlier automatic rejection blocked by policy; no bypass.',
            'G1/G2/G3 download approvals and other listening requests pending; no repeated request or inferred approval.',
            'No commit or push; worktree includes earlier uncommitted work and is preserved.'
        ])
    (repo/'research/exhaust_return_v1_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    a.output.mkdir(parents=True,exist_ok=False)
    subprocess.run(['git','diff','--binary','--output='+str(a.output/'working-tree.patch')],cwd=repo,check=True)
    names=set()
    for args in [('diff','--name-only','-z'),('ls-files','--others','--exclude-standard','-z')]:
        names.update(x for x in subprocess.check_output(['git',*args],cwd=repo).decode('utf-8').split('\0') if x)
    names.update(r['path'] for r in read(evidence/'verification3/source_binding.json')['files'])
    for name in sorted(names):
        source=repo/name
        if source.is_file():
            target=a.output/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    shutil.copytree(evidence,a.output/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(analysis,a.output/'analysis')
    sources=data/'references/analysis/event_sources_v1'
    for name in ('timelines4/E_exterior_revs','E_screen1','E_detail1'):
        shutil.copytree(sources/name,a.output/'original-context'/name)
    for name,binary in binaries.items():
        target=a.output/'binaries'/name/binary.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(binary,target)
    rejection=data/'renders/event_system_v1/launch1/approval-rejections.json'
    shutil.copy2(rejection,a.output/'prior-launch-rejections.json')
    manifest=dict(schema='vsl.exhaust-return-delivery/1',created=datetime.now(timezone.utc).isoformat(),
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        goal_complete=False,timbre_accepted=False,
        files=[dict(path=p.relative_to(a.output).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
               for p in sorted(a.output.rglob('*')) if p.is_file()])
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for row in manifest['files']:
        file=a.output/row['path'];assert file.stat().st_size==row['bytes'] and sha(file)==row['sha256']
    print(json.dumps(dict(output=str(a.output),files=len(manifest['files']),bytes=sum(r['bytes'] for r in manifest['files']),
        unchanged=unchanged,goal_complete=False),ensure_ascii=False))


if __name__=='__main__':main()
