"""Freeze known clipping diagnosis, reference-rate coordinates and their independent audit."""
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
root=args.workspace/'references/analysis/F2_rate_coordinates_v1';final=root/'final1'
summary=repo/'research/F2_rate_coordinates_v1_summary.json'
frozen=args.workspace/'baselines/F2_rate_coordinates_v1'


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
    final.mkdir(exist_ok=False)
    r=dict(schema='vsl.F2-rate-coordinates-final/1',result='running',sources={},reports={})
    try:
        locations={name:root/name for name in ('diagnosis1','diagnosis2','observe1','audit1','review1')}
        values={name:load(path/'report.json') for name,path in locations.items()}
        actual=values['observe1'];audit=values['audit1'];diagnosis=values['diagnosis2']
        assert actual['controls']['passed'] and audit['controls_replayed']
        assert audit['counts']==dict(channel_fits=18,successful_channel_fits=18,components=92,
            old_bound_components=28,new_bound_components=16,old_main_eligible_rows=5,
            new_main_eligible_rows=9,new_all_component_eligible_rows=3,linear_subspace_projections=72)
        assert audit['actual_report_sha256']==sha(root/'observe1/report.json')
        assert audit['known_diagnostic_arrays_and_fits_exact_between_revisions']
        assert not audit['real_nonlinear_fits_resolved_again']
        for name,digest in audit['diagnostic_reports_sha256'].items():assert sha(root/name/'report.json')==digest
        sources={Path(__file__),repo/'AGENTS.md',repo/'research/F2相对变化率V1.md',
            repo/'research/F2_chirp_limits_v1_plan.json',repo/'research/F2_rate_coordinates_v1_plan.json',
            repo/'handoff/研究续接.md',repo/'handoff/算法说明.md',repo/'handoff/开发留痕.md',
            repo/'research/怠速与加速完成度V1.md'}
        versions={}
        for name,value in values.items():
            assert not value['model_exported'] and not value['runtime_changed']
            r['reports'][name]=dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(locations[name]/'report.json'),result=value['result'])
            for file,digest in value['sources'].items():
                assert sha(locations[name]/'exact_sources'/file)==digest
                if name!='diagnosis1':assert sha(repo/file)==digest
                versions.setdefault(file,{})[name]=digest;sources.add(repo/file)
        figure=root/'review1/F2_rate_coordinates.png'
        assert values['review1']['plot_sha256']==sha(figure)
        for name,digest in values['review1']['reports_sha256'].items():assert sha(root/name/'report.json')==digest
        for source in sources:
            relative=source.relative_to(repo);target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            r['sources'][relative.as_posix()]=sha(source)
        previous=args.workspace/'references/analysis/F2_sideband_v1/final1'
        for name in ('C_files_sha256.json','voice_files_sha256.json'):shutil.copy2(previous/name,final/name)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        shutil.copy2(figure,final/figure.name)
        source=load(repo/'references/segments_v1.json')['sources']['F2']
        parents={name:dict(path='baselines/'+name+'/manifest.json',
            sha256=sha(args.workspace/'baselines'/name/'manifest.json'))
            for name in ('F2_sideband_v1','F2_local_envelopes_v1')}
        comparisons=audit['comparisons']
        r.update(result='known_flat_bound_defect_corrected_local_recording_residual_persists_NOT_shared_phase_DNA',
            real_audio_read=True,source_versions=versions,
            input_media=[dict(path=source[k],sha256=source[k+'_sha256']) for k in ('raw','master')],
            prior_manifests=parents,catalogue_sha256=sha(repo/'references/segments_v1.json'),
            data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            counts=audit['counts'],audit_errors=audit['errors'],
            known_old_waveform_errors=[row['waveform_relative_error'] for row in diagnosis['cases']],
            known_new_cases=[{k:v for k,v in row.items() if k!='fit'} for row in actual['controls']['cases']],
            reference_conversion_bound_error=actual['controls']['reference_conversion_bound_error'],
            engineering_prior='q_bound=B_ref*nominal_bin/reference_bin; B_ref2Hz/s, first observed main reference',
            parameter_count_changed=False,truth_used_as_phase_fit_initialization=False,
            diagnostic_reporting_only_revision=True,diagnostic_arrays_and_fits_exact=True,
            comparisons=comparisons,
            real_local_cost_reduction_percent_range=[min(row['channels'][0]['local_cost_reduction_percent'] for row in comparisons),
                max(row['channels'][0]['local_cost_reduction_percent'] for row in comparisons)],
            conditional_Q_ranges={prefix:[min(row['channels'][0][prefix+'_Q_reduction_percent'] for row in comparisons),
                max(row['channels'][0][prefix+'_Q_reduction_percent'] for row in comparisons)] for prefix in ('old','new')},
            main_in_bound_flags_are_changed_prior_NOT_real_accuracy=True,
            C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            figures_visually_checked=True,all_executed_diagnostic_sources_retained=True,
            existing55CTests_rerun=False,model_exported=False,runtime_changed=False,
            real_nonlinear_fits=18,audit_real_nonlinear_resolves=0,shared_phase_clock_fit=False,
            phase_extracted_real_model_permitted=False,physical_AM_FM_source_classified=False,
            high_frequency_recovered=False,RPM_inferred=False,vehicle_timbre_accepted=False,
            idle_acceleration_complete=False,goal_complete=False,moving35='held_unchanged',
            original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_conditional_sideband_contract_counterexamples_and_all18plus72_projections_audited',
            current_goal_turn='progress_known_chirp_clipping_diagnosis_rate_law_all18_fits_plus72_subspaces_independently_audited',
            next_step='Known same-global-trajectory, deliberate phase-offset and nonquadratic controls before original six adjacent overlapping-window complex phase comparisons. No aligning away offsets or forcing gaps. Shared samples are not independent heldouts/common-clock qualification. Keep originalfailed36/all17/full33/individual14k/originalE before shared-phase realDNA.',
            limits=audit['limits']+actual['limits'])
        verify_current(r);save(summary,r)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(final/'report.json',r)
    print(json.dumps(dict(result=r['result'],counts=r['counts'])),flush=True)
elif args.stage=='freeze':
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    r=load(summary);verify_current(r);assert sha(summary)==sha(final/'report.json')
    frozen.mkdir(exist_ok=False);shutil.copytree(root,frozen/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(frozen/'source.zip'),commit],cwd=repo,check=True)
    files=[dict(path=x.relative_to(frozen).as_posix(),bytes=x.stat().st_size,sha256=sha(x))
        for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=files,
        prior_manifests=r['prior_manifests'],real_audio_read=True,profiles_exported=0,
        physical_source_classified=False,vehicle_timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(x['bytes'] for x in files),
        commit=commit,manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
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
    print(json.dumps(dict(result='all_frozen_payloads_sources_prior_evidence_media_C_voices_verified',
        files=len(m['files']),manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
