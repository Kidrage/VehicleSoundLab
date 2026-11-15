"""Independent immutable source/input/lifetime/full/resource publication audit."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    def read(path):return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    v=read(a.archive/'validation.json');e=a.archive/'evidence'
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    parents={}
    for name,digest in v['upstream_manifests_sha256'].items():
        path=a.archive/f'inputs/upstream/{name}/manifest.json';assert sha(path)==digest
        parents[name]={row['path']:row['sha256'] for row in read(path)['files']}
    sources=inputs=files=0
    for folder in v['selected_terminal_evidence_directories']:
        r=read(e/folder/'report.json')
        for key in ('inputs','input_sha256'):
            for name,digest in r.get(key,{}).items():
                target=v['original_input_archive_locations'][name];assert sha(a.archive/target)==digest
                parts=Path(target).parts
                if parts[:2]==('inputs','upstream'):
                    leaf=Path(*parts[3:]).as_posix()
                    assert (v['upstream_manifests_sha256'][parts[2]] if leaf=='manifest.json' else parents[parts[2]][leaf])==digest
                inputs+=1
        for name,digest in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest;sources+=1
        for key in ('cases','inverse_cases','original_cases','frames','temporal'):
            for case in r.get(key,[]):
                if 'file' in case:assert sha(e/folder/case['file'])==case['sha256'];files+=1
                if 'node_file' in case:assert sha(e/folder/case['node_file'])==case['node_sha256'];files+=1
        if 'capture_sha256' in r:assert sha(e/folder/'capture.npz')==r['capture_sha256'];files+=1
        if 'auditor_sha256' in r:
            filename='executed_inspection.py' if folder=='real_resources1' else 'executed_audit.py'
            assert sha(e/folder/filename)==r['auditor_sha256']
    def report(n):return read(e/n/'report.json')
    controls=report('controls_audit1');roots=report('roots_audit1')
    assert controls['all_qualified'] and len(controls['inverse_cases'])==v['inverse_controls']==8
    assert len(controls['original_cases'])==v['original_arbitrary_controls']==7
    assert roots['all_qualified'] and len(roots['frames'])==v['DFT_controls']==4 and len(roots['temporal'])==v['temporal_controls']==3
    assert report('roots_native_audit1')['result']=='independent_waveform_banded_controls_passed'
    for source,audit,count in (('known1','known_audit1',12),('shared1','shared_audit1',8)):
        p,r=report(source),report(audit)
        assert p['all_qualified'] and r['all_qualified'] and r['pass_count']==count
        assert r['producer_sha256']==sha(e/source/'report.json')
        assert all(c['qualified'] and c['stable_complete_normal']<=1e-11 and c['original_backward']<=1e-11 for c in r['cases'])
    life=report('lifetime_audit1')
    assert life['actual_lifetimes_verified'] and life['all_output_arrays_bitwise_previous'] and len(life['cases'])==20
    assert len(life['ownership_guards'])==v['actual_ownership_guards']==8
    assert all(c['actual_source_release_before_inner_verified'] and c['no_base_or_inverse_T_copy'] for c in life['cases'])
    assert all(x['bitwise_exact'] for c in life['cases'] for x in c['comparison'])
    full,audit=report('full1'),report('full_audit1')
    assert full['owned_pipeline'] and full['only_one_attempt']
    assert audit['solver_qualified'] and audit['fidelity_qualified']
    assert audit['base_graph_copy_avoided'] and audit['source_released_before_inner'] and audit['all_phase_releases_verified']
    assert audit['producer_sha256']==sha(e/'full1/report.json')
    assert audit['gradient']==v['full_gradient']<2e-7
    assert audit['stable_original_complete_normal']==v['full_stable_normal']<=1e-11
    assert audit['original_backward']==v['full_backward']<=1e-11
    assert audit['residual_gap_passed'] and audit['representer_gap_passed']
    assert audit['metrics']==v['full_metrics']
    assert audit['comparison_rows']==v['all17_comparison_rows'] and len(audit['comparison_rows'])==17
    assert audit['original_correction_history']==v['full_all_three_original_histories'] and len(audit['original_correction_history'])==3
    N,M=12289,49;n=576*M;k=min(N,n)
    base=32768*N+8*N*n+8*(k+n)*k
    inverse=[8*N*n+8*n*k,8*n*k+16*k*k]
    assert base==audit['actual_full_main_array_bytes']==v['full_base_main_bytes']==7160357896
    assert base+8*k*k==v['previous_full_base_main_bytes']==8368514064
    required=max([base]+inverse)+1610612736+3221225472
    pre=full['resource_preflight'];assert pre['required_available']==required and pre['passed']
    assert min(pre['available_physical_bytes'],pre['available_commit_bytes'])>=required
    assert full['process_memory']['cumulative_peak_working_set_bytes']==v['full_actual_WS_peak']
    assert full['process_memory']['cumulative_peak_private_commit_bytes']==v['full_actual_private_commit_peak']
    assert full['resources']['max_tracked_live_backing_bytes']==v['full_registered_backing_peak']
    progress=read(e/'full1/progress.json');assert progress['status']=='completed' and progress['report_sha256']==sha(e/'full1/report.json')
    resources=report('real_resources1');ra=report('real_resources_audit1')
    assert resources['cases']==v['actual_real_shape_resource_cases'] and ra['cases']==v['real_resource_audit_cases']
    assert ra['result']=='independent_waveform_early_release_real_resources_verified'
    assert ra['producer_sha256']==sha(e/'real_resources1/report.json') and len(ra['cases'])==12
    assert resources['actual_recorded_context_qualified'] and resources['no_real_fit_or_large_arrays_allocated']
    for c in resources['cases']:
        N,M=c['frames'],c['nodes'];n=576*M;k=min(N,n)
        values=dict(W_band=32768*N,X=8*N*n,graph=8*(k+n)*k,old_graph_T=8*k*k,
                    inverse_right=8*n*k,inverse_inner=16*k*k)
        assert values==c['individual_bytes']
        major=max(values['W_band']+values['X']+values['graph'],values['X']+values['inverse_right'],values['inverse_right']+values['inverse_inner'])
        assert c['main_arrays_only']==major and c['required_available']==major+1610612736+3221225472
        assert c['all_original_nodes_preserved'] and c['shape_arithmetic_only_NOT_real_fit_peak']
    assert sha(e/'executed_package.py')==sha(a.archive/'source/tools/package_waveform_early_release_v1.py')
    assert v['full_goal']=='active' and v['no_large_real_fit_or_C_or_hearing_promotion']
    assert not v['runtime_default_driver_owned_take_room_changed']
    result=dict(result='independent_waveform_early_release_archive_bindings_verified',
        source_bindings=sources,input_bindings=inputs,case_file_bindings=files,
        known20_exact=True,full_original_solver_and_fidelity=True,actual_early_release=True,
        all17_rows_and12_actual_shape_resources_verified=True,auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(result,flush=True)


if __name__=='__main__':main()
