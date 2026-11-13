"""Freeze joint nuisance diagnostics and separately scoped human-reviewed F source evidence."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--stage',choices=('publish','freeze'),required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
base=args.workspace/'references/analysis'
joint=base/'joint_nuisance_pair_v1'
final=joint/'final1'
summary=repo/'research/joint_nuisance_pair_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.joint-nuisance-and-F-evidence-publication/1',result='running',sources={},reports={})
    try:
        locations=dict(pair=joint/'pair1',joint_audit=joint/'audit1',F_audition=base/'F_state_audition_v1/review1',
            F_catalogue=base/'F_state_catalog_v1/register1',F2_measure=base/'F2_idle_observation_v1/measure1',
            F_audit=base/'F2_idle_observation_v1/audit1')
        items={name:load(path/'report.json') for name,path in locations.items()}
        pair,audit,F,catalogue,F2,F_audit=(items[name] for name in locations)
        assert pair['result']=='finite_joint_nuisance_pairs_measured_not_global_minima'
        assert pair['controls']['passed'] and all(row['feasible'] and row['fit']['every_subproblem_certified'] for row in pair['cases'])
        assert audit['all_actual40_steps_audited'] and audit['candidate_report_sha256']==sha(joint/'pair1/report.json')
        assert F['result']=='exact_native_source_clips_and_single_player_prepared_not_audio_quality_acceptance'
        assert catalogue['F3_stopped_DNA_rejected']
        assert F2['result']=='reviewed_F2_recording_blocks_measured_not_idle_DNA_or_RPM' and F2['known_controls']['passed']
        assert F_audit['all7_source_clips_exact'] and F_audit['prior_catalogue_entries_unchanged']
        assert F_audit['speech_masked_F3_quantitative_use_rejected']
        assert F_audit['F2_report_sha256']==sha(locations['F2_measure']/'report.json')
        browser_dir=locations['F_audition']/'browser1'
        browser=load(browser_dir/'report.json')
        assert browser['result']=='all7_native_float_clips_decode_and_single_player_transport_verified_muted'
        assert browser['source_report_sha256']==sha(locations['F_audition']/'report.json')
        assert browser['html_sha256']==F['html_sha256']==sha(locations['F_audition']/'index.html')
        assert browser['executed_source_sha256']==sha(repo/'tools/inspect_F_state_audition_v1.cjs')==sha(browser_dir/'executed_source.cjs')
        for name in ('desktop','mobile'):
            assert sha(browser_dir/(name+'.png'))==browser[name+'_sha256']
        review=load(repo/'research/F_state_audition_v1_review.json')
        assert review['human_listening_result']=='received' and review['short_clip_source_usability_partially_accepted']
        sources={Path(__file__),repo/'tools/inspect_F_state_audition_v1.cjs',repo/'AGENTS.md',
            repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',repo/'handoff/开发留痕.md',
            repo/'research/怠速与加速完成度V1.md',repo/'research/相角与幅度联合补偿V1.md',
            repo/'research/F原声核查V1.md',repo/'research/F2怠速录音观察V1.md'}
        for name,value in items.items():
            assert not value['runtime_changed']
            for relative,digest in value['sources'].items():
                assert sha(repo/relative)==sha(locations[name]/'exact_sources'/relative)==digest
                sources.add(repo/relative)
            report['reports'][name]=dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(locations[name]/'report.json'),result=value['result'])
        report['reports']['F_browser']=dict(path=(browser_dir/'report.json').relative_to(args.workspace).as_posix(),
            sha256=sha(browser_dir/'report.json'),result=browser['result'])
        assert not pair['real_audio_read'] and not audit['real_audio_read']
        assert F['real_audio_read'] and F2['real_audio_read'] and F_audit['real_audio_read']
        prior=base/'bounded_envelope_pair_v1/final1'
        for filename in ('C_files_sha256.json','voice_files_sha256.json'):
            hashes=load(prior/filename)
            assert all(sha(repo/path)==digest for path,digest in hashes.items())
            shutil.copy2(prior/filename,final/filename)
        assert len(load(final/'C_files_sha256.json'))==540
        for clip in F['clips']:
            assert sha(args.workspace/clip['source_master'])==clip['source_master_sha256']
            assert sha(args.workspace/clip['original_encoded'])==clip['original_encoded_sha256']
            assert sha(locations['F_audition']/clip['file'])==clip['sha256']
        assert sha(repo/'references/segments_v1.json')==sha(args.workspace/'references/segments_v1.json')==catalogue['catalogue_sha256']
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
            cwd=repo,capture_output=True,check=True)
        for source in sources:
            relative=source.relative_to(repo);destination=final/'exact_sources'/relative
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
            report['sources'][relative.as_posix()]=sha(source)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        for location,filename,digest in ((joint/'pair1','joint_nuisance_pairs.png',pair['plot_sha256']),
            (locations['F2_measure'],'F2_idle_blocks.png',F2['plot_sha256'])):
            assert sha(location/filename)==digest;shutil.copy2(location/filename,final/filename)
        report.update(result='joint_nuisance40_steps_and_human_reviewed_F_source_evidence_published_not_phase_qualification',
            pairs=[dict(id=row['id'],before=row['raw_difference_norm_before'],after=row['raw_difference_norm_after'],
                iterations=row['fit']['iterations'],accepted=row['fit']['accepted_steps'],seconds=row['seconds'],
                every_subproblem_certified=row['fit']['every_subproblem_certified'],
                fixed_hypothesis_fresh_noise_distance=row['fixed_hypothesis_distance_under_fresh_white_noise']) for row in pair['cases']],
            joint_all40_audited=True,global_nuisance_minimum_proved=False,phase_estimator_qualified=False,
            phase_diagnostic_real_audio_read=False,approved_F_source_audio_read=True,
            F_human_review=review,F2_three_block_recording_band_span_db_LR=F2['three_block_recording_band_span_db_LR'],
            F2_display_only_low_band_peaks=F_audit['display_only_low_band_peaks'],
            F3_stopped_excluded_from_quantitative_analysis=True,F2_or_F3_RPM_inferred=False,
            catalogue_sha256=catalogue['catalogue_sha256'],all_existing_catalogue_entries_unchanged=True,
            browser_metadata_and_muted_transport_pass=True,all_source_clips_exact=True,
            C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            existing55CTests_rerun=False,model_exported=False,runtime_changed=False,moving35='held_unchanged',
            original17_rerun=False,full33_replaced=False,individual14kHz_demonstrated=False,
            phase_extracted_real_model_permitted=False,A_low_listening='original_question_pending',
            idle_acceleration_complete=False,vehicle_timbre_accepted=False,goal_complete=False,
            previous_goal_turn_classification='progress_actual_bounded_envelope_compensation_independent_audit_and_freeze',
            goal_turn_classification='progress_actual_joint_nuisance40QPs_full_audit_and_human_F_source_review_permissioned_catalogue_and_independent_raw_F2_spectra',
            next_step='Check F2 multiple-line common periodicity with independent counterexamples before any fundamental or RPM claim; verify continuous F3 gear/action boundaries and AV evidence. New phase-extracted real models still require failed36/all17/full33/individual14kHz/original E gates. No blind nuisance-direction or iteration sweeps.',
            limits=pair['limitations']+F2['limits'])
        save(summary,report)
    except Exception as exc:
        report.update(result='failed',error=repr(exc));raise
    finally:
        save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],actual_QPs=40,F_clips=7,C_H=540)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary)
    assert report['result']=='joint_nuisance40_steps_and_human_reviewed_F_source_evidence_published_not_phase_qualification'
    assert sha(summary)==sha(final/'report.json')
    for relative,digest in report['sources'].items():
        assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for row in report['reports'].values():
        assert sha(args.workspace/row['path'])==row['sha256']
    out=args.workspace/'baselines/joint_nuisance_pair_v1';out.mkdir(exist_ok=False)
    shutil.copytree(joint,out/'evidence')
    for name in ('F_state_audition_v1','F_state_catalog_v1','F2_idle_observation_v1'):
        shutil.copytree(base/name,out/name)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    files=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    previous={name:dict(path='baselines/'+name+'/manifest.json',sha256=sha(args.workspace/'baselines'/name/'manifest.json'))
        for name in ('bounded_envelope_pair_v1','state_media_v1')}
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=files,prior_manifests=previous,
        phase_diagnostic_real_audio_read=False,approved_F_source_audio_read=True,profiles_exported=0,
        vehicle_timbre_accepted=False,goal_complete=False))
    assert all(sha(out/row['path'])==row['sha256'] for row in files)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(files),bytes=sum(row['bytes'] for row in files),
        manifest_sha256=sha(out/'manifest.json'))),flush=True)
