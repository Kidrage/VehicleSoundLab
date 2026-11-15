"""Independent immutable full-file source/input/factor/result bindings."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive','out'): p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    def read(path): return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
    v = read(a.archive/'validation.json')
    e = a.archive/'evidence'
    assert {x.name for x in e.iterdir() if x.is_dir()} == set(v['selected_terminal_evidence_directories'])
    manifests = {}
    for name,digest in v['upstream_manifests_sha256'].items():
        path = a.archive/f'inputs/upstream/{name}/manifest.json'
        assert sha(path) == digest
        manifests[name] = {x['path']:x['sha256'] for x in read(path)['files']}
    inputs = versions = factor_count = 0
    def bound(name,digest):
        target = v['original_input_archive_locations'][name]
        path = a.archive/target
        assert path.resolve().is_relative_to(a.archive.resolve()) and sha(path) == digest
        parts = Path(target).parts
        if parts[:2] == ('inputs','upstream'):
            leaf = Path(*parts[3:]).as_posix()
            expected = v['upstream_manifests_sha256'][parts[2]] if leaf=='manifest.json' else manifests[parts[2]][leaf]
            assert expected == digest
    def factors(x):
        nonlocal factor_count
        if isinstance(x,dict):
            if {'path','shape','file_bytes','sha256'} <= x.keys():
                bound(x['path'],x['sha256'])
                assert x['file_bytes'] == x['declared_bytes'] == 8*x['shape'][0]*x['shape'][1]
                assert x['closed'] and not x['mapped']
                factor_count += 1
            for child in x.values(): factors(child)
        elif isinstance(x,list):
            for child in x: factors(child)
    reports = {}
    for folder in v['selected_terminal_evidence_directories']:
        r = reports[folder] = read(e/folder/'report.json')
        for name,digest in r.get('inputs',{}).items():
            bound(name,digest)
            inputs += 1
        for name,digest in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name) == digest == v['executed_source_versions'][name][folder]
            versions += 1
        for index,(name,digest) in enumerate(r.get('oracles_sha256',{}).items()):
            assert sha(e/folder/f'executed_oracle_{index}.py') == digest
        if 'capture_sha256' in r: assert sha(e/folder/'capture.npz') == r['capture_sha256']
        if 'auditor_sha256' in r: assert sha(e/folder/'executed_audit.py') == r['auditor_sha256']
        if 'inspector_sha256' in r: assert sha(e/folder/'executed_inspection.py') == r['inspector_sha256']
        for case in r.get('cases',[]):
            if 'file' in case and 'sha256' in case: assert sha(e/folder/case['file']) == case['sha256']
            if 'node_file' in case: assert sha(e/folder/case['node_file']) == case['node_sha256']
        factors(r)
    for name,digest in v['current_source_sha256'].items(): assert sha(a.archive/'source'/name) == digest
    panel,pa = reports['panels1'],reports['panels_audit1']
    assert panel['block'] == pa['block'] == 1024 and pa['all_qualified']
    assert pa['producer_sha256'] == sha(e/'panels1/report.json') and len(pa['cases']) == 2
    base = reports['base_guard1']
    assert base['all_qualified'] and len(base['cases']) == 7
    assert all(c['qualified'] and len(c['ownership_rejections'])==2 and c['perturbed_waveform_rejected'] for c in base['cases'])
    full,audit = reports['full1'],reports[v['selected_full_audit']]
    assert full['only_one_attempt'] and full['result'] == 'waveform_file_full_known_measured'
    assert full['solver_qualified'] and full['fidelity_qualified'] and audit['all_qualified']
    assert audit['producer_sha256'] == sha(e/'full1/report.json')
    assert read(e/'full1/progress.json')['status'] == 'completed'
    assert read(e/'full1/progress.json')['report_sha256'] == sha(e/'full1/report.json')
    assert audit['gradient'] < 2e-7 and audit['stable_original_complete_normal'] <= 1e-11 and audit['original_backward'] <= 1e-11
    assert audit['residual_gap_passed'] and audit['representer_gap_passed'] and audit['extra_trace2e_11_passed']
    assert len(audit['original_correction_history']) == 3
    assert len(audit['comparison_rows']) == 17 and audit['comparison_rows'] == v['full_comparison_rows'] == full['comparison_rows']
    assert audit['file_resource_audit'] == v['full_resource_audit'] and audit['file_resource_audit']['all_qualified']
    assert audit['metrics'] == v['full_metrics']
    for key,field in (('gradient','full_gradient'),('stable_original_complete_normal','full_stable_complete_normal'),('original_backward','full_backward')):
        assert audit[key] == v[field]
    resources = reports[v['selected_resources_audit']]
    peak = reports['peak_audit1']
    assert peak['all_qualified'] and peak['measured_comparison'] == v['measured_lifetime_budget_comparison']
    assert resources['all_qualified'] and len(resources['cases']) == 12
    assert resources['cases'] == v['all12_conditional_resources']
    assert resources['all12_conditional_preflights_passed'] == v['all12_conditional_preflights_passed']
    assert sha(e/'executed_package.py') == sha(a.archive/'source/tools/package_waveform_file_full_v1.py')
    doc = (a.archive/'source/research/完整文件声纹提取验证V1.md').read_text(encoding='utf-8')
    numbers = [full['process_memory']['cumulative_peak_working_set_bytes'],
        full['process_memory']['cumulative_peak_private_commit_bytes'],
        audit['file_resource_audit']['registered_peak_bytes'],audit['file_resource_audit']['factor_file_bytes'],
        audit['file_resource_audit']['panel_read_bytes'],audit['file_resource_audit']['panel_write_bytes']]
    assert all(format(n,',') in doc for n in numbers)
    assert not v['real_inverse_fit_executed'] and v['no_C_or_timbre_promotion'] and v['full_goal']=='active'
    result = dict(result='independent_waveform_file_full_archive_bindings_verified',
        inputs_verified=inputs,executed_source_versions_verified=versions,factor_descriptors_verified=factor_count,
        original_full_gates_all3histories_and17signed_rows_verified=True,
        all_versions_and_actual_resources_verified=True,published_resources_verified=True,
        auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result,flush=True)


if __name__ == '__main__': main()
