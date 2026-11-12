"""Publish and freeze the actual amplitude/phase solver and failed directions."""
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
base=args.workspace/'references/analysis/absolute_amplitude_v1'
final=base/'final1'
summary=repo/'research/absolute_amplitude_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if args.stage=='publish':
    final.mkdir(exist_ok=False)
    report=dict(schema='vsl.absolute-amplitude-publication/1',result='running',sources={},reports={})
    try:
        reports={}
        changed={}
        for name in ('dense1','controls1','direction1','direction2','audit1'):
            folder=base/name
            value=load(folder/'report.json')
            assert not value['real_audio_read'] and not value['real_source_permitted']
            reports[name]=value
            changed[name]=[]
            for relative,digest in value['sources'].items():
                assert sha(folder/'exact_sources'/relative)==digest
                if sha(repo/relative)!=digest:
                    changed[name].append(relative)
            report['reports'][name]=dict(path=(folder/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(folder/'report.json'),result=value['result'],changed_executed_sources=changed[name])
        assert changed['direction1']==['tools/absolute_amplitude_v1/direction.py']
        assert all(not value for name,value in changed.items() if name!='direction1')
        assert reports['direction1']['result']=='failed'
        assert 'Joint differential check failed' in reports['direction1']['error']
        assert reports['dense1']['result']=='dense_diagnostic_rejected' and not reports['dense1']['assessment']['qualified']
        assert reports['controls1']['result']=='passed'
        assert reports['audit1']['result']=='reconstructed_actual_output_no_qualification'
        assert reports['audit1']['phase_residual_cost_assessment_exact']
        assert not reports['direction2']['direction']['accepted']
        for filename in ('C_files_sha256.json','voice_files_sha256.json'):
            previous=args.workspace/'references/analysis/guard_observation_v1/final1'/filename
            value=load(previous)
            assert all(sha(repo/relative)==digest for relative,digest in value.items())
            shutil.copy2(previous,final/filename)
        assert len(load(final/'C_files_sha256.json'))==540
        subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],
            cwd=repo,capture_output=True,check=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        source={Path(__file__),repo/'AGENTS.md',repo/'handoff/算法说明.md',repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md',repo/'research/怠速与加速完成度V1.md',repo/'research/绝对幅度分块求解V1.md'}
        for value in reports.values():
            source.update(repo/relative for relative in value['sources'])
        for path in source:
            relative=path.relative_to(repo)
            target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
            report['sources'][relative.as_posix()]=sha(path)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        assert sha(base/'dense1/absolute_amplitude.png')==reports['dense1']['plot_sha256']
        shutil.copy2(base/'dense1/absolute_amplitude.png',final/'absolute_amplitude.png')
        fit=reports['dense1']['fit']
        report.update(result='absolute_amplitude_improved_phase_still_rejected',
            assessment=reports['dense1']['assessment'],initial_cost=fit['initial_cost'],final_cost=fit['final_cost'],
            normalized_projection_residual=fit['normalized_projection_residual'],outer_cycles=fit['outer_cycles'],
            final_inner_success=fit['final_amplitude']['success'],joint_convergence_demonstrated=False,
            independent_audit={key:value for key,value in reports['audit1'].items() if key not in ('sources','assessment')},
            direction=reports['direction2']['direction'],original17_rerun=False,full33_replaced=False,
            individual14kHz_demonstrated=False,real_source_permitted=False,source_audio_read=False,
            model_exported=False,runtime_changed=False,C_H=540,existing_Ctests_rerun=False,moving35='held_unchanged',
            new_media_downloaded=False,idle_acceleration_complete=False,vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            goal_turn_classification='progress_observed_convex_amplitude_solver_and_actual_constraint_diagnosis',
            next_step='Bounded joint trust-region solve inside the original amplitude cone and phase limits; not unbounded tangent or blind BCD iteration increases; retain full17/full33/individual14kHz/original E',
            limits=['Lower waveform projection residual does not establish latent phase accuracy or vehicle realism',
                'Intermediate QP caps and ordinary joint finite-difference failure retained with exact sources',
                'A local constrained tangent is not a complete variable-projection/trust-region solver',
                'F1/F2/F3 and original A-low questions remain pending; no duplicate requests'])
        save(summary,report)
    except Exception as exc:
        report.update(result='failed',error=repr(exc))
        raise
    finally:
        save(final/'report.json',report)
    print(json.dumps(dict(result=report['result'],phase_p95=report['assessment']['point_phase_p95_cycles'],real_models=0)),flush=True)
else:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    report=load(summary)
    assert report['result']=='absolute_amplitude_improved_phase_still_rejected'
    assert sha(summary)==sha(final/'report.json')
    for relative,digest in report['sources'].items():
        assert sha(repo/relative)==sha(final/'exact_sources'/relative)==digest
    for value in report['reports'].values():
        assert sha(args.workspace/value['path'])==value['sha256']
    out=args.workspace/'baselines/absolute_amplitude_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base,out/'evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items=[dict(path=path.relative_to(out).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior=args.workspace/'baselines/guard_observation_v1/manifest.json'
    save(out/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=items,goal_complete=False,
        profiles_exported=0,source_evaluated=False,vehicle_timbre_accepted=False,
        prior_guard_manifest=prior.relative_to(args.workspace).as_posix(),prior_guard_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path'])==item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen',commit=commit,files=len(items),bytes=sum(item['bytes'] for item in items))),flush=True)
