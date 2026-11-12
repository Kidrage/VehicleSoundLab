"""Publish/freeze amplitude, covariance, boundary and finite-band evidence together."""
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

analysis=args.workspace/'references/analysis'
base=analysis/'guard_observation_v1'
final=base/'final1'
summary=repo/'research/guard_observation_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.guard-observation-publication/1',result='running',reports={},sources={})
    try:
        folders={'smooth_dense1':analysis/'smooth_envelope_v1/dense1','smooth_sure1':analysis/'smooth_envelope_v1/sure1',
            'smooth_controls1':analysis/'smooth_envelope_v1/controls1','guard_dense1':base/'dense1',
            'combined1':base/'combined1','audit1':base/'audit1','band1':base/'band1','band_audit1':base/'band_audit1',
            'band_audit2':base/'band_audit2','band_oracle1':base/'band_oracle1'}
        reports={}
        for name,folder in folders.items():
            value=load(folder/'report.json')
            assert value['result'] in ('dense_diagnostic_rejected','dense_diagnostic_passed_not_full_qualification','passed',
                'reconstructed_dense_candidates_not_full_qualification','reconstructed_band_candidate_not_full_qualification',
                'diagnosed_amplitude_feasibility_no_qualification_change')
            for relative,digest in value['sources'].items():
                assert sha(repo/relative)==sha(folder/'exact_sources'/relative)==digest
            assert not value['real_audio_read']
            reports[name]=value
            report['reports'][name]=dict(path=(folder/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(folder/'report.json'),result=value['result'])
        assert reports['smooth_controls1']['result']=='passed'
        assert reports['smooth_controls1']['predictive_risk']['passed']
        assert reports['smooth_controls1']['covariance']['passed']
        audit=reports['audit1']
        assert not audit['nonlinear_estimator_rerun'] and len(audit['cases'])==4
        assert all(row['phase_and_residual_exact'] and row['assessment_exact'] for row in audit['cases'])
        boundary=audit['boundary_control']
        assert boundary['passed'] and boundary['original_observation_boundary_residual_norm']<1e-12
        assert boundary['guarded_boundary_residual_norm']>1e-4
        assert not boundary['guard_geometry']['candidate_source_orders_changed']
        band_audit=reports['band_audit1']
        assert band_audit==reports['band_audit2']
        assert band_audit['diagnosis_report_sha256']==sha(base/'band1/report.json')
        assert band_audit['original_rules_exact'] and band_audit['phase_and_projection_residual_exact']
        assert band_audit['literal_outside_band_maximum_fraction']<1e-24
        assert band_audit['assessment']==reports['band1']['assessment']
        oracle=reports['band_oracle1']
        assert oracle['diagnosis_report_sha256']==sha(base/'band1/report.json')
        assert oracle['all_qp_success'] and not oracle['may_initialize_estimator'] and not oracle['qualification_changed']
        assert oracle['actual_estimator_projection_residual']==reports['band1']['fit']['normalized_projection_residual']
        assert not (base/'validate1').exists()
        stages=['smooth_dense1','smooth_sure1','guard_dense1','combined1','band1']
        candidates=[]
        for name in stages:
            value=reports[name]
            assert value['fit']['evaluations']==120
            assert not value['real_source_permitted'] and not value['qualification_changed']
            candidates.append(dict(name=name,phase_p95_cycles=value['assessment']['point_phase_p95_cycles'],
                qualified=value['assessment']['qualified'],iteration_capped=not value['fit']['solver_success'],
                normalized_projection_residual=value['fit']['normalized_projection_residual']))
        old=analysis/'envelope_resolution_v1/final1'
        for filename in ('C_files_sha256.json','voice_files_sha256.json'):
            hashes=load(old/filename)
            assert all(sha(repo/name)==digest for name,digest in hashes.items())
            shutil.copy2(old/filename,final/filename)
        assert len(load(final/'C_files_sha256.json'))==540
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
            cwd=repo,check=True,capture_output=True)
        for folder in (base,analysis/'smooth_envelope_v1'):
            assert not list(folder.rglob('*.model')) and not list(folder.rglob('*.wav'))
        sources={Path(__file__),repo/'AGENTS.md',repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md',repo/'research/旁带观察与幅度限带V1.md',repo/'research/怠速与加速完成度V1.md',
            repo/'tools/validate_guard_observation_v1.py'}
        for value in reports.values():
            sources.update(repo/name for name in value['sources'])
        for source in sources:
            relative=source.relative_to(repo)
            target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            report['sources'][relative.as_posix()]=sha(source)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        for folder,filename in ((base/'audit1','candidate_audit.png'),(base/'band_audit1','band_certificate.png')):
            value=reports['audit1' if folder.name=='audit1' else 'band_audit1']
            assert sha(folder/filename)==value['plot_sha256']
            shutil.copy2(folder/filename,final/filename)
        report.update(result='boundary_and_bandwidth_principle_not_fully_qualified',candidates=candidates,
            boundary_alias_control=boundary,finite_band_certificate={key:band_audit[key] for key in (
                'literal_outside_band_maximum_fraction','full_period_minimum_envelope','full_period_maximum_envelope','band')},
            band_amplitude_oracle={key:oracle[key] for key in ('normalized_projection_residual_at_exact_phase',
                'actual_estimator_projection_residual','all_qp_success','worst_amplitude_rms_error','may_initialize_estimator')},
            smooth_controls=reports['smooth_controls1']['predictive_risk'],
            duplicate_band_audit=dict(first='band_audit1',repeat='band_audit2',all_report_values_exact=True,
                reason='Accidental redundant audit, both retained; no estimator rerun or outcome selection'),
            covariance_controls=reports['smooth_controls1']['covariance'],
            all17_guard_validator='authored, not executed because guard-only dense case failed',
            original17_rerun=False,full33_replaced=False,individual14kHz_demonstrated=False,
            real_source_permitted=False,source_audio_read=False,model_exported=False,runtime_changed=False,
            C_H=540,existing_Ctests_rerun=False,moving35='held_unchanged',new_media_downloaded=False,
            idle_acceleration_complete=False,vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            goal_turn_classification='progress_exact_window_covariance_boundary_alias_and_positive_finite_band_amplitude',
            next_step='Separate bounded absolute amplitudes from common/constant phases in the actual observation-only optimizer, using the convex-amplitude feasibility evidence only as diagnosis; then all17/full33/individual14kHz before original E',
            limits=['Exact first-order boundary alias is not global nonlinear nonidentifiability or physical crank/RPM evidence',
                'Local predictive risk assumes white source noise and ignores nonlinear changes/active bounds; not real uncertainty calibration',
                'A finite-band amplitude certificate does not establish phase accuracy, real idle timbre or full state coverage',
                'All failed positive attempts and exact executed sources are retained; no gate-based parameter sweep',
                'F1/F2/F3 and original A-low listening remain pending; no duplicate requests'])
        save(summary,report)
    except Exception as exc:
        report.update(result='failed',error=repr(exc))
        raise
    finally:
        save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],candidates=report['candidates'],real_models=0)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary)
    assert report['result']=='boundary_and_bandwidth_principle_not_fully_qualified' and sha(summary)==sha(final/'report.json')
    for relative,digest in report['sources'].items():
        assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for value in report['reports'].values():
        assert sha(args.workspace/value['path'])==value['sha256']
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/name)==digest for name,digest in load(final/filename).items())
    out=args.workspace/'baselines/guard_observation_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence/guard_observation_v1')
    shutil.copytree(analysis/'smooth_envelope_v1',out/'evidence/smooth_envelope_v1')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/envelope_resolution_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_envelope_manifest=prior.relative_to(args.workspace).as_posix(),prior_envelope_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path'])==item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
