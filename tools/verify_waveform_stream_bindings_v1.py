"""Independent input, source-version, original-gate and archive bindings."""
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
    e=a.archive/'evidence';v=read(a.archive/'validation.json')
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    manifests={}
    for name,h in v['upstream_manifests_sha256'].items():
        path=a.archive/'inputs/upstream'/name/'manifest.json';assert sha(path)==h
        manifests[name]={r['path']:r['sha256'] for r in read(path)['files']}
    sources=inputs=arrays=0
    for folder in v['selected_terminal_evidence_directories']:
        report=read(e/folder/'report.json')
        for name,h in report.get('inputs',{}).items():
            target=v['original_input_archive_locations'][name];assert sha(a.archive/target)==h
            parts=Path(target).parts
            if parts[0]=='inputs':assert manifests[parts[2]][Path(*parts[3:]).as_posix()]==h
            else:assert parts[0]=='evidence' and parts[1] in v['selected_terminal_evidence_directories']
            inputs+=1
        for name,h in report.get('sources',{}).items():assert sha(e/folder/'exact_sources'/name)==h;sources+=1
        for group in ('cases','frames','temporal'):
            for case in report.get(group,[]):
                if 'file' in case:assert sha(e/folder/case['file'])==case['sha256'];arrays+=1
        if 'auditor_sha256' in report:assert sha(e/folder/'executed_audit.py')==report['auditor_sha256']
    for audit,producer in (('controls_audit1','controls1'),('controls_shared_audit1','controls_shared1'),
        ('known_audit1','known1'),('shared_audit2','shared1')):
        r=read(e/audit/'report.json');assert r['producer_sha256']==sha(e/producer/'report.json') and r['all_qualified']
    failed=read(e/'shared_audit1/report.json');assert failed['result']=='failed' and 'shared_Frobenius' in failed['error']
    known=read(e/'known_audit1/report.json');shared=read(e/'shared_audit2/report.json');resources=read(e/'resources_audit2/report.json')
    assert known['pass_count']==12 and shared['pass_count']==8
    assert sum(not c['stricter_whitened_2e_11_diagnostic_passed'] for c in known['cases'])==8
    assert sum(not c['supplemental_original_oracle_Frobenius_2e_11_passed'] for c in shared['cases'])==3
    assert len(shared['rejections_preserved'])==7 and all(c['rejected'] for c in shared['rejections_preserved'])
    assert resources['full_shared_two_RHS_conditional_arrays']==v['full_shared_two_RHS_conditional_arrays']
    assert resources['full_shared_two_RHS_conditional_arrays']['coexisting_four_array_subtotal']==9173984280
    assert resources['dependencies']['triangular_source_sha256']==sha(e/'resources_audit2/scipy_solve_triangular_source.txt')
    assert sha(e/'executed_package.py')==sha(a.archive/'source/tools/package_waveform_stream_v1.py')
    result=dict(result='independent_waveform_stream_archive_bindings_verified',source_bindings=sources,
        original_input_bindings=inputs,array_bindings=arrays,original12_qualified=12,shared8_qualified=8,
        mismatched_operator_rejections=7,strict_white8_and_shared_Frobenius3_failures_retained=True,
        no_full_or_audio_C_promotion=True,auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result,flush=True)


if __name__=='__main__':main()
