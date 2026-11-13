"""Freeze fixed variation hypotheses, known counterexamples and all12 audited groups."""
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
root=args.workspace/'references/analysis/F2_variation_projection_v1';final=root/'final1'
summary=repo/'research/F2_variation_projection_v1_summary.json';frozen=args.workspace/'baselines/F2_variation_projection_v1'


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
    final.mkdir(exist_ok=False);r=dict(schema='vsl.F2-variation-projection-final/1',result='running',sources={},reports={})
    try:
        locations={n:root/n for n in ('observe1','audit1','review1')};values={n:load(path/'report.json') for n,path in locations.items()}
        actual=values['observe1'];audit=values['audit1'];review=values['review1']
        assert actual['controls']['passed'] and audit['known_controls_replayed']
        assert audit['actual_report_sha256']==sha(root/'observe1/report.json')
        assert audit['counts']==dict(three_line_observations=12,rank_one_projections=24,conditional_omitted_line_predictions=72,native_frequency_differences=864000)
        assert actual['real_nonlinear_fits']==audit['real_nonlinear_resolves']==audit['physical_source_classifications']==0
        sources={Path(__file__),repo/'AGENTS.md',repo/'research/F2共同变化投影V1.md',repo/'research/F2_variation_projection_v1_plan.json',
            repo/'handoff/研究续接.md',repo/'handoff/算法说明.md',repo/'handoff/开发留痕.md',repo/'research/怠速与加速完成度V1.md'}
        for name,value in values.items():
            assert not value['model_exported'] and not value['runtime_changed']
            r['reports'][name]=dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),sha256=sha(locations[name]/'report.json'),result=value['result'])
            for file,digest in value['sources'].items():
                assert sha(repo/file)==sha(locations[name]/'exact_sources'/file)==digest;sources.add(repo/file)
        figure=root/'review1/F2_variation_projection.png';assert review['plot_sha256']==sha(figure)
        for name,digest in review['reports_sha256'].items():assert sha(root/name/'report.json')==digest
        for source in sources:
            relative=source.relative_to(repo);target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);r['sources'][relative.as_posix()]=sha(source)
        previous=args.workspace/'references/analysis/F2_overlap_phase_v1/final1'
        for name in ('C_files_sha256.json','voice_files_sha256.json'):shutil.copy2(previous/name,final/name)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md');shutil.copy2(figure,final/figure.name)
        source=load(repo/'references/segments_v1.json')['sources']['F2']
        parents={name:dict(path='baselines/'+name+'/manifest.json',sha256=sha(args.workspace/'baselines'/name/'manifest.json'))
            for name in ('F2_overlap_phase_v1','F2_rate_coordinates_v1')}
        channels=[x for row in actual['observations'] for x in row['channels']]
        ranges={name:dict(residual_squared_fraction=[min(x['observations'][name]['residual_squared_fraction'] for x in channels),max(x['observations'][name]['residual_squared_fraction'] for x in channels)],
            conditional_omitted_line_rms_Hz=[min(v for x in channels for v in x['observations'][name]['omitted_line_prediction_rms_error_Hz']),max(v for x in channels for v in x['observations'][name]['omitted_line_prediction_rms_error_Hz'])])
            for name in ('harmonic_hypothesis','equal_Hz')}
        r.update(result='fixed2_3_5_geometry_favored_in_local_disagreements_NOT_physical_common_source_or_clock',
            real_audio_read=True,input_media=[dict(path=source[k],sha256=source[k+'_sha256']) for k in ('raw','master')],
            prior_manifests=parents,catalogue_sha256=sha(repo/'references/segments_v1.json'),data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            counts=audit['counts'],audit_errors=audit['errors'],known_complex_source_error=audit['known_complex_source_error'],
            known_scalar_metric_error=audit['known_scalar_metric_error'],known_cases=[{k:x[k] for k in ('id','waveform_relative_errors','bounds','observations','truth_used_as_fit_initialization')} for x in actual['controls']['cases']],
            independent_program_identity_error=actual['controls']['independent_program_identity_error'],actual_ranges=ranges,
            comparisons=audit['comparisons'],real_nonlinear_fits=0,physical_harmonic_orders_verified=False,
            physical_source_classifications=0,independent_heldout_validation=False,shared_phase_clock_fit=False,
            phase_extracted_real_model_permitted=False,current_g_may_drive_synthesis=False,
            C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            figures_visually_checked=True,existing55CTests_rerun=False,model_exported=False,runtime_changed=False,
            high_frequency_recovered=False,RPM_inferred=False,vehicle_timbre_accepted=False,idle_acceleration_complete=False,
            goal_complete=False,moving35='held_unchanged',original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_endpoint_precision_repaired_all18corrections72overlaps_audited_frozen_pushed',
            current_goal_turn='progress_known_common_cubic_neighbor_and_identity_counterexamples_all12fixed_geometry_groups_independently_audited',
            next_step='Return original dense36 common-phase extraction failure; continuous representation/observed initialization and band-out/noise geometry. Correlated observation phasep95 .000253653 still fails .0001. Originalfailed36/all17/full33/individual14k/originalE must pass before real sharedphaseDNA; lowband geometry is no substitute and currentg must not drive synthesis.',
            limits=audit['limits']+actual['limits'])
        verify_current(r);save(summary,r)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(final/'report.json',r)
    print(json.dumps(dict(result=r['result'],counts=r['counts'],ranges=ranges)),flush=True)
elif args.stage=='freeze':
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    r=load(summary);verify_current(r);assert sha(summary)==sha(final/'report.json')
    frozen.mkdir(exist_ok=False);shutil.copytree(root,frozen/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(frozen/'source.zip'),commit],cwd=repo,check=True)
    files=[dict(path=x.relative_to(frozen).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=files,prior_manifests=r['prior_manifests'],
        real_audio_read=True,profiles_exported=0,physical_source_classified=False,vehicle_timbre_accepted=False,goal_complete=False))
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
    print(json.dumps(dict(result='all_frozen_payloads_sources_parents_media_C_voices_verified',files=len(m['files']),manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
