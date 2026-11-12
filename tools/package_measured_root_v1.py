"""Publish and freeze known-signal progress while retaining rapid rejection."""
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

base=args.workspace/'references/analysis/measured_root_v1'
diagnostics=args.workspace/'references/analysis/fractional_residue_v1'
final=base/'final1'
summary_path=repo/'research/measured_root_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    result=dict(schema='vsl.measured-root-publication/1',result='running',reports={},sources={})
    try:
        self_copy=final/'exact_sources/tools/package_measured_root_v1.py'
        self_copy.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(Path(__file__),self_copy)
        result['sources']['tools/package_measured_root_v1.py']=sha(Path(__file__))
        entries=dict(diagnose1=diagnostics/'diagnose1',diagnose2=diagnostics/'diagnose2',
            validate1=base/'validate1',high_audit1=base/'high_audit1',rapid_audit1=base/'rapid_audit1')
        for name,directory in entries.items():
            path=directory/'report.json'
            entry=load(path)
            assert entry['result'] in ('diagnostic_complete_no_qualification','rejected','diagnosed_no_algorithm_change')
            result['reports'][name]=dict(path=path.relative_to(args.workspace).as_posix(),sha256=sha(path),result=entry['result'])
            for relative,digest in entry['sources'].items():
                assert sha(directory/'exact_sources'/relative)==digest
                if name!='diagnose1':
                    assert sha(repo/relative)==digest
        plan=load(repo/'research/measured_root_v1_plan.json')
        original_plan=load(repo/'research/fractional_clock_v1_plan.json')
        for key in original_plan:
            if key not in ('schema','scope','policy','fixtures','coarse'):
                assert plan[key]==original_plan[key]
        assert {key:value for key,value in plan['coarse'].items() if key!='precision_weight_median_cap'}==original_plan['coarse']
        original_ids={case['id'] for case in original_plan['fixtures']}
        assert [case for case in plan['fixtures'] if case['id'] in original_ids]==original_plan['fixtures']
        assert len(plan['fixtures'])==33
        validated=load(base/'validate1/report.json')
        high=load(base/'high_audit1/report.json')
        rapid=load(base/'rapid_audit1/report.json')
        assert [row['case'] for row in validated['cases']]==plan['fixtures']
        positives=[row for row in validated['cases'] if not row['case'].get('negative')]
        negatives=[row for row in validated['cases'] if row['case'].get('negative')]
        assert len(positives)==30 and sum(row['passed'] for row in positives)==29
        assert len(negatives)==3 and all(row['passed'] for row in negatives)
        assert [row['case']['id'] for row in validated['cases'] if not row['passed']]==['fifth_rapid_corner']
        assert not validated['real_source_permitted'] and not high['combined_qualification_passed']
        measured_high=[row for row in high['cases'] if row['hf_measured']]
        assert len(measured_high)==29 and all(row['passed'] for row in measured_high)
        high_plan=load(repo/'research/measured_root_high_v1_plan.json')
        assert high_plan['maximum_line_power_error_db']==plan['rules']['maximum_oracle_band_power_error_db']
        assert high_plan['maximum_line_complex_correlation_error']==plan['rules']['maximum_oracle_complex_correlation_error']
        assert rapid['observed_rows']==1001 and len(rapid['unsupported_proposals'])==1
        assert len(rapid['unsupported_proposals'][0]['proposal_supported_orders'])==2
        assert len(rapid['unsupported_proposals'][0]['original_smoothed_supported_orders'])>=3
        diagnosis=load(diagnostics/'diagnose2/report.json')
        assert all(row.get('frozen_final_coordinate_exact') for row in diagnosis['cases'] if row['frozen_status']=='measured')
        prediction_error=max(line['prediction_error_db'] for row in diagnosis['cases'] for line in row.get('known_high_carriers',[]))
        assert prediction_error<.00019
        with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:
            indexed=list(csv.DictReader(stream))
        c_hashes={row['文件']:row['SHA-256'] for row in indexed}
        assert len(c_hashes)==540 and all(sha(repo/name)==digest for name,digest in c_hashes.items())
        prior=args.workspace/'references/analysis/fractional_clock_v1/final2'
        voice_hashes=load(prior/'voice_files_sha256.json')
        assert all(sha(repo/name)==digest for name,digest in voice_hashes.items())
        save(final/'C_files_sha256.json',c_hashes)
        save(final/'voice_files_sha256.json',voice_hashes)
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],cwd=repo,check=True,capture_output=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        assert not list(diagnostics.rglob('*.model')) and not list(diagnostics.rglob('*.wav'))
        import numpy as np
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        old=load(args.workspace/'references/analysis/fractional_clock_v1/validate9/report.json')
        names=['fifth_steady','fifth_masking_7','fifth_masking_15']
        figure,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
        for axis,kind in zip(axes,('grid','individual_hf')):
            before=[]
            after=[]
            for name in names:
                first=next(row for row in old['cases'] if row['case']['id']==name)
                current=next(row for row in validated['cases'] if row['case']['id']==name)
                audited=next(row for row in high['cases'] if row['case']['id']==name)
                before.append(first['coherent_oracle']['maximum_band_power_error_db'] if kind=='grid' else audited['baseline_full_mixture']['maximum_line_power_error_db'])
                after.append(current['coherent_oracle']['maximum_band_power_error_db'] if kind=='grid' else audited['maximum_line_power_error_db'])
            x=np.arange(len(names))
            for values,offset,label,color in ((before,-.18,'Frozen validate9','#4477aa'),(after,.18,'Measured-root candidate','#ee7733')):
                bars=axis.bar(x+offset,values,width=.36,label=label,color=color)
                axis.bar_label(bars,fmt='%.3g',padding=3,fontsize=8)
            axis.axhline(.5,color='#aa3344',ls='--',lw=1,label='0.5 dB gate')
            axis.set(xticks=x,xticklabels=['Steady','Mask near order7','Mask near order15'],ylabel='Maximum absolute power error (dB)',
                title='Full-mixture fifth-grid bands' if kind=='grid' else 'Full-mixture individual HF lines')
            axis.margins(y=.2)
            axis.grid(axis='y',alpha=.2)
        axes[0].legend(fontsize=8)
        figure.suptitle('Known signals only: rapid corner still rejected; no new vehicle timbre',fontsize=11)
        figure.savefig(final/'hf_preservation.png',dpi=160)
        plt.close(figure)
        result.update(result='partial_improvement_not_qualified',total_cases=33,passed_cases=32,
            positive_cases=30,passed_positive_cases=29,negative_cases=3,passed_negative_cases=3,
            individually_audited_HF_positive_cases=29,passed_HF_positive_cases=29,
            maximum_HF_line_error_db=max(row['maximum_line_power_error_db'] for row in measured_high),
            maximum_HF_line_complex_correlation_error=max(row['maximum_line_correlation_error'] for row in measured_high),
            known_phase_prediction_maximum_error_db=prediction_error,
            rapid_failure=rapid['unsupported_proposals'][0],
            source_audio_read=False,real_source_evaluated=False,model_exported=False,real_C_render_executed=False,
            strict_source_evaluation_permitted=False,vehicle_timbre_accepted=False,idle_acceleration_complete=False,
            C_H=540,runtime_changed=False,existing_Ctests_rerun=False,moving35='held_unchanged',new_media_downloaded=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            plot_sha256=sha(final/'hf_preservation.png'),
            next_step='Project continuous median into distinct-measured-line feasible support, qualify all33 plus individual HF, then resolve aperture average versus instantaneous phase/curvature',
            goal_turn_classification='progress_known-component_attribution_and_substantial_measured-root_HF_improvement',
            limits=['No whole-algorithm qualification or real-source evaluation from32/33',
                'Known components are not physical source separation or engine RPM/load measurements',
                'High-frequency numerical preservation is not vehicle listening acceptance',
                'Original F1/F2/F3 and A-low questions remain pending; no duplicate requests'])
        sources={Path(__file__),repo/'AGENTS.md',repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',
            repo/'research/实测根音与高频保留V1.md',repo/'research/怠速与加速完成度V1.md'}
        for name,directory in entries.items():
            if name!='diagnose1':
                sources.update(repo/relative for relative in load(directory/'report.json')['sources'])
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
    print(json.dumps(dict(result=result['result'],passed_cases=32,total_cases=33,real_models=0)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    result=load(summary_path)
    assert result['result']=='partial_improvement_not_qualified' and sha(summary_path)==sha(final/'report.json')
    for name,digest in result['sources'].items():
        assert sha(repo/name)==sha(final/'exact_sources'/name)==digest
    for item in result['reports'].values():
        assert sha(args.workspace/item['path'])==item['sha256']
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/name)==digest for name,digest in load(final/filename).items())
    out=args.workspace/'baselines/measured_root_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence')
    shutil.copytree(diagnostics,out/'diagnostics')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/fractional_clock_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_fractional_manifest=prior.relative_to(args.workspace).as_posix(),prior_fractional_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path'])==item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
