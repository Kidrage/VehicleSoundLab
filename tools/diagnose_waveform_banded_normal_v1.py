"""Separate original FFT metric, stored Gram and native-root normal actions.

Known stereo fixtures only. Component norms are a numerical diagnosis, not a
physical explanation of electronic timbre or a claim of a sole error source.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem
    from waveform_stream_v1.shared import SharedSupportedGeometry
    from waveform_banded_v1.metric import supported_banded
    from waveform_structured_v1.resources import ArrayLedger
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_diagnosis.py')
    r=dict(result='running',cases=[],inputs={},sources={})
    source,audit=[load(path/'report.json') for path in (a.study,a.audit)]
    assert source['backend']=='banded' and audit['pass_count']==7
    for path in (a.study/'report.json',a.audit/'report.json'):r['inputs'][str(path)]=sha(path)
    names={n for n in source['sources'] if n.endswith('.py')}
    for name in names:
        assert sha(repo/name)==source['sources'][name]
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
    try:
        for case in source['cases']:
            if case['kind']!='Hann':continue
            path=a.study/case['file'];assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as z:
                audio,positions,orders,scale=(z[n] for n in ('audio','positions','orders','scale'))
                wave=z['wave_model_residual'];packed=z['z'];model=z['root_model_residual']
                complete_model=z['original_model_residual'];producer_normal=z['stable_root_normal']
            synthesis=WaveSynthesis(len(audio),positions,orders,2)
            metric=SupportedMetric(audio,64.);system=SupportedSystem(synthesis,scale,metric)
            shared=SharedSupportedGeometry(system);band=supported_banded(metric)
            stored_action=band@wave;root=band.factor(ArrayLedger())
            exact_action=wave/metric.wave_scale**2+metric.adjoint(metric.forward(wave))
            root_action=root.apply(root.transpose(wave))
            model_action=root.apply(model)
            def normal(action):
                return np.column_stack([shared.prior.inverse(shared.adjoint(c)) for c in action.T])+packed
            gs={tag:normal(action) for tag,action in (
                ('original_FFT',exact_action),('stored_Gram',stored_action),
                ('factored_Gram',root_action),('root_model',model_action))}
            denominator=np.sqrt(2)*case['solver']['augmented_root_Frobenius']*np.linalg.norm(complete_model)
            denominator=max(denominator,1e-300)
            normalized={tag:float(np.linalg.norm(value)/denominator) for tag,value in gs.items()}
            deltas={name:gs[left]-gs[right] for name,left,right in (
                ('FFT_minus_stored','original_FFT','stored_Gram'),
                ('stored_minus_factored','stored_Gram','factored_Gram'),
                ('factored_minus_model','factored_Gram','root_model'))}
            assert np.max(abs(sum(deltas.values())-(gs['original_FFT']-gs['root_model'])))<1e-12
            producer_difference=float(np.linalg.norm(gs['root_model']-producer_normal)/denominator)
            assert producer_difference<1e-11
            dest=a.out/(case['label']+'.npz')
            np.savez_compressed(dest,denominator=denominator,producer_normal=producer_normal,**gs,**deltas)
            r['cases'].append(dict(label=case['label'],file=dest.name,sha256=sha(dest),
                original_qualified=case['qualified'],normalized_normal_actions=normalized,
                normalized_vector_differences={n:float(np.linalg.norm(v)/denominator) for n,v in deltas.items()},
                root_model_vs_producer_difference=producer_difference,
                decomposition_is_vector_identity_not_sum_of_norms=True))
            save(a.out/'report.json',r);print('NORMAL COMPONENTS',case['label'],normalized,flush=True)
        assert len(r['cases'])==5
        r.update(result='waveform_banded_complete_normal_components_diagnosed',
            original_gate_unchanged=1e-11,shared_qualification_still=7,
            sole_cause_or_physical_timbre_cause_established=False,no_refined_solution_or_source_or_C=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
