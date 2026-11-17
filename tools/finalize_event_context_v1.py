"""Independently audit fixed-window evidence and freeze the authoring delta."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from event_authoring.audio import sha
from event_designer.context import export_evidence
from event_designer.workspace import EventWorkspace
from event_designer.package import write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    a=parser.parse_args();repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    work=data/'references/analysis/event_context_workbench_v1'
    verified=json.loads((work/'verification5/report.json').read_text(encoding='utf-8'));assert verified['result']=='passed'
    regression=json.loads((work/'response-regression2/report.json').read_text(encoding='utf-8'));assert regression['result']=='passed'
    for file in (work/'verification5/exact_sources').rglob('*'):
        if file.is_file():assert sha(file)==sha(repo/file.relative_to(work/'verification5/exact_sources')),str(file)
    ws=EventWorkspace(repo,work/'verification5/browser-projects/events')
    p=ws.view(verified['browser']['project_id']);e=export_evidence(p)
    assert e['matches_current_selection'] and not e['matches_model_event_and_before_background']
    base=data/'baselines/startup_timbre_v1/delivery1'
    manifest=json.loads((base/'manifest.json').read_text(encoding='utf-8'));old=[]
    for row in manifest['files']:
        rel=row['path']
        if rel.startswith('repo/') and (rel.endswith(('.c','.h')) or rel.startswith('repo/voices/')):
            assert sha(repo/rel[5:])==row['sha256'],rel
            old.append(rel)
    binaries={
        'build-vehicle-source-v6/bin/Release/vsl_source_bridge.dll':'d6e383857365705bc60f6f4a4271c1c5a1793c0e3b485b4fb5a342dd990ebeb4',
        'build-event-synth-v2/bin/Release/vsl_event_author_bridge.dll':'2043597cb96ab7902431bebb84ed2552ccf30277ace8d9160663ca357819fed1'}
    assert all(sha(repo/file)==digest for file,digest in binaries.items())
    scanroot=data/'references/analysis/approved_event_scan_v1'
    scan=json.loads((scanroot/'B_middle1/report.json').read_text(encoding='utf-8'))
    assert sha(scan['source'])==scan['source_sha256']
    errors=[];independent=[]
    with sf.SoundFile(scan['source']) as stream:
        assert stream.samplerate==48000
        for row in scan['candidates']:
            powers={}
            for key in ('event','before','after'):
                first,last=[round(t*48000) for t in row[key+'_seconds']]
                stream.seek(first);x=stream.read(last-first,dtype='float64',always_2d=True)
                powers[key]=float(np.sum(x*x)/x.size)
            ratios={key:float(10*np.log10(max(powers['event'],1e-30)/max(powers[key],1e-30))) for key in ('before','after')}
            errors.extend(abs(ratios[key]-row['contrast_db'][key]) for key in ratios)
            assert row['both_full_band_above_3db']==all(v>=3 for v in ratios.values())
            independent.append(dict(seconds=row['source_seconds'],powers=powers,contrasts=ratios))
    assert len(independent)==322 and max(errors)<1e-10
    qualified=[r for r in scan['candidates'] if r['both_full_band_above_3db']];assert len(qualified)==13
    boundaries=[b['retain_seconds'][0] for b in scan['blocks']]
    assert all(min(abs(r['source_seconds']-b) for b in boundaries)>.1 for r in qualified)
    timeline=json.loads((scanroot/'B_contexts1/report.json').read_text(encoding='utf-8'));assert len(timeline['cases'])==13
    delivery=json.loads((work/'delivery1/report.json').read_text(encoding='utf-8'));assert len(delivery['projects'])==4
    for item in delivery['projects']:
        project=json.loads((Path(item['project_folder'])/'project.json').read_text(encoding='utf-8'))
        assert project['document'] is None and not item['parameters_available']
    summary=dict(schema='vsl.event-context-workbench-milestone/1',result='passed',previous_goal_turn='no_progress',current_goal_turn='progress',
        scan=dict(ranges=scan['requested_ranges'],candidates=322,both_backgrounds_above_3db=13,confirmed_afterfires=0,
                  independent_all_window_power_audit=True,max_contrast_error_db=max(errors),qualified_near_block_edges=False,
                  source_sha256=scan['source_sha256']),
        editable_diagnostic_projects=[dict(id=p['project_id'],name=p['name']) for p in delivery['projects']],
        browser=verified['browser'],known_antiphase_and_PCM=verified['result'],legacy_response_regression=regression,
        scoped_context_cannot_claim_full_model_provenance=True,
        frozen_C_H_and_voice_subset_exact=len(old),voice_files_exact=sum(p.startswith('repo/voices/') for p in old),
        runtime_binaries_exact=binaries,source_C_changed=False,ABI_changed=False,formal_event_bank_changed=False,
        persistent_app_restarted=False,owned_test_services_closed=True,new_download=False,timbre_accepted=False,goal_complete=False,
        pending='Startup hearing, true full-band afterfire and other event material/quality, complete multi-state vehicle acceptance.',
        base_freeze=str(base),base_freeze_manifest_sha256=sha(base/'manifest.json'),authoring_delta_freeze=str(a.freeze))
    write_json(repo/'research/event_context_workbench_v1_verification.json',summary)
    auditroot=work/'audit1';auditroot.mkdir(exist_ok=False)
    write_json(auditroot/'scan-window-audit.json',dict(result='passed',cases=independent,max_contrast_error_db=max(errors)))
    shutil.copy2(__file__,auditroot/'executed_finalizer.py')
    a.freeze.mkdir(parents=True,exist_ok=False)
    selections=['tools/event_authoring','tools/event_designer','tools/sound_designer','tools/inspect_event_timeline_v1.py',
                'tools/scan_approved_event_region.py','tools/verify_event_context_workbench_v1.py',
                'tools/verify_event_context_ui_v1.cjs','tools/build_event_context_delivery_v1.py',
                'tools/finalize_event_context_v1.py','tools/verify_event_response_workbench_v1.py','tools/verify_event_response_ui_v1.cjs',
                'handoff/事件素材核查与工作台V2.md','handoff/当前代码阅读入口.md',
                'research/event_context_workbench_v1_verification.json','examples/event_authoring/E_exhaust_return_full.job.json','AGENTS.md']
    for relative in selections:
        source=repo/relative;target=a.freeze/'repo'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if source.is_dir():shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:shutil.copy2(source,target)
    for source,name in [(work,'workbench-evidence'),(scanroot,'approved-scan-evidence'),
                        (data/'references/analysis/exhaust_full_v1','exhaust-rejection-evidence')]:
        shutil.copytree(source,a.freeze/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for relative in binaries:
        target=a.freeze/'binaries'/Path(relative).name;target.parent.mkdir(exist_ok=True);shutil.copy2(repo/relative,target)
    files=[dict(path=p.relative_to(a.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(a.freeze.rglob('*')) if p.is_file()]
    frozen=dict(schema='vsl.event-context-authoring-delta-freeze/1',created=datetime.now(timezone.utc).isoformat(),
                base_freeze=str(base),base_manifest_sha256=summary['base_freeze_manifest_sha256'],goal_complete=False,files=files)
    write_json(a.freeze/'manifest.json',frozen)
    # Reopen and hash copied bytes, not just the source list used during copying.
    loaded=json.loads((a.freeze/'manifest.json').read_text(encoding='utf-8'))
    assert all(sha(a.freeze/r['path'])==r['sha256'] and (a.freeze/r['path']).stat().st_size==r['bytes'] for r in loaded['files'])
    output=dict(result='passed',files=len(files),bytes=sum(r['bytes'] for r in files),manifest_sha256=sha(a.freeze/'manifest.json'))
    write_json(a.freeze.parent/(a.freeze.name+'-audit.json'),output);print(json.dumps(output))


if __name__=='__main__':main()
