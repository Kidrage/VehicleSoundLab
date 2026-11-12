"""Freeze the declared amplitude-resolution attempt and initialization diagnosis."""
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

base=args.workspace/'references/analysis/envelope_resolution_v1'
final=base/'final1'
summary=repo/'research/envelope_resolution_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.envelope-resolution-publication/1',result='running',reports={},sources={})
    try:
        reports={}
        for name in ('dense1','bias1','tangent1','tangent2'):
            path=base/name/'report.json'
            value=load(path)
            assert value['result'] in ('dense_diagnostic_rejected','diagnosed_no_qualification_change',
                'diagnosed_linear_sensitivity_no_qualification_change')
            for relative,digest in value['sources'].items():
                assert sha(path.parent/'exact_sources'/relative)==digest
                if not (name=='tangent1' and relative=='tools/diagnose_envelope_tangent_v1.py'):
                    assert sha(repo/relative)==digest
            assert not value['real_audio_read'] and not value['real_source_permitted'] and not value['qualification_changed']
            filename='phase_comparison.png' if name=='dense1' else 'initialization_comparison.png' if name=='bias1' else 'tangent_decomposition.png'
            assert value['plot_sha256']==sha(path.parent/filename)
            reports[name]=value
            report['reports'][name]=dict(path=path.relative_to(args.workspace).as_posix(),sha256=sha(path),result=value['result'])
        dense=reports['dense1']
        bias=reports['bias1']
        tangent=reports['tangent2']
        assert bias['parent_report_sha256']==sha(base/'dense1/report.json')
        assert reports['tangent1']['parent_report_sha256']==tangent['parent_report_sha256']==sha(base/'dense1/report.json')
        assert reports['tangent1']['components']==tangent['components']
        assert reports['tangent1']['total_linear_phase_p95_cycles']==tangent['total_linear_phase_p95_cycles']
        assert not tangent['nonlinear_estimator_run'] and tangent['linear_projection_solves']
        assert tangent['projected_decomposition_maximum_error']<1e-12
        assert dense['geometry']['spacing']==5 and dense['geometry']['previous_spacing']==10
        assert dense['transfer']['maximum_sample_envelope_phase_difference']<1e-11
        assert dense['fit']['evaluations']==120 and dense['fit']['parameters']==514
        assert not dense['assessment']['qualified'] and dense['controls']['passed'] and bias['controls']['passed']
        parent=args.workspace/'references/analysis/observed_topology_v1/final1'
        for filename in ('C_files_sha256.json','voice_files_sha256.json'):
            hashes=load(parent/filename)
            assert all(sha(repo/name)==digest for name,digest in hashes.items())
            shutil.copy2(parent/filename,final/filename)
        assert len(load(final/'C_files_sha256.json'))==540
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
            cwd=repo,check=True,capture_output=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        sources={Path(__file__),repo/'AGENTS.md',repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md',repo/'research/实慢幅度分辨率V1.md',repo/'research/怠速与加速完成度V1.md',
            repo/'tools/validate_envelope_resolution_v1.py'}
        for value in reports.values():
            sources.update(repo/relative for relative in value['sources'])
        for source in sources:
            relative=source.relative_to(repo)
            target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            report['sources'][relative.as_posix()]=sha(source)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        for folder,filename in (('dense1','phase_comparison.png'),('bias1','initialization_comparison.png'),('tangent2','tangent_decomposition.png')):
            shutil.copy2(base/folder/filename,final/filename)
        report.update(result='envelope_resolution_not_qualified',dense_original_phase_p95=dense['original_assessment']['point_phase_p95_cycles'],
            dense_refined_phase_p95=dense['assessment']['point_phase_p95_cycles'],dense_fit=dense['fit'],
            initialization_diagnosis=bias['comparison'],fixed_true_phase=bias['fixed_true_phase'],fresh_fit=bias['fresh'],
            tangent_components=tangent['components'],tangent_phase_condition=tangent['profiled_phase_condition'],
            actual_vs_linear_phase_correlation=tangent['actual_vs_linear_correlation'],
            tangent_interpretation='Local unweighted noise sensitivity dominates in this fixture; not calibrated real-source uncertainty or a bounded robust fit',
            nested_transfer=dense['transfer'],geometry=dense['geometry'],controls=bias['controls'],
            original17_rerun=False,full33_replaced=False,individual14kHz_demonstrated=False,
            all17_validator='authored but not executed because declared dense candidate failed',
            source_audio_read=False,model_exported=False,real_source_permitted=False,
            runtime_changed=False,C_H=540,existing_Ctests_rerun=False,moving35='held_unchanged',
            idle_acceleration_complete=False,vehicle_timbre_accepted=False,new_media_downloaded=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            goal_turn_classification='progress_dense_amplitude_resolution_and_initialization_evidence',
            next_step='Constrain true amplitude temporal bandwidth and audit observation-noise amplification before any more resolution increase; qualify original17/full33/individual14kHz before original E',
            limits=['Observed-gap spline spacing is not a strict amplitude bandwidth or physical order/RPM identification',
                'Oracle branch is diagnostic only and never initializes the estimator',
                'Dense positive remains failed; do not drop it, relax gates or call iteration-capped solves converged',
                'All17, original33, individual14kHz and original E remain required before real extraction',
                'F1/F2/F3 and original A-low listening questions remain pending; no duplicate requests'])
        save(summary,report)
    except Exception as exc:
        report.update(result='failed',error=repr(exc))
        raise
    finally:
        save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],phase_before=report['dense_original_phase_p95'],
        phase_after=report['dense_refined_phase_p95'],real_models=0)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary)
    assert report['result']=='envelope_resolution_not_qualified' and sha(summary)==sha(final/'report.json')
    for relative,digest in report['sources'].items():
        assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for value in report['reports'].values():
        assert sha(args.workspace/value['path'])==value['sha256']
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/name)==digest for name,digest in load(final/filename).items())
    out=args.workspace/'baselines/envelope_resolution_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/observed_topology_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_observed_manifest=prior.relative_to(args.workspace).as_posix(),prior_observed_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path'])==item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
