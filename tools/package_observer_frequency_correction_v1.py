"""Freeze saved corrections, convex-gap evidence and boundary diagnosis together."""
import argparse,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];analysis=a.workspace/'references/analysis'
    e=analysis/'observer_frequency_correction_v1';root=a.workspace/'baselines/observer_frequency_correction_v1'
    parent=a.workspace/'baselines/observer_frequency_v1'
    parent_summary=load(repo/'research/observer_frequency_v1_summary.json')
    assert sha(parent/'manifest.json')==parent_summary['manifest_sha256']
    protected={}
    for n,count in (('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)):
        values=load(parent/'evidence'/n);assert len(values)==count and all(sha(repo/k)==v for k,v in values.items())
        save(e/n,values);protected[n]=values
    names=set()
    for flags in (['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']):names.update(subprocess.check_output(['git']+flags,cwd=repo).decode('utf-8').split('\0'))
    names.discard('');assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    entries={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    hearings=load(parent/'validation.json')['protected_hearings_sha256'];assert all(sha(repo/n)==d for n,d in hearings.items())
    for n in ('optimality','boundary'):
        source=analysis/('observer_frequency_optimality_v1' if n=='optimality' else 'observer_boundary_v1')
        if (e/n).exists():
            original={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*') if p.is_file()}
            copied={p.relative_to(e/n).as_posix():sha(p) for p in (e/n).rglob('*') if p.is_file()}
            assert original==copied
        else:shutil.copytree(source,e/n)
    records=(('known1','observer_frequency_correction_known_ready'),('real1','observer_frequency_correction_all6_measured'),
        ('optimality/known1','observer_frequency_optimality_known_ready'),('optimality/real1','observer_frequency_optimality_all6_measured'),
        ('boundary/known1','observer_boundary_known_ready'),('boundary/real1','observer_boundary_real_ready'),('review1','observer_frequency_correction_review_ready'))
    allinputs={}
    for folder,result in records:
        r=load(e/folder/'report.json');assert r['result']==result
        for n,d in r['sources'].items():assert sha(repo/n)==sha(e/folder/'exact_sources'/n)==d
        for n,d in r.get('inputs',{}).items():
            assert sha(n)==d
            if n in allinputs:assert allinputs[n]==d
            allinputs[n]=d
        for case in r.get('cases',[]):
            if 'file' in case:
                path=e/folder/case['label']/case['file'] if folder=='real1' else e/folder/case['file']
                assert sha(path)==case['sha256']
    audits=(('known_audit1','known1','independent_observer_frequency_correction_known_passed','tools/audit_observer_frequency_correction_known_v1.py'),
        ('real_audit1','real1','independent_observer_frequency_correction_real_passed','tools/audit_observer_frequency_correction_real_v1.py'),
        ('optimality/known_audit2','optimality/known1','independent_observer_frequency_optimality_known_passed','tools/audit_observer_frequency_optimality_known_v1.py'),
        ('optimality/real_audit2','optimality/real1','independent_observer_frequency_optimality_real_passed','tools/audit_observer_frequency_optimality_real_v1.py'),
        ('boundary/known_audit1','boundary/known1','independent_observer_boundary_known_passed','tools/audit_observer_boundary_v1.py'),
        ('boundary/real_audit1','boundary/real1','independent_observer_boundary_real_passed','tools/audit_observer_boundary_v1.py'))
    for folder,producer,result,script in audits:
        r=load(e/folder/'report.json');assert r['result']==result and r['producer_sha256']==sha(e/producer/'report.json')
        assert r['auditor_sha256']==sha(e/folder/'executed_audit.py')==sha(repo/script)
        if 'oracles_sha256' in r:
            for j,(n,d) in enumerate(r['oracles_sha256'].items()):assert sha(repo/n)==sha(e/folder/f'executed_oracle_{j}.py')==d
        else:assert r['oracle_sha256']==sha(e/folder/'executed_oracle.py')==sha(repo/'tools/observer_complete_v1/audit_oracle.py')
    # Failed numerical checks remain intact, alongside the passing repairs.
    failures=[]
    for folder in ('optimality/known_audit1','optimality/real_audit1'):
        r=load(e/folder/'report.json');assert r['result']=='failed'
        failures.append(dict(folder=folder,error=r['error'],executed_auditor_sha256=sha(e/folder/'executed_audit.py')))
    pub=load(e/'review1/report.json');metrics=load(e/'review1/metrics_verification.json')
    assert metrics['result']=='independent_observer_frequency_correction_publication_passed'
    assert metrics['all36_rows_verified'] and metrics['all6_solver_records_verified'] and metrics['all12_gap_records_exact'] and metrics['all_aggregates_and_regression_counts_verified']
    assert metrics['auditor_sha256']==sha(e/'review1/executed_metrics_audit.py')==sha(repo/'tools/audit_observer_frequency_correction_review_v1.py')
    for n in ('figure_inputs','solve_inputs','gap_inputs','summary'):assert sha(e/'review1'/(n+'.json'))==pub[n+'_sha256']==metrics[n+'_sha256']
    visual=load(e/'review1/visual_review.json');decision=load(e/'review1/decision.json')
    assert visual['scientific_figures_individually_viewed']==2 and visual['accepted_for_publication']
    for n,d in pub['images'].items():assert sha(e/'review1'/n)==d==visual['images_sha256'][n]
    assert not decision['native_or_runtime_promoted'] and not list(e.rglob('*.wav'))
    inputs={'data_AGENTS':a.workspace/'AGENTS.md'};locations={}
    mappings=((e,'evidence/'),(analysis/'observer_frequency_optimality_v1','evidence/optimality/'),(analysis/'observer_boundary_v1','evidence/boundary/'))
    oldlocal=analysis/'observer_frequency_v1'
    for n,d in allinputs.items():
        path=Path(n);mapped=False
        for prefix,target in mappings:
            if path.is_relative_to(prefix):
                locations[n]=target+path.relative_to(prefix).as_posix();assert sha(e/locations[n].removeprefix('evidence/'))==d;mapped=True;break
        if mapped:continue
        if path.is_relative_to(oldlocal):
            relative='observer_frequency_v1/evidence/'+path.relative_to(oldlocal).as_posix()
            origin=a.workspace/'baselines'/relative;assert sha(origin)==d
        else:
            assert path.is_relative_to(a.workspace/'baselines'),n
            relative=path.relative_to(a.workspace/'baselines').as_posix();origin=path
        inputs['upstream/'+relative]=origin;locations[n]='inputs/upstream/'+relative
    for n in ('manifest.json','validation.json'):inputs['upstream/observer_frequency_v1/'+n]=parent/n
    summary=load(e/'review1/summary.json');bounds=load(e/'boundary/real1/report.json')
    validation=dict(result='observer_frequency_correction_frozen',source_models=6,engines=1,ascents=2,
        correction_known_mono_stereo_cases=3,zero_rhs_exact=True,source_captures=12,band_Gram_matrices=5760,
        primal_dual_known_candidates=9,primal_dual_source_states=12,boundary_known_cases=2,boundary_source_cases=6,
        publication_rows=36,solver_converged=summary['original_solver_converged'],additional_gap_passed=summary['additional_gap_passed'],
        results=summary,boundary_endcap_fractions=[c['endcap_fraction_by_band'] for c in bounds['cases']],
        historical_failed_audits=failures,failed_packaging_attempt='package_attempt1/executed_package.py;per-source folder lookup repaired;copied payloads reused only after byte verification',original_input_archive_locations=locations,decision=decision,
        original_solver_gate_unchanged=True,floating_point_not_interval_certificate=True,numpy_longdouble_bits=64,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,protected_hearings_sha256=hearings,
        runtime_default_driver_owned_take_room_changed=False,new_stochastic_source=False,native48k_or_C_or_timbre_qualified=False,
        scientific_figures_individually_viewed=2,old_68CTest_not_repeated=True,downloaded=False,pushed=False,
        full_goal='active',next='research/observer_supported_metric_v1_plan.json')
    sources=[n.removeprefix('source/') for n in entries if n.startswith('source/') and (repo/n.removeprefix('source/')).is_file()]
    sources += [n for n in names if ('observer_frequency' in n or 'observer_boundary' in n or 'observer_supported' in n) and Path(n).suffix in ('.py','.json','.md')]
    sources += ['research/加权拟合修正与边界频谱V1.md','tools/package_observer_frequency_correction_v1.py']
    shutil.copy2(__file__,e/'executed_package.py')
    result=freeze(root,repo,sources,e,inputs,validation);verify(root)
    save(repo/'research/observer_frequency_correction_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',['observer_frequency_correction_v1','baselines/observer_frequency_correction_v1/manifest.json',
        result['file_count'],result['manifest_sha256'],'6saved-corrections/12captures5760Gram/9dual-known/6boundary/36published',
        '670C-H82voice3F2/index exact;all6stop7+gap notqualified;no source promotion',
        'research/加权拟合修正与边界频谱V1.md | research/observer_frequency_correction_v1_summary.json','baselines/observer_frequency_correction_v1/validation.json'])
    print(dict(result='observer_frequency_correction_frozen',**result),flush=True)


if __name__=='__main__':main()
