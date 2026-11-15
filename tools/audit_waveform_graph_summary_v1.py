"""Bind three original12 attempts and independently derive the graph summary."""
import argparse
import shutil
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    baseline=a.workspace/'baselines/waveform_representer_v1/evidence'
    reports={};inputs={};rows=[]
    for tag,source_dir,audit_dir in (
        ('previous',baseline/'known2',baseline/'known_audit2'),
        ('nullspace',a.study/'known1',a.study/'known_audit1'),
        ('graph',a.study/'graph_known1',a.study/'graph_known_audit1')):
        source=load(source_dir/'report.json');audit=load(audit_dir/'report.json')
        for path in (source_dir/'report.json',audit_dir/'report.json'):inputs[str(path)]=sha(path)
        assert audit['producer_sha256']==sha(source_dir/'report.json')
        assert audit['auditor_sha256']==sha(audit_dir/'executed_audit.py')
        assert len(source['cases'])==len(audit['cases'])==12
        records=[]
        for s,v in zip(source['cases'],audit['cases']):
            assert s['label']==v['label'] and s['kind']==v['kind']
            assert sha(source_dir/s['file'])==s['sha256']
            assert v['qualified']==s['qualified']
            for name,expected in source['sources'].items():assert sha(source_dir/'exact_sources'/name)==expected
            ratios={tag:s[tag+'_certificate']['gap_upper_bound']/(1e-6*s[tag+'_certificate']['primal']+1e-10)
                    for tag in ('residual','representer')}
            for name in ratios:
                cert=s[name+'_certificate']
                assert cert['relative_gate']==1e-6 and cert['absolute_gate']==1e-10
                assert (ratios[name]<=1)==cert['additional_gap_gate_passed']
            original=(v['dense_relative_error']<2e-7 and v['original_gradient']<2e-7 and all(x<=1 for x in ratios.values()))
            assert original==v['original_equations_and_gaps_passed']
            qualified=(original and v['original_stable_normal_relative']<=1e-11
                       and v['original_backward_discrepancy']<=1e-11 and s['solver']['stable_root_guard_passed'])
            assert qualified==v['qualified']
            row=dict(version=tag,label=s['label'],kind=s['kind'],dense_error=v['dense_relative_error'],
                original_gradient=v['original_gradient'],gap_ratios=ratios,qualified=qualified,
                original_equations_and_gaps_passed=original,
                original_stable_normal=v['original_stable_normal_relative'],
                original_backward_discrepancy=v['original_backward_discrepancy'],
                original_direct_normal=v['independent_original_direct_normal_relative'],
                root_direct_normal=v['root_direct_normal_relative'],
                metric_seconds=s['metric_build_seconds'],solve_seconds=s['root_and_solve_seconds'],
                cumulative_process_peak_bytes=s['process_peak_working_set_bytes'])
            rows.append(row);records.append(row)
        reports[tag]=dict(qualified=sum(c['qualified'] for c in records),
            original_equations_and_gaps_passed=sum(c['original_equations_and_gaps_passed'] for c in records),
            original_direct_normal_passed=sum(c['original_direct_normal']<=1e-11 for c in records),
            failed_labels=[c['label'] for c in records if not c['qualified']],
            max_stable_normal=max(c['original_stable_normal'] for c in records),
            max_backward_discrepancy=max(c['original_backward_discrepancy'] for c in records),
            min_dense_error=min(c['dense_error'] for c in records),max_dense_error=max(c['dense_error'] for c in records),
            max_original_gap_ratio=max(x for c in records for x in c['gap_ratios'].values()),
            cumulative_process_peak_bytes=max(c['cumulative_process_peak_bytes'] for c in records))
    assert [reports[k]['qualified'] for k in ('previous','nullspace','graph')]==[9,9,12]
    assert reports['graph']['original_equations_and_gaps_passed']==12
    for stem in ('','graph_'):
        producer=a.study/(stem+'explicit1');audit_dir=a.study/(stem+'explicit_audit1')
        s,v=load(producer/'report.json'),load(audit_dir/'report.json')
        assert v['producer_sha256']==sha(producer/'report.json')
        assert len(v['cases'])==7 and len(v['frames'])==4 and v['all_qualified']
        assert all(c['qualified'] and c['Decimal_precisions']==[80,110] for c in v['cases'])
        assert all(c['qualified'] and c['all_entries']==41**2 for c in v['frames'])
        for path in (producer/'report.json',audit_dir/'report.json'):inputs[str(path)]=sha(path)
    diagnosis=load(a.study/'precision_diagnosis1/report.json')
    d_audit=load(a.study/'precision_audit1/report.json')
    assert d_audit['result']=='independent_waveform_nullspace_diagnosis_verified'
    assert d_audit['producer_sha256']==sha(a.study/'precision_diagnosis1/report.json')
    assert len(diagnosis['cases'])==len(d_audit['cases'])==4
    for path in (a.study/'precision_diagnosis1/report.json',a.study/'precision_audit1/report.json'):inputs[str(path)]=sha(path)
    result=dict(result='independent_waveform_graph_summary_verified',rows=rows,versions=reports,
        inputs=inputs,explicit_controls_per_version=7,finite_DFT_controls_per_version=4,
        independent_Decimal_diagnostic_cases=4,all_original_gates_unchanged=True,
        failed_nullspace_attempt_retained=True,source_or_full_or_native48k_or_C_or_hearing_qualified=False,
        auditor_sha256=sha(__file__))
    save(a.out/'report.json',result);print(reports,flush=True)


if __name__=='__main__':main()
