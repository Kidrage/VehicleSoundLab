"""Freeze both declared majorizer paths, including numerical/audit failures."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=('publish','freeze','verify'),required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
analysis=args.workspace/'references/analysis';root=analysis/'majorizer_paths_v1';final=root/'final1'
summary=repo/'research/majorizer_paths_v1_summary.json';frozen=args.workspace/'baselines/majorizer_paths_v1'


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def current(r):
    for name,digest in r['sources'].items():assert sha(repo/name)==sha(final/'exact_sources'/name)==digest
    for item in [*r['reports'].values(),*r['other_evidence'].values()]:assert sha(args.workspace/item['path'])==item['sha256']
    for name in ('C_files_sha256.json','voice_files_sha256.json'):
        assert all(sha(repo/file)==digest for file,digest in load(final/name).items())
    assert len(load(final/'C_files_sha256.json'))==540
    assert sha(args.workspace/'AGENTS.md')==sha(final/'data_workspace_AGENTS.md')==r['data_memory_sha256']
    assert sha(repo/'references/segments_v1.json')==sha(args.workspace/'references/segments_v1.json')==r['catalogue_sha256']
    for item in r['prior_manifests'].values():assert sha(args.workspace/item['path'])==item['sha256']
    subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],cwd=repo,capture_output=True,check=True)


if args.stage=='publish':
    final.mkdir(parents=True,exist_ok=False)
    r=dict(schema='vsl.majorizer-paths-final/1',result='running',sources={},reports={},other_evidence={})
    try:
        paths={'diagnosis':'radial_majorizer_v1/diagnosis1','block_fit':'radial_majorizer_v1/fit1',
            'block_audit':'radial_majorizer_v1/audit1','joint_fit':'joint_radial_majorizer_v1/fit1',
            'joint_failed_audit':'joint_radial_majorizer_v1/audit1','joint_audit':'joint_radial_majorizer_v1/audit2'}
        reports={k:load(analysis/v/'report.json') for k,v in paths.items()}
        d,b,ba,j,ja=(reports[k] for k in ('diagnosis','block_fit','block_audit','joint_fit','joint_audit'))
        assert d['result']=='all20_saved_candidate_deficits_decomposed_no_refit' and d['controls']['passed']
        assert b['result']=='known_majorizer_rejected' and b['steps']==b['QP_certified']==b['accepted_steps']==20
        assert ba['result']=='parent20_deficits_and_actual20_majorized_steps_independently_rebuilt'
        assert j['result']=='known_joint_majorizer_rejected' and j['steps']==19 and j['QP_certified']==16
        assert ja['result']=='all19_joint_majorizer_steps_including3_QP_failures_independently_rebuilt'
        assert ja['QP_failure_steps']==[5,14,15] and ja['recovery_gates']==dict(phase=True,root=True,support=True,floor=True,all_QPs=False)
        assert not ja['original_factor_relative_gates_all_passed'] and ja['supplemental_forward_bounds_passed']
        assert reports['joint_failed_audit']['result']=='failed'
        for label,fit,audit in (('block',b,ba),('joint',j,ja)):
            path=analysis/paths[label+'_fit'];assert fit['fit_report_sha256']==sha(path/'fit.json')
            assert audit['candidate_report_sha256']==sha(path/'report.json')
            assert not audit['nonlinear_estimator_rerun'] and not audit['quadratic_solver_rerun']
        sources={Path(__file__),repo/'AGENTS.md',repo/'research/径向上界与联合恢复V1.md',repo/'handoff/研究续接.md',
            repo/'handoff/算法说明.md',repo/'handoff/开发留痕.md',repo/'research/怠速与加速完成度V1.md'}
        for label,report in reports.items():
            folder=analysis/paths[label];r['reports'][label]=dict(path=(folder/'report.json').relative_to(args.workspace).as_posix(),sha256=sha(folder/'report.json'),result=report['result'])
            for name,digest in report['sources'].items():
                assert sha(folder/'exact_sources'/name)==digest
                if label!='joint_failed_audit':
                    assert sha(repo/name)==digest;sources.add(repo/name)
        diagnostic=analysis/'joint_radial_majorizer_v1/gradient_roundoff_diagnosis1.json'
        r['other_evidence']['roundoff_diagnostic']=dict(path=diagnostic.relative_to(args.workspace).as_posix(),sha256=sha(diagnostic))
        for path in sources:
            rel=path.relative_to(repo);dest=final/'exact_sources'/rel
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['sources'][rel.as_posix()]=sha(path)
        previous=analysis/'phase_envelope_blocks_v1/final1'
        for name in ('C_files_sha256.json','voice_files_sha256.json'):shutil.copy2(previous/name,final/name)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        parent_path='baselines/phase_envelope_blocks_v1/manifest.json'
        parent=dict(phase_envelope_blocks_v1=dict(path=parent_path,sha256=sha(args.workspace/parent_path)))
        bf=load(analysis/paths['block_fit']/'fit.json');jf=load(analysis/paths['joint_fit']/'fit.json')
        r.update(result='known_joint_recovery_passes_but3_QPs_and_original_relative_audit_fail',prior_manifests=parent,
            derivation='Concave squared-magnitude radial softL1 tangent: vI2 upper bound in residual space; objective/gradient unchanged',
            old_parent_saved_candidates=20,old_rejected_angle_amplitude_steps=d['angle_amplitude_rejected'],
            old_linear_radial_cost_increase_steps=d['angle_amplitude_linear_radial_increases'],
            controls=d['controls'],block_assessment=b['assessment'],joint_assessment=j['assessment'],
            recovery_gates=ja['recovery_gates'],block_cost=bf['final_cost'],joint_cost=jf['final_cost'],
            block_normalized_residual=bf['normalized_projection_residual'],joint_normalized_residual=jf['normalized_projection_residual'],
            actual_QPs=39,block_QPs=20,joint_QPs=19,certified_QPs=36,joint_failed_QP_steps=ja['QP_failure_steps'],
            joint_maximum_iterations=20,joint_stop='Original minimum trust radius reached after19 actual steps',
            truth_guided_prefix_selected=False,actual_fits=2,individually_declared_paths=True,
            parent_deficit_maximum_error=ba['parent_deficit_maximum_error'],
            waveform_maximum_error=max(ba['waveform_maximum_error'],ja['waveform_maximum_error']),
            scalar_loss_maximum_error=max(ba['scalar_loss_maximum_error'],ja['scalar_loss_maximum_error']),
            original_factor_relative_failed_steps=ja['original_factor_relative_gate_failed_steps'],
            original_factor_relative_gate_passed=False,supplemental_forward_bounds_passed=True,
            legacy_factor_source_string='Original adapter names exact H; audited actual curvature is vI2',
            C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),catalogue_sha256=sha(repo/'references/segments_v1.json'),
            real_audio_read=False,model_exported=False,runtime_changed=False,new_WAV=False,existing55CTests_rerun=False,
            original_dense_started=False,real_shared_phase_DNA_permitted=False,vehicle_timbre_accepted=False,
            full_qualification=False,idle_acceleration_complete=False,goal_complete=False,moving35='held_unchanged',
            F3_stopped54_56='speech_excluded_from_quantitative_and_DNA',other_reviewed_F_short_clips='usable_mild_wind_noted',original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_one_fixedblock_knownfit_andall20audit',current_goal_turn='progress_derivedmajorizer_20olddeficits_2declaredfits_39QPsaudited_failuresretained',
            next_step='Isolate saved3failed QPs; verify numerical scaling/active-set termination/observed convergence certificates with independent controls and originalprecision/budget. No truthprefix or sweeps. Original36/all17/full33/individual14k/originalE before real DNA.',
            limits=d['limits']+b['limits']+ja['limits'])
        current(r);save(summary,r)
    except Exception as exc:
        r.update(result='failed',error=repr(exc));raise
    finally:save(final/'report.json',r)
    print(json.dumps(dict(result=r['result'],actual_QPs=r['actual_QPs'],certified_QPs=r['certified_QPs'])),flush=True)
elif args.stage=='freeze':
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    r=load(summary);current(r);assert sha(summary)==sha(final/'report.json')
    frozen.mkdir(exist_ok=False)
    for name in ('radial_majorizer_v1','joint_radial_majorizer_v1','majorizer_paths_v1'):
        shutil.copytree(analysis/name,frozen/'evidence'/name)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(frozen/'source.zip'),commit],cwd=repo,check=True)
    files=[dict(path=x.relative_to(frozen).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=files,prior_manifests=r['prior_manifests'],
        known_phase_recovery=True,known_full_qualification=False,original_dense_started=False,profiles_exported=0,vehicle_timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(x['bytes'] for x in files),commit=commit,manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
else:
    r=load(summary);current(r);m=load(frozen/'manifest.json')
    assert sha(summary)==sha(final/'report.json')==sha(frozen/'evidence/majorizer_paths_v1/final1/report.json')
    for item in m['files']:assert sha(frozen/item['path'])==item['sha256'] and (frozen/item['path']).stat().st_size==item['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as archive:
        assert archive.testzip() is None
        for name,digest in r['sources'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==digest
    for item in r['prior_manifests'].values():
        path=args.workspace/item['path'];assert sha(path)==item['sha256']
        for row in load(path)['files']:assert sha(path.parent/row['path'])==row['sha256']
    print(json.dumps(dict(result='all_payloads_exact_sources_parent_C_voices_verified',files=len(m['files']),manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
