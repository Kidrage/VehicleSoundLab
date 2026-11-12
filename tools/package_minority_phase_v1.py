"""Publish and freeze observation-selected minority phase evidence."""
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

base=args.workspace/'references/analysis/minority_phase_v1'
final=base/'final1'
summary=repo/'research/minority_phase_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.minority-phase-publication/1',result='running',reports={},sources={})
    try:
        target=final/'exact_sources/tools/package_minority_phase_v1.py'
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(Path(__file__),target)
        report['sources']['tools/package_minority_phase_v1.py']=sha(Path(__file__))
        reports={}
        for name in ('validate1','validate2','audit1'):
            path=base/name/'report.json'
            value=load(path)
            assert value['result'] in ('failed','passed','rejected','audited_no_fit_rerun')
            for relative,digest in value['sources'].items():
                assert sha(path.parent/'exact_sources'/relative)==digest
                if name!='validate1':
                    assert sha(repo/relative)==digest
            reports[name]=value
            report['reports'][name]=dict(path=path.relative_to(args.workspace).as_posix(),sha256=sha(path),result=value['result'])
        validation=reports['validate2']
        audit=reports['audit1']
        plan=load(repo/'research/aperture_model_v1_plan.json')
        variant=load(repo/'research/minority_phase_v1_plan.json')
        assert [row['case'] for row in validation['cases']]==plan['cases']+variant['added_cases']
        assert validation['controls']['passed'] and not validation['real_source_permitted']
        assert audit['validation_report_sha256']==sha(base/'validate2/report.json')
        assert audit['plot_sha256']==sha(base/'audit1/minority_phase.png')
        assert audit['selection_input_audit']['no_case_truth_or_heldout_access']
        assert reports['validate1']['result']=='failed' and 'AssertionError' in reports['validate1']['error']
        assert not reports['validate1']['cases']
        positive=[row for row in validation['cases'] if not row['case'].get('negative')]
        negative=[row for row in validation['cases'] if row['case'].get('negative')]
        reused=[row for row in validation['cases'] if row['baseline_reused']]
        assert len(positive)==10 and len(negative)==2 and len(reused)==7
        assert all(row['baseline_reused']['fixtures_exact'] and row['baseline_reused']['actual_phase_and_residual_exact'] for row in reused)
        old=args.workspace/'references/analysis/aperture_model_v1/final1'
        for filename in ('C_files_sha256.json','voice_files_sha256.json'):
            hashes=load(old/filename)
            assert all(sha(repo/name)==digest for name,digest in hashes.items())
            shutil.copy2(old/filename,final/filename)
        assert len(load(final/'C_files_sha256.json'))==540
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
            cwd=repo,check=True,capture_output=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        phases={row['case']['id']:row['assessment']['point_phase_p95_cycles'] for row in positive}
        report.update(result='minority_principle_passed_not_full_qualification' if validation['result']=='passed' else 'minority_principle_rejected',
            total_cases=12,passed_cases=sum(row['passed'] for row in validation['cases']),positive_cases=10,
            passed_positive_cases=sum(row['passed'] for row in positive),negative_cases=2,
            correctly_rejected_negative_cases=sum(not row['fit']['observation_supported'] for row in negative),
            exact_reused_baseline_cases=7,controls=validation['controls'],phase_p95_cycles=phases,
            selected_orders={row['case']['id']:row['fit']['selected_orders'] for row in validation['cases']},
            capped_joint_fits=[dict(case=row['case']['id'],order=stage['selected_order'])
                for row in validation['cases'] for stage in row['fit']['stages']
                if stage['status']=='fitted' and not stage['solver_success']],
            source_audio_read=False,model_exported=False,real_source_permitted=False,full33_qualification_replaced=False,
            individual14kHz_retention_demonstrated=False,known_carrier_topology_required=True,
            vehicle_timbre_accepted=False,idle_acceleration_complete=False,runtime_changed=False,C_H=540,
            existing_Ctests_rerun=False,moving35='held_unchanged',new_media_downloaded=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            plot_sha256=audit['plot_sha256'],goal_turn_classification='progress_observation_selected_bounded_minority_phase_model',
            next_step='Infer supported carrier topology from measurements and qualify the same finite-aperture model on all33 plus individual14kHz before the original E case',
            limits=['Known sparse topology and low-band principle do not prove a general or real engine source extractor',
                'Numerical error gates do not establish optimizer convergence, audible improvement or state coverage',
                'At most two departure partials; all-independent negative must not be forced into a common clock',
                'F1/F2/F3 and A-low review questions stay pending; no duplicate requests'])
        sources={Path(__file__),repo/'AGENTS.md',repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',
            repo/'research/少数声线独立相位V1.md',repo/'research/怠速与加速完成度V1.md'}
        for name in ('validate2','audit1'):
            sources.update(repo/relative for relative in reports[name]['sources'])
        for source in sources:
            relative=source.relative_to(repo)
            target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            report['sources'][relative.as_posix()]=sha(source)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        shutil.copy2(base/'audit1/minority_phase.png',final/'minority_phase.png')
        save(summary,report)
    except Exception as exc:
        report.update(result='failed',error=repr(exc))
        raise
    finally:
        save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],passed=report['passed_cases'],total=12,real_models=0)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary)
    assert report['result'] in ('minority_principle_passed_not_full_qualification','minority_principle_rejected')
    assert sha(summary)==sha(final/'report.json')
    for relative,digest in report['sources'].items():
        assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for item in report['reports'].values():
        assert sha(args.workspace/item['path'])==item['sha256']
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/name)==digest for name,digest in load(final/filename).items())
    out=args.workspace/'baselines/minority_phase_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/aperture_model_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_aperture_manifest=prior.relative_to(args.workspace).as_posix(),prior_aperture_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path'])==item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
