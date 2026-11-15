"""ONE sequential unchanged complete-file solve of all SIX prepared real cases."""
import argparse
import gc
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','preparation','preparation-audit','generic-audit','out'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from waveform_file_real_v1.prepare import build
    from waveform_file_real_v1.evaluate import evaluate
    from waveform_file_real_v1.resources import preflight
    from waveform_file_full_v1.pipeline import solve_full
    from waveform_file_full_v1.resources import Telemetry
    from waveform_banded_v1.metric import supported_banded
    from waveform_structured_v1.resources import process_memory
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    r=dict(result='running',pid=os.getpid(),only_one_sequential_run=True,cases=[],sources={},inputs={},block=1024)
    try:
        def bind(path):
            path=Path(path);r['inputs'][str(path)]=sha(path);return path
        preparation=load(bind(a.preparation/'report.json'))
        pa=load(bind(a.preparation_audit/'report.json'))
        ga=load(bind(a.generic_audit/'report.json'))
        assert preparation['result']=='waveform_file_real_six_prepared' and len(preparation['cases'])==6
        assert pa['result']=='independent_waveform_file_real_preparation_verified' and pa['all_qualified']
        assert pa['producer_sha256']==sha(a.preparation/'report.json') and len(pa['cases'])==6
        assert ga['result']=='independent_waveform_file_real_known_auditor_verified' and ga['all_qualified'] and len(ga['cases'])==3
        for original in (preparation,ga):
            for name,digest in original['sources'].items():assert sha(repo/name)==digest
        for name,digest in preparation['inputs'].items():assert sha(bind(name))==digest
        for c in preparation['cases']:assert sha(bind(a.preparation/c['file']))==c['sha256']
        disk=sum(c['resources']['full_factor_disk_bytes'] for c in preparation['cases'])
        assert disk==preparation['retained_six_factor_bytes'] and shutil.disk_usage(a.out).free>=disk+2*1024**3
        names=set(preparation['sources'])|set(ga['sources'])|{'tools/run_waveform_file_real_v1.py',
            'tools/audit_waveform_file_real_v1.py','tools/waveform_file_real_v1/audit.py',
            'research/waveform_file_real_v1_plan.json','tools/research_archive_v1.py'}
        for name in sorted(names):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        r['declared_cases']=[c['label'] for c in preparation['cases']]
        save(a.out/'run_spec.json',dict(schema='vsl.real_file_run_spec/1',pid=os.getpid(),
            declared_cases=r['declared_cases'],sources=r['sources'],inputs=r['inputs'],
            only_one_sequential_run=True,block=1024,retained_six_factor_bytes=disk))
        save(a.out/'report.json',r)
        print('REAL_SIX_PID',os.getpid(),'CASES',len(preparation['cases']),flush=True)
        for index,c in enumerate(preparation['cases']):
            label=c['label'];directory=a.out/label;directory.mkdir()
            with np.load(a.preparation/c['file']) as f:z={n:f[n] for n in f.files}
            system,shared,reference=build(z['audio'],z['target'],z['original_positions'],z['orders'],z['scale'])
            metric=system.metric
            assert np.array_equal(z['positions'],system.synthesis.positions)
            for name in ('weights','band_power','floor_active'):assert np.array_equal(z[name],getattr(metric,name))
            assert float(z['sigma'])==metric.wave_scale and float(z['amplitude'])==metric.amplitude_scale
            resources=preflight(directory,len(z['audio']),len(z['positions']),288,1024)
            if not resources['memory_passed'] or not resources['disk_passed']:
                save(directory/'preflight_failed.json',resources)
                raise MemoryError('Real case original reserves failed before allocating any complete factor')
            remaining=sum(x['resources']['full_factor_disk_bytes'] for x in preparation['cases'][index:])
            assert shutil.disk_usage(directory).free>=remaining+2*1024**3
            save(directory/'preflight.json',resources)
            ledger=Telemetry(directory);factors=directory/'factors';factors.mkdir()
            r['current_case']=label;r['current_case_index']=index
            save(a.out/'report.json',r)
            print('REAL_FIT_START',label,'N',len(z['audio']),'M',len(z['positions']),flush=True)
            action=lambda e:e/metric.wave_scale**2+metric.adjoint(metric.forward(e))
            values,inverse,pipeline,initial,taus=solve_full(shared,lambda:supported_banded(metric),z['audio'],action,factors,ledger,1024)
            inverse.close();inverse_info=inverse.info()
            outputs,stats=evaluate(system,shared,z['audio'],values,pipeline['base_solver'],reference)
            ledger.snapshot('fullPipeline.evaluated')
            z.update(values,**outputs,**taus,inverse_right_tau=inverse.right.tau,inverse_inner_tau=inverse.inner.tau,
                **{'base_'+key:value for key,value in initial.items()})
            np.savez_compressed(directory/'capture.npz',**z)
            ledger.snapshot('fullPipeline.saved')
            info=dict(result='waveform_file_real_case_measured',label=label,frames=len(z['audio']),nodes=len(z['positions']),orders=288,block=1024,
                pipeline=pipeline,solver=pipeline['base_solver'],inverse_info=inverse_info,**stats,
                resource_preflight=resources,resources=ledger.report(),process_memory=process_memory(),
                capture_sha256=sha(directory/'capture.npz'),prepared_file=str(a.preparation/c['file']),prepared_sha256=c['sha256'],
                no_full_factor_arrays_in_capture=True,no_sustained_source_or_C_or_hearing_promotion=True,
                process_peak_is_cumulative_not_isolated_case=True)
            save(directory/'report.json',info)
            ledger.progress(dict(pid=os.getpid(),status='completed',label=label,report_sha256=sha(directory/'report.json')))
            del z,values,outputs,inverse,system,shared,reference,initial,taus,pipeline,metric,action
            gc.collect()
            # Each case report/spec is now immutable. Its independent auditor
            # is a separate process; no producer helper is used by its equations.
            audit_dir=a.out/(label+'_audit')
            subprocess.run([sys.executable,str(repo/'tools/audit_waveform_file_real_v1.py'),
                '--workspace',str(a.workspace),'--study',str(directory),'--out',str(audit_dir)],check=True,cwd=repo)
            audited=load(audit_dir/'report.json')
            assert audited['verification_passed']
            row=audited['cases'][0]
            assert row['producer_sha256']==sha(directory/'report.json')
            r['cases'].append(dict(label=label,case_report=label+'/report.json',case_report_sha256=sha(directory/'report.json'),
                audit_report=audit_dir.name+'/report.json',audit_report_sha256=sha(audit_dir/'report.json'),
                verification_passed=True,solver_qualified=row['solver_qualified'],fidelity_qualified=row['fidelity_qualified'],metrics=row['metrics']))
            save(a.out/'report.json',r)
            print('REAL_FIT_AUDITED',label,'solver',row['solver_qualified'],'fidelity',row['fidelity_qualified'],flush=True)
        r.update(result='waveform_file_real_six_measured',verification_passed=True,
            all_solver_qualified=all(c['solver_qualified'] for c in r['cases']),all_fidelity_qualified=all(c['fidelity_qualified'] for c in r['cases']),
            elapsed_seconds_PC_only=time.monotonic()-started,no_C_or_hearing_or_sustained_voice_promotion=True)
        save(a.out/'report.json',r)
        print('REAL_SIX_COMPLETE',r['all_solver_qualified'],r['all_fidelity_qualified'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error),elapsed_seconds_PC_only=time.monotonic()-started)
        save(a.out/'report.json',r);raise


if __name__=='__main__':main()
