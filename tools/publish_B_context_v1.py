"""Bind B source evidence, correct current catalog context and publish boundaries."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.b-context-publication/1',result='running',evidence_sha256={},source_sha256={})
try:
    root=a.workspace/'references/analysis/cabin_low_context_v1'
    acoustic=a.workspace/'references/analysis/cabin_low_v1'
    def bind(file):
        file=Path(file);r['evidence_sha256'][file.relative_to(a.workspace).as_posix()]=sha(file)
    def report(directory,expected):
        file=directory/'report.json';item=json.loads(file.read_text(encoding='utf-8-sig'))
        assert item['result']==expected,(directory,item['result'])
        bind(file);return item
    first=report(root/'fetch1','retrieval_failed')
    fetched=report(root/'fetch2','downloaded_video_context_not_aligned')
    audio=report(root/'audio1','downloaded_audio_not_aligned')
    for folder,item in [('fetch1',first),('fetch2',fetched),('audio1',audio)]:
        assert sha(root/folder/'executed_fetch.py')==item['source_sha256']
    assert sha(Path(fetched['file']))==fetched['sha256']
    assert sha(Path(audio['file']))==audio['sha256']
    assert sha(a.workspace/'references/raw/B_context_720p.mp4')==fetched['sha256']
    failed=json.loads((root/'B_inspect1/report.json').read_text(encoding='utf-8'))
    assert failed['result']=='failed' and 'TimeoutExpired' in failed['error']
    assert sha(root/'B_inspect1/executed_inspect.py')==failed['source_sha256']
    bind(root/'B_inspect1/report.json')
    frames=boards=0
    for folder,source,count in [('inspect1','E',13),('B_inspect2','B',64),('B_idle_inspect1','B',36)]:
        item=report(root/folder,'frames_decoded_not_yet_human_annotated')
        assert sha(root/folder/'executed_inspect.py')==item['source_sha256']
        assert sha(root/folder/'executed_plan.json')==item['inspection_plan_sha256']
        entry=item['sources'][source];assert len(entry['frames'])==count
        assert sha(Path(entry['video']))==entry['video_sha256']
        for row in entry['frames']+entry['boards']:
            file=root/folder/source/row['file'];assert sha(file)==row['sha256'];bind(file)
        frames+=count;boards+=len(entry['boards'])
    aligned=report(root/'align1','audio_timeline_alignment_pass')
    assert aligned['controls']['known_insertion_pass'] and aligned['controls']['periodic_signal_rejected']
    assert len(aligned['windows'])==5 and all(w['passed'] for w in aligned['windows'])
    assert sha(root/'align1/B_video_audio_decoded_float.wav')==aligned['input']['decoded_sha256']
    for folder in ['observe1','target_observe1']:
        item=report(acoustic/folder,'observed_not_fitted')
        for name,entry in item['segments'].items():
            for file,key in [('observations.npz','observation_sha256'),('observations.png','plot_sha256')]:
                path=acoustic/folder/name/file;assert sha(path)==entry[key];bind(path)
    qualified=report(acoustic/'qualify1','local_diagnostics_only')
    assert not qualified['model_exported'] and not qualified['runtime_modified']
    assert not any(c['local_diagnostic_gate'] for c in qualified['cases'].values())
    catalogs=[repo/'references/segments_v1.json',a.workspace/'references/segments_v1.json']
    alignment_offset=aligned['median_video_audio_minus_user_audio_seconds']
    changed=[]
    for i,file in enumerate(catalogs):
        data=json.loads(file.read_text(encoding='utf-8'))
        shutil.copy2(file,a.out/f'catalog_before_{i}.json')
        b=data['sources']['B'];assert b['video_sha256']==fetched['sha256']
        b['alignment']='Five4s L/R audio matches: video paired-audio time = local user-MP3 time + %.9fs; offset spread %.6fms. This does NOT calibrate instrument/video/engine-event latency or every intervening sample.'%(alignment_offset,aligned['offset_range_ms'])
        b['alignment_evidence']='references/analysis/cabin_low_context_v1/align1/report.json'
        pull=data['segments']['B_cabin_pull']
        pull.update(perspective='cabin binaural, visually inspected road driving',
            visual='Gear4 at218.018s,gear3 at220.020..230.030s; displayed speed falls then rises/falls. Video audio is about36.3ms later than user MP3.',
            audio_interpretation='Mixed downshift and changing-speed cabin context; not one uniform loaded acceleration',
            not_established=['pedal/load or injector telemetry','exact RPM','independent instrument/engine-event latency','engine banks from L/R','isolated engine field'],
            evidence='references/analysis/cabin_low_context_v1/final1/exact_sources/research/B_context_v1_annotations.json')
        pull['allowed_uses']=list(dict.fromkeys(pull['allowed_uses']+['gear_display_context']))
        release=data['segments']['B_cabin_release_context']
        release.update(perspective='cabin binaural, visually inspected cornering/gear change',
            visual='Gear1 at476.009s,gear2 at478.011/480.013s, cornering and changing displayed speed',
            audio_interpretation='Mixed upshift/cornering/speed changes; legacy release label is not measured throttle release',
            evidence=pull['evidence'])
        release['allowed_uses']=list(dict.fromkeys(release['allowed_uses']+['gear_display_context']))
        new=[('B_walkaround_frunk_context',[84,94],'exterior changing viewpoint at front luggage hood','Opening/closing front luggage hood; old B_cabin_steady name is incorrect',['scene_context_only','interference_observation']),
             ('B_stationary_departure_context',[124,140],'cabin stationary then departure','P/0mph at132/136s,gear1 by140s; control actions and acoustic rises/falls',['stationary_context','interior_dynamic_observation']),
             ('B_departure_gears_context',[160,176],'cabin road departure','Gear2/23mph at164s,gear3/35mph at168s,gear4/39mph at172/176s',['gear_display_context','interior_dynamic_observation']),
             ('B_arrival_parking_context',[798,808],'cabin arrival/parking','Gear1 at798s,hand at controls802s,P/0mph and Parking brake applied at806s',['parking_context','interior_dynamic_observation'])]
        for key,seconds,perspective,visual,uses in new:
            assert key not in data['segments']
            data['segments'][key]=dict(source='B',seconds=seconds,perspective=perspective,
                visual=visual,allowed_uses=uses,
                audio_interpretation='Mixed scene observation; no source/state model qualified',
                not_established=['engine source isolation','exact ECU RPM','pedal/load/fueling','thermal state','independent instrument/engine-event latency'],
                evidence=pull['evidence'] if 'frunk' in key else 'references/analysis/cabin_low_context_v1/final1/exact_sources/research/B_idle_context_v1_annotations.json',
                existing_audition=None)
        file.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        changed.append(dict(path=str(file),sha256=sha(file)))
    assert changed[0]['sha256']==changed[1]['sha256']
    subprocess.run(['git','diff','--exit-code','HEAD','--','*.c','*.h','voices'],cwd=repo,check=True,capture_output=True)
    c_files=subprocess.check_output(['git','ls-files','-z','--','*.c','*.h'],cwd=repo).split(b'\0')
    c_count=sum(bool(f) for f in c_files);assert c_count==530
    paths=[Path(__file__),*sorted(repo.glob('research/*B*context*v1*.json')),
        *[repo/name for name in ['research/cabin_low_context_v1_inspection_plan.json','research/cabin_low_context_v1_annotations.json',
        'research/cabin_low_v1_observation_plan.json','research/cabin_low_v1_qualification_plan.json','research/B_alignment_v1_plan.json',
        'research/B_target_states_v1_observation_plan.json','research/B素材状态纠偏V1.md','references/segments_v1.json',
        'tools/fetch_approved_B_context_v1.py','tools/register_B_context_v1.py','tools/observe_cabin_low_v1.py','tools/qualify_cabin_low_v1.py',
        'tools/align_B_context_v1.py','tools/cabin_low_v1/alignment.py','tools/inspect_idle_context_v1.py',
        'tools/prepare_B_clips.py','tools/analyze_states_space.py']]]
    for file in paths:
        name=file.relative_to(repo);target=a.out/'exact_sources'/name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
        r['source_sha256'][name.as_posix()]=sha(file)
    r.update(result='source_context_corrected_no_new_timbre',catalogs_after=changed,
        B_frames=100,E_frames=13,contact_sheets=boards,alignment_offset_seconds=alignment_offset,
        alignment_offset_range_ms=aligned['offset_range_ms'],
        C_H_files=c_count,C_H_and_existing_models_equal_HEAD=True,
        CTests_rerun=False,new_DNA_exported=False,idle_or_acceleration_timbre_complete=False,
        limits=['No runtime/default/RPM/state-policy changes or new sound acceptance',
                'Generic dynamic phase qualification remains not_passed; two new local diagnostics rejected',
                'Moving35 preserved; original exterior low listening question not repeated'])
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if r['result']=='source_context_corrected_no_new_timbre':
    summary=dict(r,publication_report_sha256=sha(a.out/'report.json'))
    (repo/'research/B_context_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:r[k] for k in ['result','B_frames','E_frames','alignment_offset_seconds','C_H_files','new_DNA_exported']}),flush=True)
