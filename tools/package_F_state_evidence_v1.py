"""Publish/freeze/verify bounded F2/F3 source evidence, retaining failed attempts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--stage',choices=('publish','freeze','verify'),required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
base=args.workspace/'references/analysis'
root=base/'F_state_evidence_v1'
final=root/'final1'
summary=repo/'research/F_state_evidence_v1_summary.json'
frozen=args.workspace/'baselines/F_state_evidence_v1'


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def validate_report(value):
    for relative,digest in value['sources'].items():
        assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for row in value['reports'].values():
        assert sha(args.workspace/row['path'])==row['sha256']
    for name in ('C_files_sha256.json','voice_files_sha256.json'):
        hashes=load(final/name)
        assert all(sha(repo/path)==digest for path,digest in hashes.items())
    assert len(load(final/'C_files_sha256.json'))==540
    assert sha(repo/'references/segments_v1.json')==sha(args.workspace/'references/segments_v1.json')==value['catalogue_sha256']
    for row in value['media_identities']:
        assert sha(args.workspace/row['path'])==row['sha256']
    subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
                   cwd=repo,capture_output=True,check=True)


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.F-state-evidence-publication/1',result='running',sources={},reports={})
    try:
        locations={'F2':base/'F2_period_relation_v1/observe1','decode_failure':base/'F3_display_continuity_v1/inspect1',
            'rejected_Dice':base/'F3_display_continuity_v1/inspect2','shape':base/'F3_display_continuity_v1/shape1',
            'audit':root/'audit2'}
        values={name:load(path/'report.json') for name,path in locations.items()}
        audit=values['audit'];shape=values['shape'];f2=values['F2']
        assert audit['result']=='F2_exact_intervals_and_all1080_F3_native_frame_classifications_independently_verified'
        assert audit['F2_all3_cases_and7_controls_exact_rational'] and audit['all1080_classifications_reproduced']
        assert not values['rejected_Dice']['detector_controls_passed'] and shape['detector_controls_passed']
        assert audit['F3_shape_report_sha256']==sha(locations['shape']/'report.json')
        assert audit['F2_report_sha256']==sha(locations['F2']/'report.json')
        assert not f2['RPM_inferred'] and f2['selected_fundamental'] is None
        assert values['decode_failure']['result']=='failed'
        sources={Path(__file__),repo/'AGENTS.md',repo/'research/F怠速与挡位证据V1.md',
            repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',repo/'handoff/开发留痕.md',
            repo/'research/怠速与加速完成度V1.md',repo/'research/F_state_audition_v1_review.json'}
        for name,value in values.items():
            assert not value['runtime_changed'] and not value['model_exported']
            report['reports'][name]=dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(locations[name]/'report.json'),result=value['result'])
            for relative,digest in value['sources'].items():
                assert sha(locations[name]/'exact_sources'/relative)==digest
                if name!='decode_failure':assert sha(repo/relative)==digest
                sources.add(repo/relative)
        oldaudit=load(root/'audit1/report.json')
        for relative,digest in oldaudit['sources'].items():assert sha(root/'audit1/exact_sources'/relative)==digest
        report['reports']['prior_audit']=dict(path=(root/'audit1/report.json').relative_to(args.workspace).as_posix(),
            sha256=sha(root/'audit1/report.json'),result=oldaudit['result'])
        prior=base/'joint_nuisance_pair_v1/final1'
        for filename in ('C_files_sha256.json','voice_files_sha256.json'):
            shutil.copy2(prior/filename,final/filename)
        for source in sources:
            relative=source.relative_to(repo);target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            report['sources'][relative.as_posix()]=sha(source)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        assert sha(locations['F2']/'F2_period_relations.png')==f2['plot_sha256']
        shutil.copy2(locations['F2']/'F2_period_relations.png',final/'F2_period_relations.png')
        catalogue=load(args.workspace/'references/segments_v1.json')
        media=[]
        for key in ('F1','F2','F3'):
            source=catalogue['sources'][key]
            for field in ('video','raw','master'):
                if field in source and isinstance(source[field],str):
                    path=source[field];media.append(dict(path=path,sha256=sha(args.workspace/path)))
        # Use prior reviewed source identities rather than infer catalogue field names.
        previous=load(base/'F_state_audition_v1/review1/report.json')
        media={r['path']:r for r in media}
        for clip in previous['clips']:
            for path,digest in ((clip['source_master'],clip['source_master_sha256']),
                                (clip['original_encoded'],clip['original_encoded_sha256'])):
                assert sha(args.workspace/path)==digest;media[path]=dict(path=path,sha256=digest)
        report.update(result='F_source_period_relations_and_display_continuity_published_not_new_DNA',
            F2_cases=f2['cases'],F2_fundamental_selected=False,RPM_inferred=False,
            F3_display_candidates=shape['candidates'],F3_full_window_unknowns={k:v['unknown'] for k,v in audit['windows'].items()},
            all1080_classifications_independently_replayed=True,all7_F2_controls_exact_rational=True,
            rejected_Dice_and_intentional_decode_termination_retained=True,audit1_preserved_audit2_adds_absolute_timing_checks=True,
            source_variants=audit['source_variants'],human_review=load(repo/'research/F_state_audition_v1_review.json'),
            visuals_reviewed=audit['visually_reviewed'],visual_scope=audit['visual_scope'],
            media_identities=list(media.values()),catalogue_sha256=sha(repo/'references/segments_v1.json'),
            phase_extractor_qualified=False,physical_shift_timing_established=False,AV_delay_calibrated=False,load_inferred=False,
            real_audio_read=False,existing_recording_observations_read=True,original_video_read=True,
            C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            existing55CTests_rerun=False,model_exported=False,runtime_changed=False,moving35='held_unchanged',
            phase_extracted_real_model_permitted=False,vehicle_timbre_accepted=False,idle_acceleration_complete=False,goal_complete=False,
            original_A_low_listening='original_question_pending',F_source_listening='received_no_duplicate',
            next_step='Cross-validate F2 acoustic period and F3 pitch/display trajectory without physical RPM/AV claims; preserve original failed36/all17/full33/individual14k/originalE gates before any phase-extracted real model. No blind sweeps.',
            limits=audit['limits']+shape['limits']+f2['limits'])
        validate_report(report)
        save(summary,report)
    except Exception as exc:report.update(result='failed',error=repr(exc));raise
    finally:save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],C_H=540,new_models=0)),flush=True)
elif args.stage=='freeze':
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary);assert sha(summary)==sha(final/'report.json')
    validate_report(report)
    frozen.mkdir(exist_ok=False)
    for name in ('F2_period_relation_v1','F3_display_continuity_v1','F_state_evidence_v1'):
        shutil.copytree(base/name,frozen/name)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(frozen/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(frozen/'source.zip') as archive:assert archive.testzip() is None
    files=[dict(path=p.relative_to(frozen).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(frozen.rglob('*')) if p.is_file()]
    previous={name:dict(path='baselines/'+name+'/manifest.json',sha256=sha(args.workspace/'baselines'/name/'manifest.json'))
              for name in ('joint_nuisance_pair_v1','state_media_v1')}
    save(frozen/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=files,prior_manifests=previous,
        profiles_exported=0,real_audio_read=False,original_video_read=True,vehicle_timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='frozen',commit=commit,files=len(files),bytes=sum(x['bytes'] for x in files),manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
else:
    manifest=load(frozen/'manifest.json');report=load(summary);validate_report(report)
    assert sha(summary)==sha(final/'report.json')==sha(frozen/'F_state_evidence_v1/final1/report.json')
    for row in manifest['files']:
        assert sha(frozen/row['path'])==row['sha256'] and (frozen/row['path']).stat().st_size==row['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as archive:
        assert archive.testzip() is None
        for relative,digest in report['sources'].items():assert hashlib.sha256(archive.read(relative)).hexdigest()==digest
    for previous in manifest['prior_manifests'].values():
        path=args.workspace/previous['path'];assert sha(path)==previous['sha256']
        for row in load(path)['files']:assert sha(path.parent/row['path'])==row['sha256']
    print(json.dumps(dict(result='all_frozen_files_source_zip_media_C_voices_and_prior_manifest_payloads_verified',
                         files=len(manifest['files']),manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
