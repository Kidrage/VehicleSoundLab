"""Freeze the optional adaptive event authoring and actual C/UI evidence."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha
from startup_response_evidence_v1 import verify


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    args=parser.parse_args();repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    root=data/'references/analysis/event_knots_v1';base=data/'baselines/event_joint_v1/delivery1'
    checks={key:load(root/path) for key,path in dict(author='verification1/report.json',audit='audit1/report.json',
        workbench='web2/verification.json',startup='startup1/report.json',review='review-web1/verification.json').items()}
    assert all(r['result']=='passed' for r in checks.values())
    runtime=[p for group in ('src','modules','voices') for p in (repo/group).rglob('*')
        if p.is_file() and (p.suffix in ('.c','.h') or group=='voices')]
    old=base/'evidence/startup1/exact_sources'
    assert len(runtime)==459 and all(sha(p)==sha(old/p.relative_to(repo)) for p in runtime)
    verify(repo,load(root/'startup1/source_binding.json'))
    for key in ('A','B'):
        document=load(root/f'verification1/{key}/analysis/profile.json')
        assert document['source_job']['schema']=='vsl.event-authoring-job/7'
        fit=document['fit']['contour_fit'];assert fit['adaptive_selected'] and fit['qualified']
        assert all(all(b['passed'] for b in s['original_six_spectral_gates'])
            for c in checks['audit']['cases'] if c['key']==key for s in c['seeds'])
    for variant in ('original','candidate'):assert all(load(root/f'startup1/{variant}/verification.json')['checks'].values())
    tracks=load(root/'review1/tracks.json');assert len(tracks)==10
    for row in tracks:assert row['gain']==.25 and sha(root/'review1'/row['file'])==row['sha256']
    assert 'np' in (root/'choices2/executed_probe.py').read_text(encoding='utf-8')
    for run in ('probe1','choices1','choices2','choices3','verification1','audit1','web1','web2','startup1','review-web1'):
        file=data/f'references/analysis/event_knots_v1_{run}.log'
        if file.is_file():
            target=root/'logs'/file.name;target.parent.mkdir(exist_ok=True);shutil.copy2(file,target)
    for name in ('probe_event_knot_choices_v1.py','event_authoring/contour_knots.py'):
        target=root/'choices3'/('executed_'+Path(name).name);shutil.copy2(repo/'tools'/name,target)
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    sources={'AGENTS.md','handoff/当前代码阅读入口.md','handoff/启动自适应控制点提参V1.md',
        'tools/author_event.py','tools/event_designer/workspace.py','tools/event_review.py',
        'tools/verify_event_joint_startup_v1.py','tools/verify_event_joint_review_v1.py',
        'tools/verify_event_joint_web_v1.cjs','tools/verify_startup_contour_review_v1.cjs',
        'tools/verify_startup_handoff_review_v1.py','tools/research_archive_v1.py','tools/startup_response_evidence_v1.py',
        'tools/audit_event_joint_delivery_v1.py','tools/audit_startup_shape_v1.py','tools/audit_startup_contour_v1.py'}
    sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools/event_authoring').glob('*.py'))
    sources.update(p.relative_to(repo).as_posix() for p in (repo/'tools').glob('*event_knot*v1*') if p.is_file())
    sources.update('tools/sound_designer/web/'+name for name in ('events.js','events.html','events.css','event_contours.js'))
    milestone=dict(schema='vsl.adaptive-event-knots-milestone/1',result='passed',
        previous_goal_turn='Progress: optional reliable-band joint authoring and full startup verified/frozen',
        current_goal_turn='Adaptive coarse knot authoring, per-band layout selection, exact-value UI readouts and actual C/workbench/full-startup verification',
        checks=checks,source_ABI=11,author_ABI=4,profile_bytes=1408,preset_schema=7,take_schema=8,
        runtime_and_voices_unchanged=len(runtime),formal_voices_unchanged=89,
        source_files={name:sha(repo/name) for name in sorted(sources)},
        freeze=str(args.freeze),base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),
        editable_parameters=checks['workbench']['actual_parameters'],
        retained_limitations=['A mid-band normalized shape slightly worse than V2; high band and aggregate score improve',
            'one unscaled A float seed peak about1.079FS retained; all audition uses fixed.25 gain/no limiter',
            'choices2 probe missing numpy import retained; no signal gate relaxation',
            'single fixed crop/fit seed per material, not mechanical identity/RPM or held-out engine qualification'],
        new_timbre_accepted=False,goal_complete=False,ADI_optimization=False,spatial_added=False,
        new_download=False,commit_or_push=False,persistent_service_restarted=False,
        unresolved=['startup mechanical fine texture','idle naturalness','confirmed full-band afterfire',
            'other event timbres','full RPM/load/state coverage'])
    save(repo/'research/event_knots_v1_verification.json',milestone);sources.add('research/event_knots_v1_verification.json')
    args.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(sources):
        target=args.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    shutil.copytree(root,args.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    rows=[dict(path=p.relative_to(args.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json',dict(schema='vsl.adaptive-event-knots-delta-freeze/1',base_freeze=str(base),
        base_manifest_sha256=sha(base/'manifest.json'),files=rows,goal_complete=False))
    print(dict(result='frozen',files=len(rows),bytes=sum(r['bytes'] for r in rows),manifest_sha256=sha(args.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
