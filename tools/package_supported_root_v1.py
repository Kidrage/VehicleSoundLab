"""Freeze support-geometry progress and the unqualified aperture-phase evidence."""
import argparse
import csv
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

base=args.workspace/'references/analysis/supported_root_v1'
final=base/'final1'
summary_path=repo/'research/supported_root_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    result=dict(schema='vsl.supported-root-publication/1',result='running',reports={},sources={})
    try:
        self_copy=final/'exact_sources/tools/package_supported_root_v1.py'
        self_copy.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(Path(__file__),self_copy)
        result['sources']['tools/package_supported_root_v1.py']=sha(Path(__file__))
        names=('controls1','controls2','rapid1','rapid2','rapid3','phase_trace1','phase_trace2','validate1','high_audit1')
        latest={'controls2','phase_trace2','validate1','high_audit1'}
        all_reports={}
        for name in names:
            path=base/name/'report.json'
            report=load(path)
            assert report['result'] in ('passed','rejected','traced_rejection_no_algorithm_change')
            for relative,digest in report['sources'].items():
                assert sha(path.parent/'exact_sources'/relative)==digest
                if name in latest:
                    assert sha(repo/relative)==digest
            result['reports'][name]=dict(path=path.relative_to(args.workspace).as_posix(),sha256=sha(path),result=report['result'])
            all_reports[name]=report
        assert len(all_reports['controls1']['cases'])==21 and len(all_reports['controls2']['cases'])==23
        assert all_reports['controls2']['result']=='passed'
        rapid_failure=load(base/'rapid1/fifth_rapid_corner/coarse.json')
        assert rapid_failure['status']=='no_measured_projection_region' and '35..1200' in rapid_failure['reason']
        hierarchy=all_reports['phase_trace2']
        assert len(hierarchy['stages'])==1 and hierarchy['stages'][0]['status']=='rejected'
        assert hierarchy['stages'][0]['orders']==[2,3,5]
        assert hierarchy['original_rapid3_report_sha256']==sha(base/'rapid3/report.json')
        assert hierarchy['replayed_plan_sha256']==sha(base/'phase_trace2/replayed_plan.json')
        assert sha(base/'phase_trace2/aperture_point_mismatch.png')==hierarchy['plot_sha256']
        plan=load(repo/'research/supported_root_v1_plan.json')
        old_plan=load(repo/'research/measured_root_v1_plan.json')
        for key in old_plan:
            if key not in ('schema','scope','policy'):
                assert plan[key]==old_plan[key]
        validation=all_reports['validate1']
        assert not validation['subset'] and validation['result']=='rejected' and not validation['real_source_permitted']
        assert [row['case'] for row in validation['cases']]==plan['fixtures']
        positives=[row for row in validation['cases'] if not row['case'].get('negative')]
        negatives=[row for row in validation['cases'] if row['case'].get('negative')]
        failed=[row for row in validation['cases'] if not row['passed']]
        assert len(positives)==30 and sum(row['passed'] for row in positives)==29
        assert len(negatives)==3 and all(row['passed'] for row in negatives)
        assert len(failed)==1 and failed[0]['case']['id']=='fifth_rapid_corner' and failed[0]['status']=='phase_rejected'
        path=load(base/'validate1/fifth_rapid_corner/coarse.json')
        assert path['status']=='measured_consensus' and len(path['rows'])==1001
        median_projected=[row for row in path['rows'] if row['measured_refinement']['median_projection']['projected']]
        smooth_projected=[row for row in path['rows'] if row['measured_refinement']['smoothed_projection']['projected']]
        assert len(median_projected)==1 and len(smooth_projected)==14
        minimum=min(len(row['measured_refinement']['smoothed_projection']['supported_orders']) for row in path['rows'])
        assert minimum>=3
        audit=all_reports['high_audit1']
        assert audit['reused_HF_cases']==29 and audit['fresh_HF_cases']==0 and audit['measured_HF_all_passed']
        assert not audit['combined_qualification_passed'] and audit['validation_report_sha256']==sha(base/'validate1/report.json')
        prior=args.workspace/'references/analysis/measured_root_v1/final1'
        voice_hashes=load(prior/'voice_files_sha256.json')
        with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:
            indexed=list(csv.DictReader(stream))
        c_hashes={row['文件']:row['SHA-256'] for row in indexed}
        assert len(c_hashes)==540 and all(sha(repo/name)==digest for name,digest in c_hashes.items())
        assert all(sha(repo/name)==digest for name,digest in voice_hashes.items())
        save(final/'C_files_sha256.json',c_hashes)
        save(final/'voice_files_sha256.json',voice_hashes)
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],cwd=repo,check=True,capture_output=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        shutil.copy2(base/'phase_trace2/aperture_point_mismatch.png',final/'aperture_point_mismatch.png')
        result.update(result='coarse_support_repaired_phase_unqualified',support_control_cases=23,
            total_cases=33,passed_cases=32,positive_cases=30,passed_positive_cases=29,negative_cases=3,passed_negative_cases=3,
            rapid_rows=1001,rapid_median_projections=1,rapid_smoothed_projections=14,rapid_minimum_distinct_support=minimum,
            rapid_median_projection=median_projected[0],
            reused_exact_HF_positive_cases=29,fresh_HF_measurements=0,phase_hierarchy_adopted=False,
            phase_point_diagnosis=hierarchy['stages'][0],plot_sha256=sha(final/'aperture_point_mismatch.png'),
            source_audio_read=False,real_source_evaluated=False,model_exported=False,real_C_render_executed=False,
            strict_source_evaluation_permitted=False,vehicle_timbre_accepted=False,idle_acceleration_complete=False,
            C_H=540,runtime_changed=False,existing_Ctests_rerun=False,moving35='held_unchanged',new_media_downloaded=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            next_step='Independently test phase-curvature versus amplitude identifiability and a finite-aperture forward-response model including neighbouring lines; preserve all33 plus individual HF gates',
            goal_turn_classification='progress_exact_supported_coordinate_and_rejected_low_order_phase_hypothesis',
            limits=['Coarse support success is not common-phase qualification or a new real idle timbre',
                'HF reuse requires exact actual coordinate and waveform-source equality; no new listening acceptance',
                'Both original phase and low-order hierarchy reject rapid corner; do not remove or relabel that positive case',
                'Original pending F1/F2/F3 and A-low questions stay pending; no duplicate requests'])
        sources={Path(__file__),repo/'AGENTS.md',repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',
            repo/'research/共同支持与瞬时相位V1.md',repo/'research/怠速与加速完成度V1.md'}
        for name in latest:
            sources.update(repo/relative for relative in all_reports[name]['sources'])
        for source in sources:
            target=final/'exact_sources'/source.relative_to(repo)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            result['sources'][source.relative_to(repo).as_posix()]=sha(source)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        save(summary_path,result)
    except Exception as exc:
        result.update(result='failed',error=repr(exc))
        raise
    finally:
        save(final/'report.json',result)
    print(json.dumps(dict(result=result['result'],support_controls=23,passed_cases=32,total_cases=33,real_models=0)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    result=load(summary_path)
    assert result['result']=='coarse_support_repaired_phase_unqualified' and sha(summary_path)==sha(final/'report.json')
    for name,digest in result['sources'].items():
        assert sha(repo/name)==sha(final/'exact_sources'/name)==digest
    for item in result['reports'].values():
        assert sha(args.workspace/item['path'])==item['sha256']
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/name)==digest for name,digest in load(final/filename).items())
    out=args.workspace/'baselines/supported_root_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/measured_root_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_measured_manifest=prior.relative_to(args.workspace).as_posix(),prior_measured_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path'])==item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
