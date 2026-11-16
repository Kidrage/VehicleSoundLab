"""Qualify compensated primitives then diagnose the SAME four saved known inputs."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


SOURCES=('research/operator_roundoff_v1_plan.json','tools/operator_roundoff_v1/__init__.py',
    'tools/operator_roundoff_v1/compensated.py','tools/operator_roundoff_v1/exact_dyadic.py',
    'tools/operator_roundoff_v1/known.py','tools/operator_roundoff_v1/diagnostics.py',
    'tools/run_operator_roundoff_v1.py','tools/audit_operator_roundoff_v1.py',
    'tools/constrained_source_operator_v1/oracle.py','tools/locked_source_guard_v1/measurement.py',
    'tools/observer_complete_v1/audit_oracle.py','tools/research_archive_v1.py')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from operator_roundoff_v1.known import qualify
    from operator_roundoff_v1.diagnostics import analyze
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},inputs={},cases=[])
    try:
        for name in SOURCES:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        r['known']=qualify();r['known_before_saved_packet_use']=True;save(a.out/'report.json',r)
        source=load(a.study/'report.json');audit=load(a.audit/'report.json')
        assert audit['producer_sha256']==sha(a.study/'report.json') and not audit['verification_passed'] and len(audit['failures'])==19
        oracle='tools/constrained_source_operator_v1/oracle.py'
        assert source['sources'][oracle]==sha(repo/oracle)==sha(a.study/'exact_sources'/oracle)
        for path in (a.study/'report.json',a.audit/'report.json'):r['inputs'][str(path)]=sha(path)
        for case in source['cases']:
            if case['unknowns']>32:continue # full unchanged case is explicitly not rerun
            path=a.study/case['name']/'operators.npz';assert sha(path)==case['packet_sha256']
            r['inputs'][str(path)]=sha(path)
            with np.load(path) as f:z={key:f[key] for key in f.files}
            arrays,details=analyze(z);directory=a.out/case['name'];directory.mkdir()
            np.savez_compressed(directory/'roundoff.npz',**arrays)
            details.update(name=case['name'],packet_sha256=sha(directory/'roundoff.npz'))
            save(directory/'report.json',details);r['cases'].append(details);save(a.out/'report.json',r)
            print('KNOWN_ROUNDOFF',case['name'],details['gradient']['FFT_vs_compensated']['peak_relative'],flush=True)
        assert len(r['cases'])==4
        r.update(result='saved_small_operator_roundoff_decomposed',no_full_unchanged_case_rerun=True,
            original_19_failures_and_original_2e_11_check_not_relabelled=True,
            whole_operator_or_constrained_solver_qualification=False,new_C1_source_eligible_for_statistics=False,
            no_vehicle_fit_audio_C_or_audible_cause_claim=True)
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
