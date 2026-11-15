"""Independent diagnosis archive bindings; retain failure and protocol scopes."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('archive','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    def load(path):return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    v=load(a.archive/'validation.json');e=a.archive/'evidence';count=0
    def bound(name,digest):
        nonlocal count
        path=a.archive/v['original_input_archive_locations'][name]
        assert path.resolve().is_relative_to(a.archive.resolve()) and sha(path)==digest
        count+=1
    reports={name:load(e/name/'report.json') for name in v['selected_terminal_evidence_directories']}
    for folder,report in reports.items():
        for name,digest in report.get('inputs',{}).items():bound(name,digest)
        for name,digest in report.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest==v['executed_source_versions'][name][folder]
        for c in report.get('cases',[]):
            if 'file' in c:assert sha(e/folder/c['file'])==c['sha256']
            if 'report' in c:assert sha(e/folder/c['report'])==c['sha256']
    assert reports['known1']['result']==reports['known2']['result']=='extraction_sound_known_measured'
    assert reports['known_audit1']['result']=='failed' and 'line_CV' in reports['known_audit1']['error']
    assert reports['roundoff1']['original_failure']==reports['known_audit1']
    composed=reports['known_composed_audit1']
    assert len(composed['cases'])==9 and composed['operator_and_frozen_series_aggregation_qualified']
    assert not composed['legacy_cross_operator_all_statistics_qualified'] and len(composed['legacy_normalized_failures'])==5
    assert composed['producer_sha256']==sha(e/'known2/report.json')
    labels={c['label'] for c in composed['cases']};assert 'weak_HF' in labels and 'compact_all_bins' in labels
    assert all(c['operator_and_aggregation_qualified'] for c in composed['cases'])
    for failure in composed['legacy_normalized_failures']:
        assert failure['prefix']=='line' and all(i[0]==5 for i in failure['indices'])
        assert not any(failure['power_resolved'][5])
    assert len(reports['known_cases1']['cases'])==3 and len(reports['known_cases1']['guard_rejections'])==6
    for name in ('known_cases_audit1','known_cases_audit2'):
        proof=reports[name];assert proof['all_consumer_checks_passed'] and not proof['actual_recorded_case_qualified']
        assert proof['producer_sha256']==sha(e/'known_cases1/report.json')
    assert reports['known_cases_audit2']['signed_power_covariance_gates_use_actual_nonzero_field_scales']
    for c in reports['known_cases1']['cases']:
        r=load(e/'known_cases1'/c['report']);folder=e/'known_cases1'/c['label']
        for name,digest in r['inputs'].items():bound(name,digest)
        bound(r['source']['binding_file'],r['source']['binding_sha256'])
        for region in r['regions']:assert sha(folder/region['file'])==region['sha256']
    for name,digest in v['current_source_sha256'].items():assert sha(a.archive/'source'/name)==digest
    assert v['C_H_exact']==670 and v['voice_parameters_exact']==82 and v['F2_files_exact']==3
    assert not v['legacy_cross_operator_all_statistics_qualified'] and not v['numerical_sensitivity_is_certified']
    for original in v['original_input_archive_locations']:
        if '/waveform_file_real_v1/real1/' in original.replace('\\','/'):
            assert Path(original).name=='run_spec.json'
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    result=dict(result='independent_extraction_sound_bindings_verified',all_archive_bindings_verified=True,
        checked_bindings=count,known_meter_cases=9,known_consumers=3,retained_normalized_failures=5,
        no_live_fit_payload_or_completion_claim=True,manifest_sha256=sha(a.archive/'manifest.json'),
        auditor_sha256=sha(__file__))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
