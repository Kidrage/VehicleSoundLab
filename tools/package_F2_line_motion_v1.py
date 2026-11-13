"""Freeze the local-frequency observation and failures without promoting a model."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=('publish','freeze','verify'),required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
root=args.workspace/'references/analysis/F2_line_motion_v1';final=root/'final1'
summary=repo/'research/F2_line_motion_v1_summary.json';frozen=args.workspace/'baselines/F2_line_motion_v1'

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def verify_current(r):
    for relative,digest in r['sources'].items():assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for name,row in r['reports'].items():assert sha(root/name/'report.json')==row['sha256']
    for name in ('C_files_sha256.json','voice_files_sha256.json'):
        items=load(final/name)
        assert all(sha(repo/file)==digest for file,digest in items.items())
    assert len(load(final/'C_files_sha256.json'))==540
    assert sha(repo/'references/segments_v1.json')==sha(args.workspace/'references/segments_v1.json')==r['catalogue_sha256']
    for item in r['input_media']:assert sha(args.workspace/item['path'])==item['sha256']
    subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],cwd=repo,capture_output=True,check=True)

if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.F2-line-motion-final/1',result='running',sources={},reports={})
    try:
        reports={name:load(root/name/'report.json') for name in ('observe1','observe2','audit1','review1','review2')}
        a=reports['audit1'];s=reports['observe2'];v=reports['review2']
        assert a['result']=='F2_initial_AM_failure_and_all90_local_frequency_observations_independently_replayed'
        assert a['counts']==dict(observations=90,resolved=62,unresolved=28,anchor_complete_rows=3)
        assert a['observe2_report_sha256']==v['input_report_sha256']==sha(root/'observe2/report.json')
        assert reports['observe1']['result']=='failed' and not reports['observe1']['real_audio_read']
        assert s['controls']['passed'] and not s['phase_estimator_run'] and not s['model_exported']
        sources={Path(__file__),repo/'AGENTS.md',repo/'research/F2声线变化V1.md',repo/'handoff/研究续接.md',
                 repo/'handoff/算法说明.md',repo/'handoff/开发留痕.md',repo/'research/怠速与加速完成度V1.md'}
        variants={}
        for name,value in reports.items():
            report['reports'][name]=dict(sha256=sha(root/name/'report.json'),result=value['result'])
            for file,digest in value['sources'].items():
                assert sha(root/name/'exact_sources'/file)==digest
                variants.setdefault(file,{})[name]=digest
                if name not in ('observe1','review1'):assert sha(repo/file)==digest
                sources.add(repo/file)
        for path in sources:
            relative=path.relative_to(repo);target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            report['sources'][relative.as_posix()]=sha(path)
        previous=args.workspace/'references/analysis/F_state_evidence_v1/final1'
        for name in ('C_files_sha256.json','voice_files_sha256.json'):shutil.copy2(previous/name,final/name)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        catalogue=load(repo/'references/segments_v1.json');src=catalogue['sources']['F2']
        media=[dict(path=src[key],sha256=src[key+'_sha256']) for key in ('raw','master')]
        assert sha(root/'review2/F2_line_motion_review.png')==v['plot_sha256']
        shutil.copy2(root/'review2/F2_line_motion_review.png',final/'F2_line_motion_review.png')
        report.update(result='F2_local_line_motion_audited_frozen_not_idle_DNA_or_period_qualification',
            real_audio_read=True,phase_estimator_run=False,model_exported=False,runtime_changed=False,
            source_variants=variants,input_media=media,catalogue_sha256=sha(repo/'references/segments_v1.json'),
            counts=a['counts'],eligible_anchor_rows=a['eligible_anchor_rows'],independent_errors=a['independent_rectangular_DTFT_errors'],
            initial_AM_error_Hz=reports['observe1']['controls']['cases'][2]['max_frequency_error_Hz'],
            centered_AM_error_Hz=s['controls']['cases'][2]['max_frequency_error_Hz'],
            first_failure_sources_preserved=True,review1_label_layout_superseded_by_review2=True,
            both_review_figures_visually_checked=True,complete_continuous_coordinate_established=False,
            selected_fundamental=None,RPM_inferred=False,phase_extracted_real_model_permitted=False,
            C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            existing55CTests_rerun=False,moving35='held_unchanged',vehicle_timbre_accepted=False,
            idle_acceleration_complete=False,goal_complete=False,original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_F2_exact_intervals_and_1080native_F3_display_evidence_audited_frozen_pushed',
            current_goal_turn='progress_actual_AM_bias_failure_repair_and_independent90local_F2_frequency_observations',
            next_step='Validate per-window native spectral peak locations and adjacent-line bias; never widen boxes to force old failures to pass, interpolate unknowns, or convert acoustic grouping to RPM. Original failed36/all17/full33/individual14k/originalE gates remain required before phase-extracted real models.',
            limits=a['limits']+s['limits'])
        verify_current(report);save(summary,report)
    except Exception as exc:report.update(result='failed',error=repr(exc));raise
    finally:save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],counts=report['counts'])),flush=True)
elif args.stage=='freeze':
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary);verify_current(report);assert sha(summary)==sha(final/'report.json')
    frozen.mkdir(exist_ok=False);shutil.copytree(root,frozen/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(frozen/'source.zip'),commit],cwd=repo,check=True)
    files=[dict(path=x.relative_to(frozen).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    prior={name:dict(path='baselines/'+name+'/manifest.json',sha256=sha(args.workspace/'baselines'/name/'manifest.json')) for name in ('F_state_evidence_v1','state_media_v1')}
    save(frozen/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=files,prior_manifests=prior,
        profiles_exported=0,real_audio_read=True,vehicle_timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(x['bytes'] for x in files),commit=commit,manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
else:
    r=load(summary);verify_current(r);m=load(frozen/'manifest.json')
    assert sha(summary)==sha(final/'report.json')==sha(frozen/'evidence/final1/report.json')
    for row in m['files']:assert sha(frozen/row['path'])==row['sha256'] and (frozen/row['path']).stat().st_size==row['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as z:
        assert z.testzip() is None
        for file,digest in r['sources'].items():assert hashlib.sha256(z.read(file)).hexdigest()==digest
    for row in m['prior_manifests'].values():
        path=args.workspace/row['path'];assert sha(path)==row['sha256']
        for item in load(path)['files']:assert sha(path.parent/item['path'])==item['sha256']
    print(json.dumps(dict(result='source_zip_frozen_payloads_prior_manifests_media_C_voices_verified',files=len(m['files']),manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
