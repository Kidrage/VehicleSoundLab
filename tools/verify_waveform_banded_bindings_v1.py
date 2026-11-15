"""Independent archived exact sources, all retained outcomes and resource arithmetic."""
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
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    e=a.archive/'evidence';v=read(a.archive/'validation.json');source_count=input_count=file_count=0
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    parents={}
    for n,h in v['upstream_manifests_sha256'].items():
        file=a.archive/f'inputs/upstream/{n}/manifest.json';assert sha(file)==h
        parents[n]={r['path']:r['sha256'] for r in read(file)['files']}
    for folder in v['selected_terminal_evidence_directories']:
        r=read(e/folder/'report.json')
        for n,h in r.get('inputs',r.get('input_sha256',{})).items():
            target=v['original_input_archive_locations'][n];assert sha(a.archive/target)==h
            parts=Path(target).parts
            if parts[:2]==('inputs','upstream'):
                leaf=Path(*parts[3:]).as_posix()
                assert (v['upstream_manifests_sha256'][parts[2]] if leaf=='manifest.json' else parents[parts[2]][leaf])==h
            input_count+=1
        for n,h in r.get('sources',{}).items():assert sha(e/folder/'exact_sources'/n)==h;source_count+=1
        for key in ('cases','frames','temporal'):
            for c in r.get(key,[]):
                if 'file' in c and 'sha256' in c:assert sha(e/folder/c['file'])==c['sha256'];file_count+=1
    def report(name):return read(e/name/'report.json')
    controls=report('controls_audit1');band=report('band_controls_audit1');known=report('known1');ka=report('known_audit2')
    assert controls['all_qualified'] and (len(controls['cases']),len(controls['frames']),len(controls['temporal']))==(7,4,3)
    assert band['all_qualified'] and len(band['cases'])==v['band_map_controls']==4
    assert max(band['maximum_errors'].values())==v['band_map_maximum_error']<2e-12
    assert ka['producer_sha256']==sha(e/'known1/report.json') and ka['pass_count']==v['original12_qualified']==12
    assert ka['all_qualified'] and all(c['qualified'] for c in known['cases'])
    strict=[c['label'] for c in ka['cases'] if not c['old_root_Gram_2e_11_passed']]
    assert strict==v['old_root_Gram_2e_11_failures'] and len(strict)==8
    failed=report('known_audit1');assert failed['result']=='failed' and 'unchanged_whitened_graph_Gram' in failed['error']
    assert sha(e/'known_audit2/executed_audit.py')==ka['auditor_sha256']
    assert sha(e/'known_audit1/executed_audit.py')!=sha(e/'known_audit2/executed_audit.py')
    roots=report('root_diagnosis1');assert len(roots['cases'])==8 and all(c['original_lower_metric_bitwise_equal'] for c in roots['cases'])
    sa=report('shared_audit1');assert sa['producer_sha256']==sha(e/'shared1/report.json')
    assert sa['pass_count']==v['shared8_qualified']==7 and not sa['all_qualified']
    failures=[c for c in sa['cases'] if not c['qualified']];assert failures==v['shared_original_failures']
    assert len(failures)==1 and failures[0]['label']=='delayed_right' and failures[0]['stable_complete_normal']>1e-11
    assert all(r['rejected'] for r in sa['rejections_preserved']) and len(sa['rejections_preserved'])==7
    probe=report('equilibration_probe1');pa=report('diagnosis_audit1')
    assert probe['pass_count']==pa['equilibration_pass_count']==v['equiv_diagonal_probe_qualified']==4
    assert len(probe['cases'])==5 and not probe['production_backend_selected']
    assert pa['producer_sha256']==sha(e/'equilibration_probe1/report.json')
    assert [c['label'] for c in pa['cases'] if not c['qualified']]==['delayed_right']
    context=report('native_context1');ca=report('native_context_audit1')
    assert len(context['cases'])==ca['pass_count']==v['real6_provenance_verified']==6
    assert ca['producer_sha256']==sha(e/'native_context1/report.json')
    assert context['all_master_crops_bitwise_exact'] and context['all_coarse_context_and_native_FIR_guards_available']
    assert not any(c['outer_corrected_phase_independently_qualified'] for c in context['cases'])
    resources=report('resources_audit1');assert resources['conditional_cases']==v['current_conditional_resource_cases']
    for c in resources['conditional_cases']:
        N,M=c['frames'],c['nodes'];n=2*M*288;k=min(N,n)
        sizes=dict(W_band=8*4096*N,X_raw=8*N*n,graph_raw=8*(k+n)*k,graph_R=8*k*k)
        assert sizes==c['individual_bytes'] and sum(sizes.values())==c['coexisting_four_array_bytes']
        required=sum(sizes.values())+3*1024**3//2+3*1024**3;assert required==c['required_available']
        free=resources['available_memory'];assert (min(free['available_physical_bytes'],free['available_commit_bytes'])>=required)==c['current_headroom_passed']
        assert c['conditional_only_NOT_allocated']
    previous=read(a.archive/'inputs/upstream/waveform_stream_v1/evidence/known1/report.json')
    oldpeak=max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in previous['cases'])
    newpeak=max(c['process_memory']['cumulative_peak_working_set_bytes'] for c in known['cases'])
    assert oldpeak==v['original_known_peak_before']==962990080 and newpeak==v['original_known_peak_after']==413249536
    assert 1-newpeak/oldpeak==v['working_set_reduction_fraction']
    assert sha(e/'executed_package.py')==sha(a.archive/'source/tools/package_waveform_banded_v1.py')
    assert not v['full_or_real_or_native48k_or_C_or_hearing_qualified'] and not v['outer_corrected_phase_qualified']
    result=dict(result='independent_waveform_banded_archive_bindings_verified',source_bindings=source_count,
        original_input_bindings=input_count,case_file_bindings=file_count,original12_pass=12,shared8_pass=7,
        strict_failure_retained=True,equilibration5_pass=4,real6_provenance=6,source_or_runtime_NOT_promoted=True,
        auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(result,flush=True)


if __name__=='__main__':main()
