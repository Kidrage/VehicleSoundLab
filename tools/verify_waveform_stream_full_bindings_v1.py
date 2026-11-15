"""Independent full-stage source/input, complete result, inventory and publication bindings."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    def read(path):return json.loads(path.read_text('utf-8'))
    def sha(path):
        with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    e=a.archive/'evidence';v=read(a.archive/'validation.json');sources=inputs=0
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    manifests={}
    for name,h in v['upstream_manifests_sha256'].items():
        path=a.archive/'inputs/upstream'/name/'manifest.json';assert sha(path)==h
        manifests[name]={r['path']:r['sha256'] for r in read(path)['files']}
    for folder in v['selected_terminal_evidence_directories']:
        report=read(e/folder/'report.json')
        for name,h in report.get('inputs',{}).items():
            target=v['original_input_archive_locations'][name];assert sha(a.archive/target)==h
            parts=Path(target).parts
            if parts[:2]==('inputs','upstream'):
                rel=Path(*parts[3:]).as_posix()
                if rel=='manifest.json':assert v['upstream_manifests_sha256'][parts[2]]==h
                else:assert manifests[parts[2]][rel]==h
            inputs+=1
        for name,h in report.get('sources',{}).items():assert sha(e/folder/'exact_sources'/name)==h;sources+=1
    full=read(e/'full1/report.json');audit=read(e/'full_audit1/report.json');trace=read(e/'trace_controls1/report.json')
    assert sha(e/'full1/capture.npz')==full['capture_sha256'] and full['only_one_attempt']
    assert audit['producer_sha256']==sha(e/'full1/report.json')
    assert sha(e/'full_audit1/executed_audit.py')==audit['auditor_sha256']
    for j,(name,h) in enumerate(audit['oracles_sha256'].items()):assert sha(e/f'full_audit1/executed_oracle_{j}.py')==h
    assert full['solver_qualified']==audit['solver_qualified']==audit['fidelity_qualified']==v['full_known_solver_qualified']==True
    assert audit['gradient']<2e-7 and audit['stable_original_complete_normal']<=1e-11 and audit['original_backward']<=1e-11
    for tag in ('residual','representer'):
        c=audit[tag+'_certificate'];assert c['gap_upper_bound']<=1e-6*c['primal']+1e-10
    assert audit['extra_trace2e_11_passed'] and trace['all_qualified'] and len(trace['cases'])==13
    assert trace['maximum_relative_error']==max(c['relative_error'] for c in trace['cases'])<2e-12
    assert sha(e/'trace_controls1/executed_audit.py')==trace['auditor_sha256']
    inventory=read(e/'real_inventory1/report.json');assert len(inventory['cases'])==6 and inventory['same6_original_arrays_and_scales']
    for case in inventory['cases']:
        for key in ('original_target_only','proposed_2048_each_side'):
            shape=case[key];N,M=shape['frames'],shape['nodes'];n=2*M*288;k=min(N,n)
            sizes=dict(W=8*N*N,X_raw=8*N*n,graph_raw=8*(k+n)*k,graph_R=8*k*k)
            assert sizes==shape['individual_array_bytes'] and sum(sizes.values())==shape['coexisting_four_array_bytes']
            required=sum(sizes.values())+3*1024**3//2+3*1024**3
            assert required==shape['preflight_required_available']
            free=inventory['available_memory'];passed=min(free['available_physical_bytes'],free['available_commit_bytes'])>=required
            assert passed==shape['current_headroom_passed']
    assert not inventory['real6_fit_or_new_context_or_independent_phase_qualified']
    pub=read(e/'publication1/report.json');assert sha(e/'publication1/executed_publication.py')==pub['publisher_sha256']
    old=a.archive/'inputs/upstream/observer_stable_full_v1/evidence/full1/report.json';previous=read(old)
    rows=[]
    for name,value in audit['metrics'].items():
        before=previous['metrics'][name]
        for index,(old,new) in enumerate(zip(before,value)) if isinstance(value,list) else [(None,(before,value))]:
            rows.append(dict(metric=name,index=index,previous=old,current=new,regressed=new>old,difference=new-old))
    assert rows==pub['rows']==v['all17_comparison_rows'] and len(rows)==17
    assert [r for r in rows if r['regressed']]==pub['regressions']==v['all_regressions'] and len(v['all_regressions'])==3
    for name in ('objective','residual_gap','representer_gap'):
        key={'objective':'primal','residual_gap':'gap_upper_bound','representer_gap':'gap_upper_bound'}[name]
        tag='representer' if name=='representer_gap' else 'residual'
        assert pub[name+'_before']==previous[tag+'_certificate'][key] and pub[name+'_after']==audit[tag+'_certificate'][key]
    assert sha(e/'executed_package.py')==sha(a.archive/'source/tools/package_waveform_stream_full_v1.py')
    failed=read(e/'package_attempt1/report.json');assert failed['result']=='failed' and 'manifest.json' in failed['error']
    assert sha(e/'package_attempt1/executed_package.py')==failed['executed_package_sha256']
    result=dict(result='independent_waveform_stream_full_archive_bindings_verified',source_bindings=sources,
        original_input_bindings=inputs,full_known_original_gates_passed=True,trace_controls=13,publication_rows=17,
        regressions_retained=3,real6_inventory=6,real6_fit_or_context_NOT_qualified=True,
        no_C_audio_promotion=True,auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(result,flush=True)


if __name__=='__main__':main()
