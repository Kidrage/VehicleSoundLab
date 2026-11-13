"""Freeze failed fixture, repair and audited9window affine-AM rejection evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=('publish','freeze','verify'),required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
root=args.workspace/'references/analysis/F2_local_envelopes_v1';final=root/'final1'
summary=repo/'research/F2_local_envelopes_v1_summary.json';frozen=args.workspace/'baselines/F2_local_envelopes_v1'


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_current(r):
    for file,digest in r['sources'].items():assert sha(repo/file)==sha(final/'exact_sources'/file)==digest
    for item in r['reports'].values():assert sha(args.workspace/item['path'])==item['sha256']
    for name in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/file)==digest for file,digest in load(final/name).items())
    assert len(load(final/'C_files_sha256.json'))==540
    assert sha(repo/'references/segments_v1.json')==sha(args.workspace/'references/segments_v1.json')==r['catalogue_sha256']
    assert sha(args.workspace/'AGENTS.md')==sha(final/'data_workspace_AGENTS.md')==r['data_memory_sha256']
    for item in r['input_media']:assert sha(args.workspace/item['path'])==item['sha256']
    for item in r['prior_manifests'].values():assert sha(args.workspace/item['path'])==item['sha256']
    subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],cwd=repo,capture_output=True,check=True)


if args.stage=='publish':
    final.mkdir(exist_ok=False);r=dict(schema='vsl.F2-local-envelopes-final/1',result='running',sources={},reports={})
    try:
        locations={name:root/name for name in ('observe1','diagnosis1','observe2','audit1','audit2','review1')}
        values={name:load(path/'report.json') for name,path in locations.items()}
        actual=values['observe2'];audit=values['audit2'];review=values['review1']
        assert values['observe1']['result']=='failed' and not values['observe1']['real_audio_read']
        assert values['diagnosis1']['result']=='original_fixture_peak_count_failure_replayed_without_fit'
        assert actual['controls']['passed'] and audit['original_failure_replayed']
        assert audit['result']=='all18_affine_envelope_local_fits_and_original_negative_failure_independently_audited'
        assert audit['actual_report_sha256']==review['input_report_sha256']==sha(root/'observe2/report.json')
        assert review['audit_report_sha256']==sha(root/'audit2/report.json') and not audit['actual_fits_resolved_again']
        assert audit['counts']==dict(real_channel_fits=18,old_main_fq_rows=5,new_main_fq_rows=4,
            new_main_fq_and_slope_rows=4,new_fq_bound_components=30,new_slope_bound_components=2,
            converged_channel_fits=16,evaluation_limit_channel_fits=2,new_raw_main_fq_rows=5)
        sources={Path(__file__),repo/'AGENTS.md',repo/'research/F2局部幅度包络V1.md',repo/'research/F2_local_envelopes_v1_plan.json',
            repo/'research/F2_local_envelopes_v1_negative_repair.json',repo/'handoff/研究续接.md',repo/'handoff/算法说明.md',
            repo/'handoff/开发留痕.md',repo/'research/怠速与加速完成度V1.md'}
        versions={}
        for name,value in values.items():
            assert not value['model_exported'] and not value['runtime_changed']
            r['reports'][name]=dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),sha256=sha(locations[name]/'report.json'),result=value['result'])
            for file,digest in value['sources'].items():
                assert sha(locations[name]/'exact_sources'/file)==digest
                if name not in ('observe1','audit1'):assert sha(repo/file)==digest
                versions.setdefault(file,{})[name]=digest;sources.add(repo/file)
        assert review['plot_sha256']==sha(root/'review1/F2_local_envelopes.png')
        for source in sources:
            relative=source.relative_to(repo);target=final/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target);r['sources'][relative.as_posix()]=sha(source)
        previous=args.workspace/'references/analysis/F2_peak_identity_v1/final1'
        for name in ('C_files_sha256.json','voice_files_sha256.json'):shutil.copy2(previous/name,final/name)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        shutil.copy2(root/'review1/F2_local_envelopes.png',final/'F2_local_envelopes.png')
        source=load(repo/'references/segments_v1.json')['sources']['F2']
        parents={name:dict(path='baselines/'+name+'/manifest.json',sha256=sha(args.workspace/'baselines'/name/'manifest.json')) for name in ('F2_peak_identity_v1','state_media_v1')}
        reductions=[c['left_cost_reduction_percent'] for c in audit['comparisons']]
        r.update(result='positive_affine_local_amplitude_candidate_frozen_NOT_adopted_as_idle_DNA',
            real_audio_read=True,source_versions=versions,input_media=[dict(path=source[k],sha256=source[k+'_sha256']) for k in ('raw','master')],
            prior_manifests=parents,catalogue_sha256=sha(repo/'references/segments_v1.json'),data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            counts=audit['counts'],audit_errors=audit['errors'],comparisons=audit['comparisons'],
            cost_reduction_percent_range=[min(reductions),max(reductions)],
            known_cases=[dict(id=c['id'],gate_applied=c['gate_applied'],passed=c['passed']) for c in actual['controls']['cases']],
            C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            figure_visually_checked=True,existing55CTests_rerun=False,model_exported=False,runtime_changed=False,
            candidate_adopted=False,actual_fits_resolved_again=False,shared_phase_clock_fit=False,
            phase_extracted_real_model_permitted=False,RPM_inferred=False,vehicle_timbre_accepted=False,
            idle_acceleration_complete=False,goal_complete=False,moving35='held_unchanged',original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_allpeak_correspondence_and_omitted37_counterfactual_audited_frozen_pushed',
            current_goal_turn='progress_known_affine_amplitude_hypothesis_controls_failure_replay_and_all18real_comparisons_independent_audit_show_no_resolution',
            next_step='Qualify complex residual/sideband observations on known AM/FM and independent-neighbor examples before recording interpretation. Do not raise envelope degree/bounds/budget. Originalfailed36/all17/full33/individual14k/originalE remain before real shared-phase DNA.',
            limits=audit['limits']+actual['limits'])
        verify_current(r);save(summary,r)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(final/'report.json',r)
    print(json.dumps(dict(result=r['result'],counts=r['counts'],cost_reduction_percent_range=r['cost_reduction_percent_range'])),flush=True)
elif args.stage=='freeze':
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    r=load(summary);verify_current(r);assert sha(summary)==sha(final/'report.json')
    frozen.mkdir(exist_ok=False);shutil.copytree(root,frozen/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(frozen/'source.zip'),commit],cwd=repo,check=True)
    files=[dict(path=x.relative_to(frozen).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=files,prior_manifests=r['prior_manifests'],
        real_audio_read=True,profiles_exported=0,candidate_adopted=False,vehicle_timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(x['bytes'] for x in files),commit=commit,manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
else:
    r=load(summary);verify_current(r);m=load(frozen/'manifest.json')
    assert sha(summary)==sha(final/'report.json')==sha(frozen/'evidence/final1/report.json')
    for item in m['files']:assert sha(frozen/item['path'])==item['sha256'] and (frozen/item['path']).stat().st_size==item['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as z:
        assert z.testzip() is None
        for file,digest in r['sources'].items():assert hashlib.sha256(z.read(file)).hexdigest()==digest
    for item in m['prior_manifests'].values():
        path=args.workspace/item['path'];assert sha(path)==item['sha256']
        for row in load(path)['files']:assert sha(path.parent/row['path'])==row['sha256']
    print(json.dumps(dict(result='all_frozen_payloads_sources_prior_evidence_media_C_voices_verified',files=len(m['files']),manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
