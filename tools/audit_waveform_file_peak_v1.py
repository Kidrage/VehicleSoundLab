"""Compare measured registered lifetimes with declared phase/global arithmetic."""
import argparse
from pathlib import Path
import shutil
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('study','out'): p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r = dict(result='running',inputs={str(a.study/'report.json'):sha(a.study/'report.json')})
    try:
        source = load(a.study/'report.json')
        assert source['result']=='waveform_file_full_known_measured'
        assert load(a.study/'progress.json')['status']=='completed'
        events,stores = source['resources']['events'],source['resources']['storage_bytes']
        names,shapes,rows = {},{},[]
        released = False
        for x in events:
            if x['event']=='array':
                names.setdefault(x['storage'],set()).add(x['name'])
                shapes[x['storage']] = x['shape']
                continue
            if x['phase']=='fullPipeline.metric_and_graph_released': released=True
            ids = x['live_storages']
            actual = sum(stores[j] for j in ids)
            assert actual==x['tracked_live_backing_bytes']
            if x['phase']=='fileQR.upper_transpose.materialized' and not released:
                rows.append(dict(tracked_bytes=actual,
                    live_arrays=[dict(storage=j,bytes=stores[j],shape=shapes[j],names=sorted(names[j])) for j in ids]))
        assert rows
        largest = max(rows,key=lambda x:x['tracked_bytes'])
        peak = max(x['tracked_live_backing_bytes'] for x in events if x['event']=='snapshot')
        declared = source['resource_preflight']
        N,n,k,B = 12289,28224,12289,1024
        # During a later transpose, the previous returned panel remains owned
        # by its caller while the new input and output panels coexist.
        three_panel = 8*4096*N+8*k*B+3*8*n*B
        result = dict(registered_peak_bytes=peak,declared_main_allowance=declared['main_phase_array_allowance'],
            global_registered_allowance_passed=peak<=declared['main_phase_array_allowance'],
            original_graph_transpose_phase_arithmetic=declared['major_phase_panel_arithmetic']['graph_transpose'],
            observed_graph_transpose_registered_peak=largest['tracked_bytes'],
            original_phase_estimate_covers_observed=largest['tracked_bytes']<=declared['major_phase_panel_arithmetic']['graph_transpose'],
            corrected_three_panel_graph_transpose_arrays=three_panel,
            corrected_phase_plus_existing_misc_covers_observed=largest['tracked_bytes']<=three_panel+declared['resident_misc_allowance'],
            largest_graph_transpose_snapshot=largest)
        assert result['global_registered_allowance_passed']
        assert result['corrected_phase_plus_existing_misc_covers_observed']
        r.update(result='independent_waveform_file_measured_lifetimes_verified',all_qualified=True,
            measured_comparison=result,auditor_sha256=sha(__file__),
            unregistered_temporaries_and_physical_process_peak_are_separate=True)
        save(a.out/'report.json',r)
        print(r['result'],peak,'phase_covers',result['original_phase_estimate_covers_observed'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__': main()
