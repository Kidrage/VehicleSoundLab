"""Publish/freeze constrained joint candidates, their raw traces and diagnoses."""
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
base=args.workspace/'references/analysis/joint_trust_v1'
final=base/'final1'
summary=repo/'research/joint_trust_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.joint-trust-publication/1',result='running',sources={},reports={})
    try:
        reports={}
        expected_changes={'dense1':{'tools/joint_trust_v1/constraints.py','tools/joint_trust_v1/checks.py',
            'tools/joint_trust_v1/fit.py','tools/diagnose_joint_trust_v1.py'},
            'noise_budget1':{'tools/diagnose_joint_noise_budget_v1.py'},
            'plots1':{'tools/plot_joint_noise_budget_v1.py'}}
        for name in ('dense1','dense2','noise_budget1','noise_budget2','noise_budget3','audit1','plots1','plots2'):
            folder=base/name
            value=load(folder/'report.json')
            assert not value['real_audio_read'] and not value['real_source_permitted']
            reports[name]=value
            changed=set()
            for relative,digest in value['sources'].items():
                assert sha(folder/'exact_sources'/relative)==digest
                if sha(repo/relative)!=digest:
                    changed.add(relative)
            assert changed==expected_changes.get(name,set()), (name,changed)
            report['reports'][name]=dict(path=(folder/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(folder/'report.json'),result=value['result'],changed_executed_sources=sorted(changed))
        for name in ('dense1','dense2'):
            assert reports[name]['result']=='dense_diagnostic_rejected'
            assert not reports[name]['assessment']['qualified'] and reports[name]['fit']['iterations']==20
            assert reports[name]['controls']['passed']
        audit=reports['audit1']
        assert audit['result']=='reconstructed_joint_candidates_and_certificates'
        assert audit['precise_entire_trace_exact'] and len(audit['precise_trace'])==20
        assert [(r['qp_certified'],r['qp_uncertified']) for r in audit['cases']]==[(18,2),(2,18)]
        assert all(r['all_candidate_and_objective_values_exact'] for r in audit['precise_trace'])
        budget=reports['noise_budget3']
        assert budget['result']=='diagnosed_known_noise_and_representation_no_qualification'
        assert not budget['may_initialize_estimator'] and not budget['higher_order_representation_diagnostic']['actual_estimator_run']
        assert budget['diagnosis_report_sha256']==sha(base/'dense2/report.json')
        assert budget['projection_closure_maximum_error']<1e-12
        assert reports['plots2']['diagnosis_report_sha256']==sha(base/'noise_budget3/report.json')
        assert reports['plots2']['diagnostic_arrays_sha256']==sha(base/'noise_budget3/diagnostic_arrays.npz')
        previous=args.workspace/'references/analysis/absolute_amplitude_v1/final1'
        for filename in ('C_files_sha256.json','voice_files_sha256.json'):
            hashes=load(previous/filename)
            assert all(sha(repo/name)==digest for name,digest in hashes.items())
            shutil.copy2(previous/filename,final/filename)
        assert len(load(final/'C_files_sha256.json'))==540
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
            cwd=repo,capture_output=True,check=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        source={Path(__file__),repo/'AGENTS.md',repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md',repo/'research/怠速与加速完成度V1.md',repo/'research/受约束联合求解V1.md'}
        for value in reports.values():
            source.update(repo/relative for relative in value['sources'])
        for path in source:
            relative=path.relative_to(repo)
            target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
            report['sources'][relative.as_posix()]=sha(path)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        shutil.copy2(args.workspace/'tools/qp_install_report.json',final/'qp_install_report.json')
        assert sha(final/'qp_install_report.json')==reports['dense2']['qp_install_report_sha256']
        for name,filename in (('dense2','joint_trust.png'),('plots2','phase_representation.png')):
            assert sha(base/name/filename)==reports[name]['plot_sha256']
            shutil.copy2(base/name/filename,final/filename)
        report.update(result='bounded_joint_candidates_rejected_representation_diagnosed',
            candidates={name:{key:reports[name]['fit'][key] for key in ('accepted_steps','initial_cost','final_cost',
                'normalized_projection_residual','seconds')}|{'assessment':reports[name]['assessment']} for name in ('dense1','dense2')},
            independent_audit=dict(cases=audit['cases'],precise_entire_trace_exact=True,
                trace_frames=len(audit['precise_trace']),nonlinear_estimator_rerun=False,quadratic_solver_rerun=False),
            known_noise_representation={key:budget[key] for key in ('projection_norms','common_phase_representation',
                'higher_order_representation_diagnostic','above_cutoff_power_fraction','fitted_model_error_noise_correlation')},
            original17_rerun=False,full33_replaced=False,individual14kHz_demonstrated=False,
            real_source_permitted=False,source_audio_read=False,model_exported=False,runtime_changed=False,
            C_H=540,existing_Ctests_rerun=False,moving35='held_unchanged',new_media_downloaded=False,
            idle_acceleration_complete=False,vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            qp_install_report_sha256=sha(final/'qp_install_report.json'),
            goal_turn_classification='progress_actual_bounded_joint_solver_certificates_and_representation_noise_diagnosis',
            next_step='Independently validate a more accurate common-phase representation and noise sensitivity, use bounded observed-only migration, preserve minority phases/all17/full33/individual14kHz/original E; no truth-based initialization',
            limits=['Both actual dense candidates fail the original phase gate; no timbre or real extraction update',
                '18 precise QPs reached100000iterations; feasible descent steps do not prove subproblem or joint convergence',
                'Truth-only quintic representation comparison is not actual estimation, qualification or fixed-phase optimum',
                'Hard cutoff at measured half-gap would also remove much of the known true rapid phase',
                'F1/F2/F3 and original A-low remain pending; no duplicate requests'])
        save(summary,report)
    except Exception as exc:
        report.update(result='failed',error=repr(exc))
        raise
    finally:
        save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],real_models=0,precise_trace=20)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary)
    assert report['result']=='bounded_joint_candidates_rejected_representation_diagnosed'
    assert sha(summary)==sha(final/'report.json')
    for relative,digest in report['sources'].items():
        assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for value in report['reports'].values():
        assert sha(args.workspace/value['path'])==value['sha256']
    out=args.workspace/'baselines/joint_trust_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/absolute_amplitude_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_absolute_manifest=prior.relative_to(args.workspace).as_posix(),prior_absolute_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path'])==item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
