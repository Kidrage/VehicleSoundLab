"""Known-first floating primal/dual bounds, without reading material sources."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','known','known-audit','out'): p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_frequency_v1.metric import FrequencyMetric
    from observer_frequency_v1.fit import WeightedSystem
    from observer_frequency_v1.optimality import bound
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],sources={},inputs={},material_read=False)
    try:
        known,audit=load(a.known/'report.json'),load(a.known_audit/'report.json')
        assert known['result']=='observer_frequency_correction_known_ready'
        assert audit['result']=='independent_observer_frequency_correction_known_passed'
        assert audit['producer_sha256']==sha(a.known/'report.json')
        for path in (a.known/'report.json',a.known_audit/'report.json'):r['inputs'][str(path)]=sha(path)
        names=tuple(known['sources'])+('tools/observer_frequency_v1/optimality.py',
            'tools/run_observer_frequency_optimality_known_v1.py','research/observer_frequency_optimality_v1_plan.json')
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        rng=np.random.default_rng(29115)
        for case in known['cases']:
            path=a.known/case['file'];assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as z:
                audio,positions,orders,scale=z['audio'],z['positions'],z['orders'],z['scale']
                synth=WaveSynthesis(len(audio),positions,orders,audio.shape[1])
                met=FrequencyMetric(audio,64.);system=WeightedSystem(synth,scale,met)
                choices={'initial':z['initial_nodes'],'corrected':z['nodes']}
                if audio.shape[1]==1:
                    choices['perturbed']=z['nodes']+(.1*rng.normal(size=z['nodes'].shape)+.1j*rng.normal(size=z['nodes'].shape))*scale[None]
                for tag,nodes in choices.items():
                    result=bound(system,audio,nodes)
                    if tag=='corrected':assert result['additional_gap_gate_passed']
                    if tag in ('initial','perturbed'):assert not result['additional_gap_gate_passed']
                    name=case['label']+'_'+tag;dest=a.out/(name+'.npz')
                    np.savez_compressed(dest,audio=audio,positions=positions,orders=orders,scale=scale,nodes=nodes,weights=met.weights)
                    r['cases'].append(dict(label=name,file=dest.name,sha256=sha(dest),certificate=result))
        zero=np.zeros_like(audio);zero_nodes=np.zeros_like(nodes)
        met=FrequencyMetric(zero,64.);system=WeightedSystem(synth,scale,met);result=bound(system,zero,zero_nodes)
        assert result['gap_upper_bound']==result['primal']==result['dual_lower_bound']==0
        dest=a.out/'silence.npz';np.savez_compressed(dest,audio=zero,positions=positions,orders=orders,scale=scale,nodes=zero_nodes,weights=met.weights)
        r['cases'].append(dict(label='silence',file=dest.name,sha256=sha(dest),certificate=result))
        r.update(result='observer_frequency_optimality_known_ready')
        save(a.out/'report.json',r);print(r['result'],len(r['cases']),flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
