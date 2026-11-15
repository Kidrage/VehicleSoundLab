"""Known-only five stereo fixtures: diagonal root equilibration feasibility.

This probe is not a production backend or a replacement qualification suite.
All original gates remain unchanged; original normal uses original operators.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load,save,sha


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
    from observer_representer_v1.primal import PenaltyPrimal
    from observer_representer_v1.dual import representer_certificate
    from observer_frequency_v1.optimality import bound
    from observer_inverse_v1.fit import complex_array
    from waveform_stream_v1.shared import SharedSupportedGeometry
    from waveform_stream_v1.solver import solve
    from waveform_banded_v1.metric import supported_banded,BandedMetric
    from waveform_banded_v1.equilibrated import EquilibratedRoot
    from waveform_structured_v1.resources import ArrayLedger
    from waveform_structured_v1.penalty import TemporalPenalty
    a.out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    shutil.copy2(__file__,a.out/'executed_probe.py')
    source,audit=[load(path/'report.json') for path in (a.study,a.audit)]
    assert source['backend']=='banded' and audit['pass_count']==7
    r=dict(result='running',cases=[],sources={},inputs={str(path/'report.json'):sha(path/'report.json') for path in (a.study,a.audit)})
    for name in set(source['sources'])|{'tools/waveform_banded_v1/equilibrated.py','tools/probe_waveform_banded_equilibration_v1.py'}:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
    class ExperimentalMetric(BandedMetric):
        def factor(self,ledger):
            if self.consumed:raise ValueError('Already consumed')
            ledger.add('wave_metric.input',self.bands)
            root=EquilibratedRoot(self.bands,ledger);self.consumed=True
            return root
    try:
        for case in source['cases']:
            if case['kind']!='Hann':continue
            path=a.study/case['file'];assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as z:
                audio,positions,orders,scale=(z[n] for n in ('audio','positions','orders','scale'))
                original=z['original'];A=z['original_A'];rhs=z['original_rhs']
            assert len(audio)==4353 and len(positions)==9 and len(orders)==5
            synthesis=WaveSynthesis(len(audio),positions,orders,2)
            metric=SupportedMetric(audio,64.);system=SupportedSystem(synthesis,scale,metric)
            shared=SharedSupportedGeometry(system);band=supported_banded(metric)
            experimental=ExperimentalMetric(band.bands);ledger=ArrayLedger()
            values,info=solve(shared.forward,shared.adjoint,shared.prior,experimental,audio,ledger,block=32)
            q=values['q'].ravel();fitted=complex_array(q,system.nshape)*system.scale[None]
            residual=system@q-system.rhs(audio);u=-residual[:system.ysize]
            gradient=float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(rhs)),1e-300))
            relative=float(np.linalg.norm(q-original)/max(np.linalg.norm(original),1e-300))
            rc,pc=bound(system,audio,fitted),representer_certificate(system,audio,fitted,u)
            primal=PenaltyPrimal(system)
            full_prior=TemporalPenalty(system.nshape,system.D.toarray(),system.alpha,system.beta)
            assert np.array_equal(full_prior.L,primal.prior.L)
            packed=full_prior.root_transpose(q)
            full_rhs=np.r_[rhs[:system.ysize],np.zeros(system.nsize)]
            model=np.r_[system.rhs(values['wave_model_residual'])[:system.ysize],packed]
            normal=primal.rmatvec(model)
            # Dense only in this fixed known probe: original full operator norm,
            # independently of the new Cholesky/QR root's reported norm.
            Gdata=A[:system.ysize]@full_prior.inverse_transpose(np.eye(system.nsize))
            frobenius=np.sqrt(np.sum(Gdata**2)+system.nsize)
            stable=float(np.linalg.norm(normal)/max(frobenius*np.linalg.norm(model),1e-300))
            backward=float(np.linalg.norm(primal@packed-full_rhs-model)/max(np.linalg.norm(full_rhs),1e-300))
            qualified=bool(relative<2e-7 and gradient<2e-7 and stable<=1e-11 and backward<=1e-11
                and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed'] and info['stable_root_guard_passed'])
            dest=a.out/(case['label']+'.npz')
            np.savez_compressed(dest,q_interleaved=q,original_model_residual=model,original_model_normal=normal,**values)
            r['cases'].append(dict(label=case['label'],file=dest.name,sha256=sha(dest),dense_relative_error=relative,
                gradient=gradient,stable_complete_normal=stable,backward=backward,
                previous_stable_complete_normal=case['stable_complete_normal'],qualified=qualified,
                residual_certificate=rc,representer_certificate=pc,solver=info,resources=ledger.report()))
            save(a.out/'report.json',r);print('EQUILIBRATION',case['label'],stable,'qualified',qualified,flush=True)
        assert len(r['cases'])==5
        r.update(result='waveform_banded_equilibration_known_probe_measured',pass_count=sum(c['qualified'] for c in r['cases']),
            full_original12_and_controls_NOT_requalified=True,production_backend_selected=False,
            full_or_real_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
