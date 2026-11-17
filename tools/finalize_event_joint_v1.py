"""Freeze the optional authoring repair, preserving old voices and failed attempts."""
import argparse
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha
from startup_response_evidence_v1 import verify


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    args=parser.parse_args();repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    root=data/'references/analysis/event_joint_v1';base=data/'baselines/startup_contour_v1/delivery1'
    checks={key:load(root/path) for key,path in dict(author='verification2/report.json',
        audit='audit3/report.json',workbench='web1/verification.json',startup='startup1/report.json',
        review='review-web3/verification.json').items()}
    assert all(r['result']=='passed' for r in checks.values())
    assert checks['author']['runtime_and_voices_unchanged']==459
    frozen=base/'evidence/verification1/exact_sources'
    runtime=[p for group in ('src','modules','voices') for p in (repo/group).rglob('*')
        if p.is_file() and (p.suffix in ('.c','.h') or group=='voices')]
    assert len(runtime)==459 and all(sha(p)==sha(frozen/p.relative_to(repo)) for p in runtime)
    verify(repo,load(root/'startup1/source_binding.json'))
    for key in ('A','B'):
        doc=load(root/f'verification2/{key}/analysis/profile.json')
        assert doc['parameters']==load(root/f'probe1/{key}/profile.json')
        assert doc['fit']['source_response_fit']['qualified'] and doc['fit']['contour_fit']['qualified']
        assert all(all(b['passed'] for b in s['original_six_spectral_gates'])
            for c in checks['audit']['cases'] if c['key']==key for s in c['seeds'])
    refusal=next((root/'verification2/workspace').glob('*/project.json'))
    assert load(refusal)['analysis']['refusal_kind']=='contour_fit'
    for variant in ('original','candidate'):
        assert all(load(root/f'startup1/{variant}/verification.json')['checks'].values())
    tracks=load(root/'review1/tracks.json');assert len(tracks)==10
    for track in tracks:assert sha(root/'review1'/track['file'])==track['sha256'] and track['gain']==.25
    assert all((root/p).is_file() for p in ['verification1/executed_verification.py',
        'audit1/executed_audit.py','review-web1/executed_verification.py','review-web2/executed_verification.py'])
    for run in ('verification1','verification2','audit1','audit2','audit3','web1','startup1','review-web1','review-web2','review-web3'):
        source=data/f'references/analysis/event_joint_v1_{run}.log'
        if source.is_file():
            target=root/'logs'/source.name;target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
    basis=data/'references/analysis/event_basis_v1/probe1'
    assert load(basis/'target_consistency.json')
    if not (root/'diagnosis1').exists():shutil.copytree(basis,root/'diagnosis1')
    paths={'AGENTS.md','handoff/当前代码阅读入口.md','handoff/事件可靠频段联合提参V1.md',
        'tools/author_event.py','tools/event_designer/workspace.py','tools/research_archive_v1.py',
        'tools/startup_response_evidence_v1.py','tools/audit_startup_shape_v1.py','tools/audit_startup_contour_v1.py',
        'tools/verify_startup_contour_review_v1.cjs','tools/verify_startup_handoff_review_v1.py'}
    paths.update(p.relative_to(repo).as_posix() for p in (repo/'tools/event_authoring').glob('*.py'))
    paths.update(p.relative_to(repo).as_posix() for p in (repo/'tools').glob('*event_joint*v1*') if p.is_file())
    paths.add('tools/probe_event_basis_v1.py')
    paths.update('tools/sound_designer/web/'+p for p in ('events.js','events.html','events.css','event_contours.js'))
    masters={k:sha(data/f'references/clean/{k}_decoded_float.wav') for k in ('A','B')}
    assert masters['A']=='34885942c450127932a25c72a63fdeae59026f30cfe3678a7aba6b1f5f87b964'
    assert masters['B']==load(data/'references/analysis/B_startup_context_v1/crank-hold-author1/profile.json')['provenance']['sha256']
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    milestone=dict(schema='vsl.event-joint-authoring-milestone/1',result='passed',
        previous_goal_turn='No synthesis progress: confirmed generator/render scope and budget',
        current_goal_turn='Optional reliable-band joint authoring implemented, actual A/B C outputs and workbench/full-startup integration verified',
        method='band-contour-v2',job_schema=6,source_ABI=11,author_ABI=4,preset_schema=7,take_schema=8,
        bridge_sha256=checks['startup']['bridge_sha256'],author_bridge_sha256=checks['author']['author_bridge_sha256'],
        runtime_C_H_changed=[],formal_voices_unchanged=89,master_sha256=masters,checks=checks,
        source_files={p:sha(repo/p) for p in sorted(paths)},
        freeze=str(args.freeze),base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),
        retained_failures=['verification1 unsynchronized metadata equality assertion',
            'audit1 overbroad comparison against published A, not the actual entry-profile contract',
            'review-web1 verifier argument order, review-web2 old six-track assertion'],
        unresolved=['A high-band curve slightly worse than published candidate',
            'B high-band fine texture remains imperfect','startup mechanical quality','idle natural variation',
            'confirmed full-band afterfire/other event timbres','full RPM/load/state coverage'],
        timbre_accepted=False,physical_rpm_measured=False,goal_complete=False,
        persistent_service_restarted=False,new_download=False,push=False,spatial_added=False,ADI_optimization=False)
    save(repo/'research/event_joint_v1_verification.json',milestone)
    paths.add('research/event_joint_v1_verification.json');args.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(paths):
        target=args.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    shutil.copytree(root,args.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    save(args.freeze/'base.json',dict(base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),
        runtime_C_H_and_voices='unchanged; use V12 base',source_ABI=11,author_ABI=4,goal_complete=False))
    rows=[dict(path=p.relative_to(args.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json',dict(schema='vsl.event-joint-authoring-delta-freeze/1',
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),files=rows,goal_complete=False))
    print(dict(result='frozen',files=len(rows),bytes=sum(r['bytes'] for r in rows),manifest_sha256=sha(args.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
