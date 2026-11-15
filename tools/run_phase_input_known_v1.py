"""Known-first P/uniform path and signed waveform-interference controls."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from phase_input_paths_v1.factor import phases,wave_terms,signed_budget
    from phase_input_paths_v1.fixtures import cases
    from carrier_transfer_v1.spectral import measure
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',sources={},cases=[])
    try:
        names=('research/phase_input_paths_v1_plan.json','tools/run_phase_input_known_v1.py',
            'tools/phase_input_paths_v1/factor.py','tools/phase_input_paths_v1/fixtures.py',
            'tools/conditional_phase_time_v1/mapping.py','tools/carrier_transfer_v1/spectral.py')
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);report['sources'][name]=sha(dest)
        plan=load(repo/names[0]);n=np.arange(8192)
        common=.17*np.sin(2*np.pi*n/5000)
        amplitude=np.column_stack([1+.1*np.sin(n/400),.7+.08*np.cos(n/600)])
        for name,values in cases():
            delta=phases(**values)
            counter=np.zeros((len(n),4,2))
            # All four observed bands have genuine carriers; avoid judging
            # FFT relative accuracy solely against ~1e-17 leakage powers.
            for order,weight in ((70,.7),(110,.5),(140,.4),(190,.3)):
                carrier=2*np.pi*n/1024*order
                angle=carrier[:,None,None]+common[:,None,None]+delta[:,:,None]*np.array([.5,-.5])
                counter+=weight*amplitude[:,None,:]*np.cos(angle)
            terms=wave_terms(counter);error=float(abs(terms.sum(axis=1)-counter[:,3]).max())
            assert error<2e-12
            if name in ('constant_atom','no_P_dependence','fixed_product'):assert abs(terms[:,[1,3]]).max()<2e-12
            if name in ('constant_atom','fixed_uniform'):assert abs(terms[:,[2,3]]).max()<2e-12
            spectral=measure(terms,64.,plan['bands_Hz'])
            arrays=dict(**values,delta=delta,counterfactual_audio=counter,term_audio=terms,**spectral)
            for prefix in ('line','broad'):arrays.update({prefix+'_'+k:v for k,v in signed_budget(spectral[prefix+'_Gram']).items()})
            path=a.out/(name+'.npz');np.savez_compressed(path,**arrays)
            report['cases'].append(dict(name=name,file=path.name,sha256=sha(path),wave_identity_FS=error))
        # Exact cancellation fixture forbids treating self powers as total power.
        b=np.zeros_like(amplitude)
        for order,weight in ((70,.7),(110,.5),(140,.4),(190,.3)):
            b+=weight*amplitude*np.cos((2*np.pi*n/1024*order)[:,None]+np.array([0.,.3]))
        terms=np.stack([b,-b,.3*b,.2*b],axis=1)
        spectral=measure(terms,64.,plan['bands_Hz']);path=a.out/'cancellation.npz'
        np.savez_compressed(path,term_audio=terms,**spectral)
        report['cancellation']=dict(file=path.name,sha256=sha(path))
        report['result']='phase_input_known_ready';save(a.out/'report.json',report);print(report['result'],flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
