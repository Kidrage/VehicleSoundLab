"""Fixed two original-operator corrections of SAME archived original12/shared8."""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','base-audit','prerequisite','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--kind',choices=('original12','shared8'),required=True)
    p.add_argument('--inverse-backend',choices=('copy','native'),default='copy')
    p.add_argument('--pipeline',action='store_true');a=p.parse_args()
    if a.pipeline and a.inverse_backend!='native':p.error('Pipeline requires declared native backend')
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from waveform_correction_v1.inverse import NormalInverse
    if a.inverse_backend=='native':
        from waveform_correction_v1.native_inverse import NativeNormalInverse as NormalInverse
    from waveform_correction_v1.correct import refine
    from waveform_correction_v1.problem import restore,evaluate
    from waveform_structured_v1.resources import ArrayLedger,process_memory
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',kind=a.kind,pid=os.getpid(),cases=[],sources={},inputs={},material_read=False,fixed_correction_steps=2,inverse_backend=a.inverse_backend,pipeline=a.pipeline)
    try:
        prerequisite=load(a.prerequisite/'report.json')
        assert prerequisite['result']=='independent_waveform_original_correction_controls_passed' and prerequisite['all_qualified']
        source=load(a.study/'report.json');audit=load(a.base_audit/'report.json')
        assert audit['producer_sha256']==sha(a.study/'report.json')
        assert len(source['cases'])==(12 if a.kind=='original12' else 8)
        assert audit['pass_count']==(12 if a.kind=='original12' else 7)
        root=a.workspace/'baselines/waveform_banded_v1'
        assert a.study.is_relative_to(root) and a.base_audit.is_relative_to(root)
        manifest=load(root/'manifest.json');entries={v['path']:v['sha256'] for v in manifest['files']}
        assert sha(root/'manifest.json')==load(repo/'research/waveform_banded_v1_summary.json')['manifest_sha256']
        assert entries[(a.study/'report.json').relative_to(root).as_posix()]==sha(a.study/'report.json')
        for path in (a.study/'report.json',a.base_audit/'report.json',a.prerequisite/'report.json',root/'manifest.json'):
            r['inputs'][str(path)]=sha(path)
        names=set(source['sources'])
        names.update(('tools/run_waveform_correction_known_v1.py','research/waveform_original_correction_v1_plan.json'))
        if a.inverse_backend=='native':names.add('research/waveform_correction_storage_v1_plan.json')
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/waveform_correction_v1').glob('*.py'))
        for n in sorted(names):
            path=a.out/'exact_sources'/n;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/n,path);r['sources'][n]=sha(path)
        for case in source['cases']:
            started=time.perf_counter();file=a.study/case['file'];digest=sha(file)
            assert digest==case['sha256']==entries[file.relative_to(root).as_posix()];r['inputs'][str(file)]=digest
            with np.load(file) as z:
                base={n:z[n] for n in ('audio','positions','orders','scale','original','x_raw','x_tau','q','z','wave_model_residual')}
            system,prior,forward,adjoint,metric_action=restore(a.kind,case,base)
            ledger=ArrayLedger();pipeline_info={};initial={}
            if a.pipeline:
                import hashlib
                from waveform_correction_v1.pipeline import solve_corrected
                from waveform_banded_v1.metric import BandedMetric,supported_banded
                expected_X_sha=hashlib.sha256(memoryview(base['x_raw'].ravel(order='F'))).hexdigest()
                del base['x_raw'],base['x_tau']
                if case['kind']=='algebra':
                    W=system.wave_metric[::base['audio'].shape[1],::base['audio'].shape[1]] if a.kind=='shared8' else system.wave_metric
                    factory=lambda:BandedMetric.control_from_dense(W)
                else:factory=lambda:supported_banded(system.metric)
                target=base['audio'] if a.kind=='shared8' else base['audio'].ravel()
                corrected,inverse,pipeline_info,initial=solve_corrected(forward,adjoint,prior,factory,target,metric_action,ledger,case['solver']['block'])
                assert pipeline_info['source_QR_sha256']==expected_X_sha
                assert np.array_equal(initial['z'],base['z'])
                assert np.array_equal(initial['wave_model_residual'],base['wave_model_residual'])
            else:
                ledger.add('base.x_raw',base['x_raw'])
                inverse=NormalInverse(base['x_raw'],ledger,block=16)
                corrected=refine(forward,adjoint,prior,metric_action,base,inverse)
            original,stats=evaluate(system,base['audio'],corrected,base['original'],a.kind)
            if case['label']=='silent_right' and a.kind=='shared8':
                assert np.count_nonzero(corrected['q'][:,1])==np.count_nonzero(corrected['wave_model_residual'][:,1])==0
            if case['label']=='both_zero':assert np.count_nonzero(corrected['q'])==0
            path=a.out/(case['kind']+'_'+case['label']+'.npz')
            np.savez_compressed(path,**{n:base[n] for n in ('audio','positions','orders','scale','original')},
                **corrected,**original,**inverse.arrays(),**{'pipeline_base_'+n:v for n,v in initial.items()})
            ledger.snapshot('correction.known_complete')
            row=dict(label=case['label'],kind=case['kind'],file=path.name,sha256=sha(path),base_file=str(file),
                previous_qualified=case['qualified'],factor=inverse.info(),resources=ledger.report(),
                pipeline_info=pipeline_info,
                process_memory=process_memory(),elapsed_seconds=time.perf_counter()-started,**stats)
            r['cases'].append(row);save(a.out/'report.json',r)
            print('CORRECTED',a.kind,case['label'],'qualified',row['qualified'],'stable',row['stable_complete_normal'],flush=True)
        r.update(result='waveform_original_operator_correction_known_measured',all_qualified=all(c['qualified'] for c in r['cases']),
            pass_count=sum(c['qualified'] for c in r['cases']),full_or_real_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json',r);print(r['result'],r['pass_count'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
