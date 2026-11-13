"""Freeze audited discrete correspondence and omitted-peak observations, without DNA promotion."""
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
root=args.workspace/'references/analysis/F2_peak_identity_v1';final=root/'final1'
summary=repo/'research/F2_peak_identity_v1_summary.json';frozen=args.workspace/'baselines/F2_peak_identity_v1'


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
    final.mkdir(exist_ok=False);r=dict(schema='vsl.F2-peak-identity-final/1',result='running',sources={},reports={})
    try:
        locations={name:root/name for name in ('observe1','audit1','review1','review2')}
        values={name:load(path/'report.json') for name,path in locations.items()}
        actual=values['observe1'];audit=values['audit1']
        assert actual['controls']['passed'] and audit['result']=='all_graph_edges_ambiguities_and_two_counterfactual_fits_independently_audited'
        assert audit['actual_report_sha256']==sha(root/'observe1/report.json')
        assert not audit['actual_fits_resolved_again']
        sources={Path(__file__),repo/'AGENTS.md',repo/'research/F2谱峰身份V1.md',repo/'research/F2_peak_identity_v1_plan.json',
            repo/'handoff/研究续接.md',repo/'handoff/算法说明.md',repo/'handoff/开发留痕.md',repo/'research/怠速与加速完成度V1.md'}
        versions={}
        for name,value in values.items():
            assert not value['model_exported'] and not value['runtime_changed']
            r['reports'][name]=dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),sha256=sha(locations[name]/'report.json'),result=value['result'])
            for file,digest in value['sources'].items():
                assert sha(locations[name]/'exact_sources'/file)==digest
                if name!='review1':assert sha(repo/file)==digest
                versions.setdefault(file,{})[name]=digest;sources.add(repo/file)
        for name in ('review1','review2'):
            assert values[name]['input_report_sha256']==sha(root/'observe1/report.json')
            assert values[name]['audit_report_sha256']==sha(root/'audit1/report.json')
            assert values[name]['plot_sha256']==sha(root/name/'F2_peak_identity.png')
        for source in sources:
            relative=source.relative_to(repo);target=final/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target);r['sources'][relative.as_posix()]=sha(source)
        previous=args.workspace/'references/analysis/F2_local_chirps_v1/final1'
        for name in ('C_files_sha256.json','voice_files_sha256.json'):shutil.copy2(previous/name,final/name)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        shutil.copy2(root/'review2/F2_peak_identity.png',final/'F2_peak_identity.png')
        source=load(repo/'references/segments_v1.json')['sources']['F2']
        parents={name:dict(path='baselines/'+name+'/manifest.json',sha256=sha(args.workspace/'baselines'/name/'manifest.json')) for name in ('F2_local_chirps_v1','state_media_v1')}
        r.update(result='audited_peak_rank_identity_and_omitted37_counterfactual_frozen_not_idle_DNA',
            real_audio_read=True,source_versions=versions,input_media=[dict(path=source[k],sha256=source[k+'_sha256']) for k in ('raw','master')],
            prior_manifests=parents,catalogue_sha256=sha(repo/'references/segments_v1.json'),data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            graph_statistics=audit['graph_statistics'],counterfactual=audit['counterfactual'],audit_errors=audit['errors'],
            known_six_line_wave_error=actual['controls']['six_tone_control']['waveform_relative_error'],
            C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            figure_visually_checked=True,all_executed_review_sources_retained=True,existing55CTests_rerun=False,
            model_exported=False,runtime_changed=False,actual_fits_resolved_again=False,shared_phase_clock_fit=False,
            phase_extracted_real_model_permitted=False,RPM_inferred=False,vehicle_timbre_accepted=False,
            idle_acceleration_complete=False,goal_complete=False,moving35='held_unchanged',
            original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_native_peak_failures_neighbor_interference_and18local_chirp_fits_independently_audited',
            current_goal_turn='progress_allpeak_rank_independent_ambiguity_preserving_correspondence_and_two_omittedpeak_real_counterfactual_fits_independently_audited',
            next_step='Known time-varying amplitude versus chirp mismatch qualification before real local envelopes; no blind bounds/windows/degrees/iteration sweeps. Originalfailed36/all17/full33/individual14k/originalE still required before phase-extracted real models.',
            limits=audit['limits']+actual['limits'])
        verify_current(r);save(summary,r)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(final/'report.json',r)
    print(json.dumps(dict(result=r['result'],counterfactual=r['counterfactual'])),flush=True)
elif args.stage=='freeze':
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    r=load(summary);verify_current(r);assert sha(summary)==sha(final/'report.json')
    frozen.mkdir(exist_ok=False);shutil.copytree(root,frozen/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(frozen/'source.zip'),commit],cwd=repo,check=True)
    files=[dict(path=x.relative_to(frozen).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=files,prior_manifests=r['prior_manifests'],
        real_audio_read=True,profiles_exported=0,vehicle_timbre_accepted=False,goal_complete=False))
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
