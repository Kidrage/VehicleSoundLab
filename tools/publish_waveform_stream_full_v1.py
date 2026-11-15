"""Retain all seventeen full/target/region comparisons against latest failed solve."""
import argparse
import shutil
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('study','audit','previous','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_publication.py')
    source,audit,previous=[load(p/'report.json') for p in (a.study,a.audit,a.previous)]
    assert audit['solver_qualified'] and audit['fidelity_qualified'] and audit['producer_sha256']==sha(a.study/'report.json')
    assert previous['result']=='observer_stable_full_known_measured' and not previous['solver_qualified']
    rows=[]
    for name,value in audit['metrics'].items():
        before=previous['metrics'][name]
        for index,(old,new) in enumerate(zip(before,value)) if isinstance(value,list) else [(None,(before,value))]:
            rows.append(dict(metric=name,index=index,previous=old,current=new,regressed=bool(new>old),difference=new-old))
    assert len(rows)==17
    result=dict(result='waveform_stream_full_comparison_published',rows=rows,regressions=[r for r in rows if r['regressed']],
        objective_before=previous['residual_certificate']['primal'],objective_after=audit['residual_certificate']['primal'],
        original_gradient_before=previous['solver']['relative_stationarity'],original_gradient_after=audit['gradient'],
        residual_gap_before=previous['residual_certificate']['gap_upper_bound'],residual_gap_after=audit['residual_certificate']['gap_upper_bound'],
        representer_gap_before=previous['representer_certificate']['gap_upper_bound'],representer_gap_after=audit['representer_certificate']['gap_upper_bound'],
        solver_before=False,solver_after=True,host_elapsed_seconds=source['solve_wall_seconds'],
        actual_working_set_peak=source['process_memory']['cumulative_peak_working_set_bytes'],
        actual_private_commit_peak=source['process_memory']['cumulative_peak_private_commit_bytes'],
        registered_live_backing_peak=source['resources']['max_tracked_live_backing_bytes'],
        inputs={str(p/'report.json'):sha(p/'report.json') for p in (a.study,a.audit,a.previous)},
        publisher_sha256=sha(__file__),no_actual_audio_or_C_promotion=True)
    save(a.out/'report.json',result)
    print(result['result'],'rows',len(rows),'regressions',len(result['regressions']),flush=True)


if __name__=='__main__':main()
