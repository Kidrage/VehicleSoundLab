"""Freeze partial qualification without promoting failed source extraction."""
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
parser.add_argument('--publication',default='final2')
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha

base=args.workspace/'references/analysis/fractional_clock_v1'
final=base/args.publication
summary_path=repo/'research/fractional_clock_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    result=dict(schema='vsl.fractional-clock-publication/1',result='running',reports={},sources={})
    try:
        self_snapshot=final/'exact_sources/tools/package_fractional_clock_v1.py'
        self_snapshot.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(Path(__file__),self_snapshot)
        result['sources']['tools/package_fractional_clock_v1.py']=sha(Path(__file__))
        for number in (1,2,3,4,6,7,8,9):
            name=f'validate{number}'
            path=base/name/'report.json'
            item=load(path)
            result['reports'][name]=dict(path=path.relative_to(args.workspace).as_posix(),sha256=sha(path),result=item['result'])
            for relative,digest in item['sources'].items():
                assert sha(path.parent/'exact_sources'/relative)==digest
                if number==9:
                    assert sha(repo/relative)==digest
        for name in ('validate5','validate5_repro1'):
            path=base/name
            assert not (path/'report.json').exists() and (path/'exact_sources/tools/fractional_clock_v1/phase.py').exists()
            files={file.relative_to(path/'exact_sources').as_posix():sha(file) for file in (path/'exact_sources').rglob('*')
                if file.is_file() and file.suffix in ('.py','.json')}
            result['reports'][name]=dict(result='failed_JSON_inf_serialization',exact_sources=files,
                failure_log='references/analysis/fractional_clock_v1/validate5/serialization_failure.txt',
                failure_log_sha256=sha(base/'validate5/serialization_failure.txt'))
        assert result['reports']['validate5']['exact_sources']==result['reports']['validate5_repro1']['exact_sources']
        result['prior_publication']=dict(path='references/analysis/fractional_clock_v1/final1/report.json',
            sha256=sha(base/'final1/report.json'),result='failed_cache_files_in_source_comparison',
            executed_publisher_sha256=sha(base/'final1/exact_sources/tools/package_fractional_clock_v1.py'),
            correction='Compare authored.py/.json sources; original frozen execution also generated.pyc caches')
        guard=load(base/'guard1/report.json')
        assert guard['result']=='failed' and 'qualification incomplete' in guard['error'] and not guard['source_audio_read']
        assert not guard['model_exported']
        result['reports']['guard1']=dict(path='references/analysis/fractional_clock_v1/guard1/report.json',sha256=sha(base/'guard1/report.json'),result='rejected_before_source_read')
        for name,digest in guard['sources'].items():
            assert sha(base/'guard1/exact_sources'/name)==sha(repo/name)==digest
        latest=load(base/'validate9/report.json')
        assert latest['result']=='rejected' and not latest['real_source_permitted'] and len(latest['cases'])==29
        positives=[row for row in latest['cases'] if not row['case'].get('negative')]
        negatives=[row for row in latest['cases'] if row['case'].get('negative')]
        failed=[row for row in latest['cases'] if not row['passed']]
        assert len(positives)==26 and sum(row['passed'] for row in positives)==23
        assert len(negatives)==3 and all(row['passed'] for row in negatives)
        assert [row['case']['id'] for row in failed]==['fifth_masking_7','fifth_masking_15','fifth_rapid_corner']
        assert not list(base.glob('E_source*')) and not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows=list(csv.DictReader(stream))
        assert len(rows)==540 and all(sha(repo/row['文件'])==row['SHA-256'] for row in rows)
        c_hashes={row['文件']:row['SHA-256'] for row in rows}
        voice_hashes=load(args.workspace/'references/analysis/period_structure_v1/final1/voice_files_sha256.json')
        assert all(sha(repo/name)==digest for name,digest in voice_hashes.items())
        save(final/'C_files_sha256.json',c_hashes)
        save(final/'voice_files_sha256.json',voice_hashes)
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],cwd=repo,check=True,capture_output=True)

        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        names=['fifth_steady','fifth_sideband','fifth_masking_7','fifth_masking_15','fifth_phase_5','fifth_rapid_corner']
        figure,axis=plt.subplots(figsize=(12,5),constrained_layout=True)
        for stage in (2,7,8,9):
            cases={row['case']['id']:row for row in load(base/f'validate{stage}/report.json')['cases']}
            values=[cases.get(name,{}).get('coherent_oracle',{}).get('maximum_band_power_error_db',np.nan) for name in names]
            axis.plot(np.arange(len(names)),values,marker='o',label=f'validate{stage}')
        axis.axhline(.5,color='red',linestyle='--',label='0.5dB gate')
        axis.set(xticks=np.arange(len(names)),xticklabels=[name.removeprefix('fifth_') for name in names],
            ylabel='Worst coherent-grid band error (dB)',xlabel='Missing points are absent/rejected cases, never zero error')
        axis.grid(alpha=.2)
        axis.legend(ncol=5,fontsize=8)
        figure.suptitle('Analytic controls only: band energy does not establish coherent-detail preservation\nFinal:23/26 positives+3/3 negatives; mask7/mask15/rapid remain failed, no source fit')
        figure.savefig(final/'coherent_detail_checks.png',dpi=140)
        plt.close(figure)
        passed=[row for row in positives if row['passed']]
        result.update(result='partial_qualification_rejected_no_source_fit',date='2026-11-13',
            total_cases=29,positive_cases=26,positive_passed=23,negative_cases=3,negative_passed=3,
            failed=[dict(id=row['case']['id'],status=row['status'],reason=row.get('reason'),root_relative_p95=row.get('root_relative_p95'),
                coherent_power_error_db=row.get('coherent_oracle',{}).get('maximum_band_power_error_db'),
                coherent_complex_correlation_error=row.get('coherent_oracle',{}).get('maximum_complex_correlation_error')) for row in failed],
            passing_positive_max_root_relative_p95=max(row['root_relative_p95'] for row in passed),
            passing_positive_max_coherent_power_error_db=max(row['coherent_oracle']['maximum_band_power_error_db'] for row in passed),
            strict_source_evaluation_permitted=False,source_audio_read=False,real_source_evaluated=False,
            model_exported=False,real_C_render_executed=False,vehicle_timbre_accepted=False,
            C_H=540,runtime_changed=False,existing_Ctests_rerun=False,idle_acceleration_complete=False,
            moving35='held_unchanged',new_media_downloaded=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            plot_sha256=sha(final/'coherent_detail_checks.png'),
            next_step='Audit mask-induced coarse-clock residue and known coherent/independent component meter effects; handle rapid high-order phase branches and curvature without relaxing gates',
            goal_turn_classification='progress_new_qualification_cases_metrics_and_reproducible_failures',
            limits=['validate1 only covers integrated Welch; cannot authorize real-source fitting',
                'All29 complete strengthened controls must pass, not a steady or majority subset',
                'Known fixture spectrum is not physical engine separation, RPM or warm-idle proof',
                'guard1 tests rejection only; real-source positive branch unexecuted',
                'No new timbre, C implementation or runtime acceptance; original pending F/A questions unchanged'])
        sources=[Path(__file__),repo/'tools/validate_fractional_clock_v1.py',repo/'tools/evaluate_fractional_source_v1.py',
            repo/'research/fractional_clock_v1_plan.json',repo/'research/分数谱线与相位提取V1.md',
            repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',repo/'research/怠速与加速完成度V1.md',repo/'AGENTS.md']
        sources+=list((repo/'tools/fractional_clock_v1').glob('*.py'))
        for source in sources:
            relative=source.relative_to(repo)
            target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            result['sources'][relative.as_posix()]=sha(source)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        save(summary_path,result)
    except Exception as exc:
        result.update(result='failed',error=repr(exc))
        raise
    finally:
        save(final/'report.json',result)
    print(json.dumps(dict(result=result['result'],passed_positive=23,positive=26,passed_negative=3,real_models=0)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    result=load(summary_path)
    assert result['result']=='partial_qualification_rejected_no_source_fit' and sha(summary_path)==sha(final/'report.json')
    for name,digest in result['sources'].items():
        assert sha(repo/name)==sha(final/'exact_sources'/name)==digest
    for item in result['reports'].values():
        if 'path' in item:
            assert sha(args.workspace/item['path'])==item['sha256']
    for filename in ('C_files_sha256.json','voice_files_sha256.json'):
        for name,digest in load(final/filename).items():
            assert sha(repo/name)==digest
    out=args.workspace/'baselines/fractional_clock_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/period_structure_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_structure_manifest=prior.relative_to(args.workspace).as_posix(),prior_structure_manifest_sha256=sha(prior)))
    for item in items:
        assert sha(out/item['path'])==item['sha256']
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
