"""Evaluate only saved states on all6 sources; never call a solver."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','known','known-audit','study','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--follow-pid',type=int)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.follow import Follow
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_frequency_v1.metric import FrequencyMetric
    from observer_frequency_v1.fit import WeightedSystem
    from observer_frequency_v1.optimality import bound
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',pid=os.getpid(),cases=[],sources={},inputs={},no_solver_calls=True)
    follow=Follow(a.study/'report.json',a.follow_pid)
    try:
        known,audit=load(a.known/'report.json'),load(a.known_audit/'report.json')
        assert known['result']=='observer_frequency_optimality_known_ready'
        assert audit['result']=='independent_observer_frequency_optimality_known_passed'
        assert audit['producer_sha256']==sha(a.known/'report.json') and audit['auditor_sha256']==sha(repo/'tools/audit_observer_frequency_optimality_known_v1.py')
        names=tuple(known['sources'])+('tools/run_observer_frequency_optimality_real_v1.py','tools/observer_complete_v1/follow.py')
        for n in names:
            dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/n,dest);r['sources'][n]=sha(dest)
        for path in (a.known/'report.json',a.known_audit/'report.json'):r['inputs'][str(path)]=sha(path)
        for i in range(6):
            producer,case=follow.case(i);folder=a.study/case['label']
            with np.load(folder/'source.npz') as z:audio,positions=z['audio'],z['positions']
            with np.load(folder/'scale.npz') as z:scale=z['scale']
            synth=WaveSynthesis(len(audio),positions,np.arange(1,289));met=FrequencyMetric(audio,case['root_hz'])
            with np.load(folder/'metric.npz') as z:assert np.array_equal(met.weights,z['weights'])
            system=WeightedSystem(synth,scale,met);row=dict(label=case['label'],root_hz=case['root_hz'],variants={})
            for n in ('source.npz','scale.npz','metric.npz'):r['inputs'][str(folder/n)]=sha(folder/n)
            for tag,n in (('initial','initial.npz'),('block_refined',case['file'])):
                path=folder/n;r['inputs'][str(path)]=sha(path)
                with np.load(path) as z:result=bound(system,audio,z['nodes'])
                row['variants'][tag]=dict(path=str(path),sha256=sha(path),certificate=result)
                print('OPTIMALITY',case['label'],tag,'gap',result['relative_gap_upper_bound'],'pass',result['additional_gap_gate_passed'],flush=True)
            r['cases'].append(row);save(a.out/'report.json',r)
        producer=follow.read();assert producer['result']=='observer_frequency_correction_all6_measured'
        r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
        r.update(result='observer_frequency_optimality_all6_measured',gap_passed={tag:sum(c['variants'][tag]['certificate']['additional_gap_gate_passed'] for c in r['cases']) for tag in ('initial','block_refined')},original_convergence_unchanged=producer['all_converged'])
        save(a.out/'report.json',r);print(r['result'],r['gap_passed'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise
    finally:follow.close()


if __name__=='__main__':main()
