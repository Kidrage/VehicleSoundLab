"""Publish measured topology and strict-input pipeline evidence without promotion."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--stage',choices=['publish','freeze'],required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

base=args.workspace/'references/analysis/observed_topology_v1'
final=base/'final1'
summary=repo/'research/observed_topology_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.observed-topology-publication/1',result='running',reports={},sources={})
    try:
        target=final/'exact_sources/tools/package_observed_topology_v1.py'
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(Path(__file__),target)
        report['sources']['tools/package_observed_topology_v1.py']=sha(Path(__file__))
        reports={}
        for name in ('observe1','observe2','validate1','validate2','audit1','dense_diagnose1'):
            path=base/name/'report.json'
            value=load(path)
            assert value['result'] in ('observed','failed','passed','rejected','strict_input_pipeline_audited',
                'diagnosed_dense_failure_no_qualification_change')
            for relative,digest in value['sources'].items():
                assert sha(path.parent/'exact_sources'/relative)==digest
                if name in ('observe2','validate2','audit1','dense_diagnose1'):
                    assert sha(repo/relative)==digest
            reports[name]=value
            report['reports'][name]=dict(path=path.relative_to(args.workspace).as_posix(),sha256=sha(path),result=value['result'])
        validation=reports['validate2']
        audit=reports['audit1']
        settings=load(repo/'research/observed_topology_v1_plan.json')
        plan=load(repo/settings['base_plan'])
        variant=load(repo/settings['minority_plan'])
        assert [row['case'] for row in validation['cases']]==plan['cases']+variant['added_cases']+settings['added_cases']
        assert len(validation['cases'])==17 and not validation['real_source_permitted']
        assert reports['observe1']['cases']==reports['observe2']['cases']
        assert reports['observe2']['controls']['passed']
        assert audit['validation_report_sha256']==sha(base/'validate2/report.json')
        assert reports['validate1']['result']=='failed' and 'not monotonic' in reports['validate1']['error']
        assert validation['completed_run_sha256']==sha(base/'validate1/report.json')
        assert audit['observation_report_sha256']==sha(base/'observe2/report.json')
        assert audit['plot_sha256']==sha(base/'audit1/observed_topology.png')
        assert all(audit['input_boundary'].values()) and not audit['optimizer_rerun']
        assert audit['total_cases']==17 and all(row['effective_inputs_exact'] for row in audit['cases'])
        positive=[row for row in validation['cases'] if not row['case'].get('negative')]
        negative=[row for row in validation['cases'] if row['case'].get('negative')]
        reused=[row for row in validation['cases'] if row['fit_reused']]
        assert len(positive)==14 and len(negative)==3 and len(reused)==10
        dense=reports['dense_diagnose1']
        assert dense['validation_report_sha256']==sha(base/'validate2/report.json')
        assert dense['plot_sha256']==sha(base/'dense_diagnose1/dense_phase_diagnosis.png')
        assert not dense['qualification_changed'] and not dense['real_source_permitted']
        assert dense['continued']['evaluations']==300 and not dense['continued']['assessment']['qualified']
        assert dense['fixed_true_phase']['uses_exact_analytic_phase'] and not dense['fixed_true_phase']['may_authorize_estimator']
        assert not dense['comparison']['global_optimum_or_identifiability_proven']
        old=args.workspace/'references/analysis/minority_phase_v1/final1'
        for filename in ('C_files_sha256.json','voice_files_sha256.json'):
            hashes=load(old/filename)
            assert all(sha(repo/name)==digest for name,digest in hashes.items())
            shutil.copy2(old/filename,final/filename)
        assert len(load(final/'C_files_sha256.json'))==540
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
            cwd=repo,check=True,capture_output=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        dual=next(row for row in validation['cases'] if row['case']['id']=='two_independent_partials')
        audited_dual=next(row for row in audit['cases'] if row['id']=='two_independent_partials')
        report.update(result='observed_topology_principle_passed_not_full_qualification' if validation['result']=='passed' else 'observed_topology_principle_rejected',
            total_cases=17,passed_cases=sum(row['passed'] for row in validation['cases']),positive_cases=14,
            passed_positive_cases=sum(row['passed'] for row in positive),negative_cases=3,
            correctly_rejected_negative_cases=sum(not row['observation_supported'] for row in negative),
            exact_reused_fits=10,new_fits=sum(row['status'] in ('measured','observation_rejected') and not row['fit_reused'] for row in validation['cases']),
            topology_early_rejections=sum(row['status']=='topology_rejected' for row in validation['cases']),
            initial_candidate_count={row['case']['id']:len(row['topology']['selected_orders']) for row in validation['cases']},
            selected_departures={row['case']['id']:row.get('fit',{}).get('selected_orders',[]) for row in validation['cases']},
            additional6_8=dict(phase_p95_cycles=dual['assessment']['point_phase_p95_cycles'],
                fitted_amplitude=audited_dual['fitted_amplitudes'][audited_dual['inferred_orders'].index(6.8)],
                discovery_threshold=dual['topology']['threshold']),
            dense36=dict(original_phase_p95_cycles=next(row for row in positive if row['case']['id']=='unknown_thirty_six')['assessment']['point_phase_p95_cycles'],
                continued=dense['continued'],fixed_true_phase=dense['fixed_true_phase'],comparison=dense['comparison'],
                qualification='failed_positive_retained'),
            input_boundary=audit['input_boundary'],source_audio_read=False,model_exported=False,
            real_source_permitted=False,full33_qualification_replaced=False,individual14kHz_retention_demonstrated=False,
            known_active_line_list_required=False,declared_fifth_grid_still_required=True,physical_source_identity_inferred=False,
            vehicle_timbre_accepted=False,idle_acceleration_complete=False,runtime_changed=False,C_H=540,
            existing_Ctests_rerun=False,moving35='held_unchanged',new_media_downloaded=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            plot_sha256=audit['plot_sha256'],goal_turn_classification='progress_measured_active_topology_and_strict_input_reconstruction',
            next_step='Resolve dense-spectrum phase/amplitude approximation bias with independently validated bounded real envelopes; then all17, original33 and individual14kHz before original E',
            limits=['Active line candidates on a declared grid are not physical source identities or arbitrary lattice/RPM inference',
                'Sideband candidates may be present; do not remove them using fixture truth or raise thresholds to match truth',
                'Dense36 remains a failed positive after300 additional evaluations; small spectral residual does not certify phase',
                'A lower biased-phase objective than the fixed-true-phase fit suggests model coupling, not a proof of global optimality or nonidentifiability',
                'Original33 and high-frequency gates remain required; optimizer convergence is not established',
                'F1/F2/F3 and A-low review questions stay pending; no duplicate requests'])
        sources={Path(__file__),repo/'AGENTS.md',repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',repo/'handoff/开发留痕.md',
            repo/'research/实测声线结构V1.md',repo/'research/怠速与加速完成度V1.md'}
        for name in ('observe2','validate2','audit1','dense_diagnose1'):
            sources.update(repo/relative for relative in reports[name]['sources'])
        for source in sources:
            relative=source.relative_to(repo)
            target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            report['sources'][relative.as_posix()]=sha(source)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        shutil.copy2(base/'audit1/observed_topology.png',final/'observed_topology.png')
        shutil.copy2(base/'dense_diagnose1/dense_phase_diagnosis.png',final/'dense_phase_diagnosis.png')
        save(summary,report)
    except Exception as exc:
        report.update(result='failed',error=repr(exc))
        raise
    finally:
        save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],passed=report['passed_cases'],total=17,real_models=0)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary)
    assert report['result'] in ('observed_topology_principle_passed_not_full_qualification','observed_topology_principle_rejected')
    assert sha(summary)==sha(final/'report.json')
    for relative,digest in report['sources'].items():
        assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for item in report['reports'].values():
        assert sha(args.workspace/item['path'])==item['sha256']
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/name)==digest for name,digest in load(final/filename).items())
    out=args.workspace/'baselines/observed_topology_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/minority_phase_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_minority_manifest=prior.relative_to(args.workspace).as_posix(),prior_minority_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path'])==item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
