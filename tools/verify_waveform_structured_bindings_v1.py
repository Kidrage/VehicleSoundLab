"""Independent archive input/executed-version/failed-audit/resource bindings."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    def read(p):return json.loads(p.read_text('utf-8'))
    def sha(p):
        with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    e=a.archive/'evidence';v=read(a.archive/'validation.json')
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    manifests={}
    for n,h in v['upstream_manifests_sha256'].items():
        p=a.archive/'inputs/upstream'/n/'manifest.json';assert sha(p)==h
        manifests[n]={r['path']:r['sha256'] for r in read(p)['files']}
    inputs=sources=arrays=0;metric_versions=set()
    for folder in v['selected_terminal_evidence_directories']:
        r=read(e/folder/'report.json')
        for n,h in r.get('inputs',{}).items():
            target=v['original_input_archive_locations'][n];assert sha(a.archive/target)==h
            parts=Path(target).parts
            if parts[0]=='inputs':assert manifests[parts[2]][Path(*parts[3:]).as_posix()]==h
            else:assert parts[0]=='evidence' and parts[1] in v['selected_terminal_evidence_directories']
            inputs+=1
        for n,h in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/n)==h;sources+=1
            if n=='tools/waveform_representer_v1/metric.py':metric_versions.add(h)
        for group in ('cases','frames','temporal'):
            for c in r.get(group,[]):
                if 'file' in c:assert sha(e/folder/c['file'])==c['sha256'];arrays+=1
        if folder in ('controls_audit1','known_audit2'):
            producer='controls1' if folder=='controls_audit1' else 'known1'
            assert r['producer_sha256']==sha(e/producer/'report.json')
            assert r['auditor_sha256']==sha(e/folder/'executed_audit.py')
    assert len(metric_versions)==2
    failed=read(e/'known_audit1/report.json');assert failed['result']=='failed'
    assert 'all_original_quadratic_terms' in failed['error']
    assert sha(e/'known_audit1/executed_audit.py')!=sha(e/'known_audit2/executed_audit.py')
    passed=read(e/'known_audit2/report.json');assert passed['pass_count']==12
    assert sum(not c['stricter_whitened_2e_11_diagnostic_passed'] for c in passed['cases'])==8
    controls=read(e/'controls_audit1/report.json');assert controls['all_qualified']
    assert (len(controls['cases']),len(controls['frames']),len(controls['temporal']))==(7,4,3)
    resources=read(e/'resources_audit1/report.json')
    assert resources['result']=='independent_waveform_structured_resources_verified'
    assert resources['current_cumulative_peak_bytes']==v['current_cumulative_process_peak_bytes']==962129920
    assert resources['full_conditional_arrays']==v['full_conditional_arrays']
    assert resources['dependencies']['scipy_qr_source_sha256']==sha(e/'resources_audit1/scipy_qr_source.txt')
    assert sha(e/'resources_audit1/executed_audit.py')==resources['auditor_sha256']
    assert sha(e/'executed_package.py')==sha(a.archive/'source/tools/package_waveform_structured_v1.py')
    result=dict(result='independent_waveform_structured_archive_bindings_verified',source_bindings=sources,
        original_input_bindings=inputs,array_bindings=arrays,metric_executed_versions=len(metric_versions),
        original12_qualified=12,failed_extra_audit_and8diagnostics_retained=True,
        peak_working_set_bytes=962129920,full_arrays_not_allocated=True,auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result,flush=True)


if __name__=='__main__':main()
