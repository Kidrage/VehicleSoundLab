"""Bind executed ensemble authoring evidence and preserve an explicit parent delta."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    args=parser.parse_args();assert not args.freeze.exists()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    root=data/'references/analysis/event_ensemble_v1';base=data/'baselines/short_event_authoring_v1/delivery1'
    assert sha(base/'manifest.json')=='140ab1fef0a3edb386f1d6e24c7cc43d1e4daca508ea88418dbc05fe762e5de8'
    assert load(data/'references/analysis/short_event_scan_v1/delivery-audit1/report.json')['result']=='passed'
    names=dict(probe='probe1/report.json',author='author1/report.json',workbench='web1/report.json',
        long_windows='B-long1/report.json',comparison='review3/report.json',independent='audit2/report.json',
        review_browser='review-web2/report.json',published='published-review.json',header='header1/report.json')
    checks={key:load(root/name) for key,name in names.items()};assert all(r['result']=='passed' for r in checks.values())
    assert checks['workbench']['own_server_closed'] and checks['review_browser']['own_service_closed']
    assert checks['header']['all_compiled_numeric_fields_exact'] and checks['header']['fields']==186
    assert load(root/'audit1/report.json')['result']=='failed'
    assert load(root/'audit1/diagnosis.json')['old_numbers_reproduced_exactly']
    assert not checks['long_windows']['answer'] and not any(r['qualified'] for r in checks['long_windows']['cases'])
    counts={r['name']:{variant:sum(t['qualified'] for t in r[variant]) for variant in ('single','ensemble')}
            for r in checks['comparison']['cases']}
    assert counts==dict(A_crank=dict(single=8,ensemble=8),A_catch=dict(single=8,ensemble=8),B_rank6=dict(single=4,ensemble=8))
    runtime={p.relative_to(repo).as_posix():sha(p) for group in ('src','modules','voices')
        for p in (repo/group).rglob('*') if p.is_file() and (p.suffix in ('.c','.h') or group=='voices')}
    assert runtime==load(data/'references/analysis/short_event_scan_v1/runtime.json') and len(runtime)==459
    bridge=repo/'build-vehicle-source-v12/bin/Release/vsl_source_bridge.dll'
    assert sha(bridge)=='97cff42c3244d15f4a48e11026737e92a6427bcdb8201a944ed9e6f33f577b9f'
    for case,paths in {
        'probe1':['tools/event_authoring/response_ensemble.py'],
        'author1':['tools/author_event.py','tools/event_designer/workspace.py','tools/verify_event_ensemble_authoring_v1.py'],
        'web1':['tools/sound_designer/web/events.js','tools/sound_designer/web/events.html','tools/verify_event_ensemble_workbench_web_v1.cjs'],
        'review3':['tools/build_event_ensemble_review_v1.py']}.items():
        for name in paths:assert sha(repo/name)==sha(root/case/'exact_sources'/name),name
    pictures=['web1/desktop-qualified.png','web1/desktop-refused.png','web1/mobile-method.png','web1/mobile-controls.png',
        'review3/review/bands.png','review-web2/browser/desktop.png','review-web2/browser/mobile.png']
    save(root/'visual-review.json',dict(result='passed',method='Images opened by agent; actual mobile controls inspected',
        files={name:sha(root/name) for name in pictures},
        observations=['New method selector, envelope exclusion and qualified/refused readouts readable',
            'Native mobile transport and method selector stay inside viewport',
            'Final material-window chart shows A8/8 both, B4/8 to8/8; earlier gated-window claim retracted']))
    save(root/'runtime.json',runtime)
    sources={'AGENTS.md','handoff/当前代码阅读入口.md','handoff/事件多次触发联合提参V1.md',
        'research/event_ensemble_v1_plan.json','examples/event_authoring/A_catch_ensemble.job.json',
        'tools/author_event.py','tools/probe_event_ensemble_v1.py','tools/verify_event_ensemble_authoring_v1.py',
        'tools/verify_event_ensemble_workbench_v1.py','tools/verify_event_ensemble_workbench_web_v1.cjs',
        'tools/probe_event_long_context_v1.py','tools/build_event_ensemble_review_v1.py',
        'tools/verify_event_ensemble_review_v1.py','tools/audit_event_ensemble_v1.py',
        'tools/verify_event_parameter_header_v1.py','tools/finalize_event_ensemble_v1.py',
        'tools/audit_event_ensemble_delivery_v1.py','tools/research_archive_v1.py','tools/event_review.py',
        'tools/verify_short_event_review_v1.cjs'}
    for directory in ('tools/event_authoring','tools/event_designer'):
        sources.update(p.relative_to(repo).as_posix() for p in (repo/directory).glob('*.py'))
    sources.update('tools/sound_designer/web/'+name for name in ('events.html','events.js','events.css'))
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    milestone=dict(schema='vsl.event-ensemble-milestone/1',result='passed',goal_complete=False,
        previous_goal_turn='No synthesis progress: generation/render budget boundary confirmation',
        current_goal_turn='Optional4training+4heldout event authoring through actual C, editable UI and independently audited paired comparisons',
        checks={key:dict(path=str(root/name),sha256=sha(root/name),result='passed') for key,name in names.items()},
        source_files={name:sha(repo/name) for name in sorted(sources)},runtime_files=runtime,
        runtime_voice_files_unchanged=459,formal_voices_unchanged=89,source_ABI=11,author_ABI=4,profile_bytes=1408,
        ui_revision=13,preset_schema=8,take_schema=9,bridge_sha256=sha(bridge),
        author_bridge_sha256=checks['author']['author_DLL_sha256'],C_python_max_error_FS=checks['independent']['C_python_max_error'],
        paired_eight_seed_qualifications=counts,refused_B_rank3=True,fixed_200ms_B_qualified=0,
        retracted='review1/2 startup6/8 count used a gated safety horizon; correct material-window result8/8. Original evidence and audit1 failure retained.',
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),freeze=str(args.freeze),
        physical_afterfire_confirmed=False,new_timbre_accepted=False,vehicle_profile_replaced=False,
        new_download=False,commit_or_push=False,spatial_added=False,ADI_optimization=False,persistent_service_restarted=False,
        unresolved=['complete confirmed physical afterfire and other event timbres','startup/idle mechanical naturalness',
            'full RPM/load/state coverage','protect adopted exterior startup temporal contours before ensemble integration'])
    save(repo/'research/event_ensemble_v1_verification.json',milestone);sources.add('research/event_ensemble_v1_verification.json')
    args.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(sources):
        target=args.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    shutil.copytree(root,args.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc','build'))
    entries=[dict(path=p.relative_to(args.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json',dict(schema='vsl.event-ensemble-delta-freeze/1',base_freeze=str(base),
        base_manifest_sha256=sha(base/'manifest.json'),files=entries,goal_complete=False))
    print(dict(result='frozen',files=len(entries),bytes=sum(r['bytes'] for r in entries),manifest_sha256=sha(args.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
