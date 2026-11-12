"""Publish and freeze the finite-aperture principle study, including rejection."""
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

base=args.workspace/'references/analysis/aperture_model_v1'
final=base/'final1'
summary=repo/'research/aperture_model_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.aperture-model-publication/1',result='running',reports={},sources={})
    try:
        self_copy=final/'exact_sources/tools/package_aperture_model_v1.py'
        self_copy.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(Path(__file__),self_copy)
        report['sources']['tools/package_aperture_model_v1.py']=sha(Path(__file__))
        reports={}
        for name in ('validate1','diagnose1','diagnose2','diagnose3'):
            path=base/name/'report.json'
            result=load(path)
            assert result['result'] in ('rejected','failed','diagnosed_no_qualification_change')
            for relative,digest in result['sources'].items():
                assert sha(path.parent/'exact_sources'/relative)==digest
                if name in ('validate1','diagnose3'):
                    assert sha(repo/relative)==digest
            reports[name]=result
            report['reports'][name]=dict(path=path.relative_to(args.workspace).as_posix(),sha256=sha(path),result=result['result'])
        validation=reports['validate1']
        diagnosis=reports['diagnose3']
        plan=load(repo/'research/aperture_model_v1_plan.json')
        assert [row['case'] for row in validation['cases']]==plan['cases']
        assert validation['controls']['passed'] and not validation['real_source_permitted']
        failed=[row for row in validation['cases'] if not row['passed']]
        assert len(failed)==1 and failed[0]['case']['id']=='independent_phase_5'
        assert not failed[0]['case'].get('negative')
        assert diagnosis['validation_report_sha256']==sha(base/'validate1/report.json')
        assert diagnosis['plot_sha256']==sha(base/'diagnose3/common_phase_bias.png')
        assert diagnosis['continued_from']['report_sha256']==sha(base/'diagnose2/report.json')
        assert diagnosis['continued_from']['arrays_sha256']==sha(base/'diagnose2/diagnosis.npz')
        assert diagnosis['fixed_true_phase']['uses_exact_analytic_phase']
        assert reports['diagnose1']['failure_stage']=='module import before output creation'
        assert 'threadpoolctl' in reports['diagnose1']['error']
        old=args.workspace/'references/analysis/supported_root_v1/final1'
        for filename in ('C_files_sha256.json','voice_files_sha256.json'):
            hashes=load(old/filename)
            assert all(sha(repo/name)==digest for name,digest in hashes.items())
            shutil.copy2(old/filename,final/filename)
        c_hashes=load(final/'C_files_sha256.json')
        assert len(c_hashes)==540
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
            cwd=repo,check=True,capture_output=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        positive=[row for row in validation['cases'] if not row['case'].get('negative')]
        capped=[row['case']['id'] for row in validation['cases'] if not row['fit']['success']]
        report.update(result='finite_aperture_principle_incomplete',total_cases=7,gate_passed_cases=6,
            positive_cases=6,gate_passed_positive_cases=5,negative_cases=1,correctly_rejected_negative_cases=1,
            controls=validation['controls'],failed_positive=failed[0],solver_not_converged_cases=capped,
            continuation=diagnosis['continued'],fixed_true_phase=diagnosis['fixed_true_phase'],conclusion=diagnosis['conclusion'],
            source_audio_read=False,model_exported=False,real_source_permitted=False,full33_qualification_replaced=False,
            individual14kHz_retention_demonstrated=False,vehicle_timbre_accepted=False,idle_acceleration_complete=False,
            runtime_changed=False,C_H=540,existing_Ctests_rerun=False,moving35='held_unchanged',new_media_downloaded=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            plot_sha256=diagnosis['plot_sha256'],
            goal_turn_classification='progress_finite_aperture_controls_and_shared_phase_model_limit',
            limits=['Sparse known low-band topology is not a general vehicle source extractor',
                'Five positive gate passes do not establish optimizer convergence or real idle/acceleration timbre',
                'Independent-phase contamination remains a required positive; do not relabel it or relax gates',
                'Original33 plus individual high-frequency and real-source holdouts remain required',
                'F1/F2/F3 and A-low review questions stay pending; no duplicate requests'])
        docs=[repo/'AGENTS.md',repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',
            repo/'research/有限窗共同相位V1.md',repo/'research/怠速与加速完成度V1.md']
        sources=set(docs+[Path(__file__)])
        for name in ('validate1','diagnose3'):
            sources.update(repo/relative for relative in reports[name]['sources'])
        for source in sources:
            relative=source.relative_to(repo)
            target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            report['sources'][relative.as_posix()]=sha(source)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        shutil.copy2(base/'diagnose3/common_phase_bias.png',final/'common_phase_bias.png')
        save(summary,report)
    except Exception as exc:
        report.update(result='failed',error=repr(exc))
        raise
    finally:
        save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],passed=6,total=7,real_models=0)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary)
    assert report['result']=='finite_aperture_principle_incomplete' and sha(summary)==sha(final/'report.json')
    for relative,digest in report['sources'].items():
        assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for item in report['reports'].values():
        assert sha(args.workspace/item['path'])==item['sha256']
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/name)==digest for name,digest in load(final/filename).items())
    out=args.workspace/'baselines/aperture_model_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/supported_root_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_supported_manifest=prior.relative_to(args.workspace).as_posix(),prior_supported_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path'])==item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
