"""Bind short-event tool, raw source checks and failures; freeze a V13 delta."""
import argparse
from pathlib import Path
import shutil
import subprocess

import numpy as np
import soundfile as sf

from event_authoring.audio import read
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    args=parser.parse_args();assert not args.freeze.exists()
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    root=data/'references/analysis/short_event_scan_v1'
    base=data/'baselines/catalog_asset_identity_v1/delivery1'
    assert sha(base/'manifest.json')=='c0bbb4dc82dad2508208655492a7a15bf4eb78f374e3d06fb7daea4e6b9273e8'
    names=dict(detector='probe2/report.json',author='author2/report.json',workbench='web6/report.json',
        legacy='legacy-regression1/report.json',material='B-fits2/report.json',review='review-web1/report.json',
        header='header1/report.json',published='published-review.json')
    checks={key:load(root/name) for key,name in names.items()}
    assert all(c['result']=='passed' for c in checks.values())
    assert checks['workbench']['own_server_closed'] and checks['review']['own_service_closed']
    assert checks['author']['short']['source_free_C_exact'] and checks['workbench']['source_free_C_PCM_exact']
    assert checks['header']['actual_compiled_header_fields_exact']
    old=load(data/'references/analysis/low_mid_event_scan_v1/before/runtime.json')
    current={p.relative_to(repo).as_posix():sha(p) for group in ('src','modules','voices')
        for p in (repo/group).rglob('*') if p.is_file() and (p.suffix in ('.c','.h') or group=='voices')}
    assert current==old and len(current)==459
    bridge=repo/'build-vehicle-source-v12/bin/Release/vsl_source_bridge.dll'
    assert sha(bridge)=='97cff42c3244d15f4a48e11026737e92a6427bcdb8201a944ed9e6f33f577b9f'
    scan=load(root/'B-scan1/report.json');assert len(scan['candidates'])==334
    assert sum(row['both_full_band_above_3db'] for row in scan['candidates'])==28
    assert sha(scan['source'])==scan['source_sha256']
    # Recompute every reported fixed-window power directly from the approved master.
    with sf.SoundFile(scan['source']) as stream:
        for row in scan['candidates']:
            powers={}
            for key in ('event','before','after'):
                first,last=(round(v*48000) for v in row[key+'_seconds'])
                stream.seek(first);x=stream.read(last-first,dtype='float64',always_2d=True)
                powers[key]=float(np.mean(x*x))
                assert powers[key]==row['windows'][key]['mean_channel_power']
                assert float(np.max(abs(x)))==row['windows'][key]['channel_peak']
            contrasts=[float(10*np.log10(max(powers['event'],1e-30)/max(powers[key],1e-30))) for key in ('before','after')]
            assert contrasts==[row['contrast_db'][key] for key in ('before','after')]
            assert row['both_full_band_above_3db']==all(v>=3 for v in contrasts)
    chosen=sorted((r for r in scan['candidates'] if r['both_full_band_above_3db']),
                  key=lambda r:(-r['minimum_contrast_db'],r['source_seconds']))[:6]
    rows=checks['material']['selection'];assert [r['source_seconds'] for r in rows]==[r['source_seconds'] for r in chosen]
    assert sum(r['status']=='profile_compiled' for r in rows)==2
    assert not any(r.get('multi_seed_qualified') for r in rows)
    contexts=load(root/'B-contexts1/report.json')['cases']
    for number,(row,case) in enumerate(zip(rows,contexts),1):
        assert case['name']=='B_short_'+str(number) and len(case['frames'])==5
        folder=root/'B-contexts1'/case['name']
        original,_,_=read(scan['source'],*case['specification']['seconds'])
        stored,_=sf.read(folder/'original.wav',always_2d=True);assert np.array_equal(original,stored)
        assert all(sha(folder/frame['file'])==frame['sha256'] for frame in case['frames'])
    pictures=['web6/desktop.png','web6/mobile.png','web6/mobile-controls.png',
              'review-web1/browser/desktop.png','review-web1/browser/mobile.png']
    pictures += [f'B-contexts1/B_short_{n}/{file}' for n in range(1,7) for file in ('dashboard.jpg','timeline.png')]
    save(root/'visual-review.json',dict(result='passed',method='Exact images opened by agent; mobile viewport capture inspected after two animation frames',
        files={name:sha(root/name) for name in pictures},
        observations=['Short-window readout and source controls readable; actual mobile transport visible and usable',
            'Earlier immediate/full-page sticky/backdrop captures contained stale composite artifacts; web6 viewport capture resolves visibility',
            'All30 source frames and six timelines inspected; physical event identity remains unconfirmed']))
    save(root/'runtime.json',current)
    save(root/'source-power-audit.json',dict(result='passed',all_B_candidates=334,all_windows=1002,
        all_original_powers_peaks_contrasts_exact=True,six_context_PCM_exact=True,all30_frame_hashes_exact=True,
        top_six_selection_exact=True,source_sha256=scan['source_sha256']))
    sources={'AGENTS.md','handoff/当前代码阅读入口.md','handoff/毫秒级事件提参与素材核查V1.md',
        'research/short_event_scan_v1_plan.json','tools/author_event.py','tools/scan_approved_event_region.py',
        'tools/inspect_event_timeline_v1.py','tools/probe_short_event_scan_v1.py',
        'tools/verify_short_event_authoring_v1.py','tools/verify_short_event_workbench_v1.py',
        'tools/verify_short_event_workbench_web_v1.cjs','tools/build_B_short_event_candidates_v1.py',
        'tools/verify_short_event_review_v1.py','tools/verify_short_event_review_v1.cjs',
        'tools/finalize_short_event_authoring_v1.py','tools/audit_short_event_delivery_v1.py',
        'tools/verify_low_mid_event_scan_v1.py','tools/verify_low_mid_event_scan_web_v1.cjs',
        'tools/verify_event_response_workbench_v1.py','tools/research_archive_v1.py','tools/event_review.py'}
    for directory in ('tools/event_authoring','tools/event_designer'):
        sources.update(p.relative_to(repo).as_posix() for p in (repo/directory).glob('*.py'))
    sources.update('tools/sound_designer/web/'+name for name in ('events.html','events.js','events.css','event_candidates.js'))
    for directory,files in [('author2',('tools/verify_short_event_authoring_v1.py','tools/author_event.py')),
                            ('web6',('tools/verify_short_event_workbench_v1.py','tools/verify_short_event_workbench_web_v1.cjs','tools/sound_designer/web/events.js')),
                            ('B-fits2',('tools/build_B_short_event_candidates_v1.py',))]:
        assert all(sha(repo/name)==sha(root/directory/'exact_sources'/name) for name in files)
    subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    milestone=dict(schema='vsl.short-event-authoring-milestone/1',result='passed',goal_complete=False,
        previous_goal_turn='No synthesis progress: source/render/MCPS boundary confirmation only',
        current_goal_turn='Usable short transient authoring through actual C; approved-source fixed selection and diagnostic failures retained',
        checks={key:dict(path=str(root/name),sha256=sha(root/name),result='passed') for key,name in names.items()},
        source_files={name:sha(repo/name) for name in sorted(sources)},runtime_voice_files_unchanged=459,formal_voices_unchanged=89,
        bridge_sha256=sha(bridge),source_ABI=11,author_ABI=4,preset_schema=8,take_schema=9,ui_revision=13,
        base_freeze=str(base),base_manifest_sha256=sha(base/'manifest.json'),freeze=str(args.freeze),
        physical_afterfire_confirmed=False,new_timbre_accepted=False,new_download=False,commit_or_push=False,
        spatial_added=False,ADI_optimization=False,persistent_service_restarted=False,
        unresolved=['complete confirmed physical afterfire and other events','startup/idle mechanical naturalness','full RPM/load/state coverage'])
    save(repo/'research/short_event_authoring_v1_verification.json',milestone)
    sources.add('research/short_event_authoring_v1_verification.json')
    args.freeze.mkdir(parents=True,exist_ok=False)
    for name in sorted(sources):
        target=args.freeze/'repo'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    shutil.copytree(root,args.freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    entries=[dict(path=p.relative_to(args.freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(args.freeze.rglob('*')) if p.is_file()]
    save(args.freeze/'manifest.json',dict(schema='vsl.short-event-authoring-delta-freeze/1',base_freeze=str(base),
        base_manifest_sha256=sha(base/'manifest.json'),files=entries,goal_complete=False))
    print(dict(result='frozen',files=len(entries),bytes=sum(r['bytes'] for r in entries),manifest_sha256=sha(args.freeze/'manifest.json')),flush=True)


if __name__=='__main__':main()
