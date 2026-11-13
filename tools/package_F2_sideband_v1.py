"""Freeze conditional sideband contracts, counterexamples and all18+72 real observations."""
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
root=args.workspace/'references/analysis/F2_sideband_v1';final=root/'final1'
summary=repo/'research/F2_sideband_v1_summary.json';frozen=args.workspace/'baselines/F2_sideband_v1'


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
    final.mkdir(exist_ok=False);r=dict(schema='vsl.F2-sideband-final/1',result='running',sources={},reports={})
    try:
        locations={name:root/name for name in ('observe1','audit1','subspaces1','subspaces_audit1','review1','review2')}
        values={name:load(path/'report.json') for name,path in locations.items()}
        actual=values['observe1'];audit=values['audit1'];spaces=values['subspaces1'];checked=values['subspaces_audit1']
        assert actual['controls']['passed'] and spaces['controls']['passed']
        assert audit['counts']==dict(channel_projections=18,full_rank_projections=18)
        assert checked['counts']==dict(projections=72,quadrature_lower_training_cost_windows=9,windows=9,physical_AM_FM_classifications=0)
        assert audit['actual_report_sha256']==spaces['parent_report_sha256']==checked['parent_report_sha256']==sha(root/'observe1/report.json')
        assert checked['actual_report_sha256']==sha(root/'subspaces1/report.json')
        sources={Path(__file__),repo/'AGENTS.md',repo/'research/F2边带与相位坐标V1.md',repo/'research/F2_sideband_v1_plan.json',
            repo/'research/F2_sideband_subspaces_v1_plan.json',repo/'handoff/研究续接.md',repo/'handoff/算法说明.md',
            repo/'handoff/开发留痕.md',repo/'research/怠速与加速完成度V1.md'}
        versions={}
        for name,value in values.items():
            assert not value['model_exported'] and not value['runtime_changed']
            r['reports'][name]=dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),sha256=sha(locations[name]/'report.json'),result=value['result'])
            for file,digest in value['sources'].items():
                assert sha(locations[name]/'exact_sources'/file)==digest
                if name!='review1':assert sha(repo/file)==digest
                versions.setdefault(file,{})[name]=digest;sources.add(repo/file)
        for name in ('review1','review2'):
            assert values[name]['plot_sha256']==sha(root/name/'F2_sideband_evidence.png')
            for key,digest in values[name]['reports_sha256'].items():assert sha(root/key/'report.json')==digest
        for source in sources:
            relative=source.relative_to(repo);target=final/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target);r['sources'][relative.as_posix()]=sha(source)
        previous=args.workspace/'references/analysis/F2_local_envelopes_v1/final1'
        for name in ('C_files_sha256.json','voice_files_sha256.json'):shutil.copy2(previous/name,final/name)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        shutil.copy2(root/'review2/F2_sideband_evidence.png',final/'F2_sideband_evidence.png')
        source=load(repo/'references/segments_v1.json')['sources']['F2']
        parents={name:dict(path='baselines/'+name+'/manifest.json',sha256=sha(args.workspace/'baselines'/name/'manifest.json')) for name in ('F2_local_envelopes_v1','F2_peak_identity_v1')}
        ranges={name:[min(row['channels'][0][name+'_reduction_percent'] for row in spaces['observations']),
            max(row['channels'][0][name+'_reduction_percent'] for row in spaces['observations'])] for name in ('amplitude','quadrature','joint')}
        r.update(result='conditional_fixed3Hz_sideband_observations_frozen_NOT_physical_source_or_DNA_classification',
            real_audio_read=True,source_versions=versions,input_media=[dict(path=source[k],sha256=source[k+'_sha256']) for k in ('raw','master')],
            prior_manifests=parents,catalogue_sha256=sha(repo/'references/segments_v1.json'),data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            counts=dict(full_sideband=audit['counts'],subspaces=checked['counts']),condition_ranges=dict(full=audit['condition_range'],subspaces=checked['condition_range']),
            audit_errors=dict(full=audit['errors'],subspaces=checked['errors']),cost_reduction_percent_ranges=ranges,
            known_AM_independent_pair_equivalence=audit['independent_AM_pair_identity_error'],
            known_true_PM_first_sideband_error=audit['independent_true_PM_coefficient_error'],
            known_halfbin_error_is_counterexample_only=True,comparisons=checked['comparisons'],
            C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            figures_visually_checked=True,all_executed_review_sources_retained=True,existing55CTests_rerun=False,
            model_exported=False,runtime_changed=False,nonlinear_fit_run=False,shared_phase_clock_fit=False,
            phase_extracted_real_model_permitted=False,physical_AM_FM_source_classified=False,high_frequency_recovered=False,
            RPM_inferred=False,vehicle_timbre_accepted=False,idle_acceleration_complete=False,goal_complete=False,
            moving35='held_unchanged',original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_positive_affine_amplitude_hypothesis_all18_real_fits_audited_no_adoption',
            current_goal_turn='progress_known_sideband_contract_nonidentifiability_and_wrongcoordinate_counterexamples_all18plus72_real_linear_projections_independently_audited',
            next_step='Known harmonic-family smooth chirp with no3Hzmod checks whether original flat q+/-2 coordinate truncation creates Q-like residual. Observed phase initialization only; truth assessment/operator contract only; no blind real bounds/rate/budget sweeps. Originalfailed36/all17/full33/individual14k/originalE remain before shared-phase realDNA.',
            limits=audit['limits']+checked['limits']+actual['limits'])
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
    print(json.dumps(dict(result='all_frozen_payloads_sources_prior_evidence_media_C_voices_verified',files=len(m['files']),manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
