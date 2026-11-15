"""Known interleaved stereo objectives versus one geometry with two RHS."""
import argparse
import copy
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','prerequisite','original','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_representer_v1.fixtures import DenseFixture
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem
    from observer_representer_v1.primal import PenaltyPrimal
    from observer_representer_v1.dual import representer_certificate
    from observer_frequency_v1.optimality import bound
    from observer_inverse_v1.fit import real_vector, complex_array
    from waveform_structured_v1.penalty import TemporalPenalty
    from waveform_structured_v1.resources import ArrayLedger, process_memory
    from waveform_stream_v1.shared import SharedSupportedGeometry
    from waveform_stream_v1.solver import solve
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    prerequisite=load(a.prerequisite/'report.json')
    assert prerequisite['all_qualified'] and prerequisite['pass_count']==12
    parent=load(a.original/'primal_algebra1/report.json')
    names=set(parent['sources'])
    names.update(('tools/run_waveform_shared_known_v1.py','research/waveform_stream_known_v1_plan.json',
        'tools/run_waveform_structured_known_v1.py','tools/waveform_representer_v1/metric.py'))
    for folder in ('waveform_stream_v1','waveform_structured_v1','observer_supported_v1','observer_complete_v1','observer_forward_v1'):
        names.update(f.relative_to(repo).as_posix() for f in (repo/'tools'/folder).glob('*.py'))
    r=dict(result='running',pid=os.getpid(),cases=[],rejections=[],sources={},inputs={},material_read=False)
    try:
        for path in (a.prerequisite/'report.json',a.original/'primal_algebra1/report.json'):
            r['inputs'][str(path)]=sha(path)
        for name in sorted(names):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)

        def run_case(label,kind,system,audio,reference=None,original_file=None):
            C=audio.shape[1];M,H,_=system.nshape
            ledger=ArrayLedger()
            if kind=='algebra':
                prior=TemporalPenalty((M,H,1),system.D.toarray(),system.alpha,system.beta)
                single=system.Phi[::C,::C].copy()
                forward=lambda x:single@x;adjoint=lambda x:single.T@x
                W=np.array(system.wave_metric[::C,::C],order='F')
            else:
                shared=SharedSupportedGeometry(system)
                prior=shared.prior;forward=shared.forward;adjoint=shared.adjoint;W=shared.metric_matrix()
            values,info=solve(forward,adjoint,prior,W,audio,ledger,block=32)
            q=values['q'].ravel();fitted=complex_array(q,system.nshape)*system.scale[None]
            # Original complete interleaved matrix is a SMALL known oracle,
            # never used by the producer solve or by a future full fit.
            A=np.column_stack([system@e for e in np.eye(system.nsize)])
            rhs=system.rhs(audio)
            if reference is None:reference=linalg.lstsq(A,rhs,lapack_driver='gelsd')[0]
            residual=system@q-rhs;u=-residual[:system.ysize]
            gradient=float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(rhs)),1e-300))
            relative=float(np.linalg.norm(q-reference)/max(np.linalg.norm(reference),1e-300))
            rc=bound(system,audio,fitted);pc=representer_certificate(system,audio,fitted,u)
            primal=PenaltyPrimal(system)
            z=TemporalPenalty(system.nshape,system.D.toarray(),system.alpha,system.beta).root_transpose(q)
            full_rhs=np.r_[rhs[:system.ysize],np.zeros(system.nsize)]
            model=np.r_[system.rhs(values['wave_model_residual'])[:system.ysize],z]
            normal=primal.rmatvec(model)
            normA=float(np.sqrt(C)*info['augmented_root_Frobenius'])
            stable=float(np.linalg.norm(normal)/max(normA*np.linalg.norm(model),1e-300))
            backward=float(np.linalg.norm(primal@z-full_rhs-model)/max(np.linalg.norm(full_rhs),1e-300))
            qualified=bool(relative<2e-7 and gradient<2e-7 and stable<=1e-11 and backward<=1e-11
                and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed'] and info['stable_root_guard_passed'])
            path=a.out/(kind+'_'+label+'.npz')
            np.savez_compressed(path,audio=audio,positions=system.positions if kind=='algebra' else system.synthesis.positions,
                orders=system.orders if kind=='algebra' else system.synthesis.orders,scale=system.scale,
                D=system.D.toarray(),original=reference,original_A=A,original_rhs=rhs,
                original_model_residual=model,original_model_normal=normal,u=u,**values)
            ledger.snapshot('caller.after_serialization')
            row=dict(label=label,kind=kind,file=path.name,sha256=sha(path),original_file=original_file,
                dense_relative_error=relative,original_gradient=gradient,stable_complete_normal=stable,
                original_backward=backward,residual_certificate=rc,representer_certificate=pc,
                solver=info,qualified=qualified,resources=ledger.report(),process_memory=process_memory())
            r['cases'].append(row);save(a.out/'report.json',r)
            print('SHARED',kind,label,'qualified',qualified,'normal',stable,'LR',[float(np.linalg.norm(v)) for v in audio.T],flush=True)
            return values

        for case in parent['cases']:
            if case['channels']!=2:continue
            path=a.original/'primal_algebra1'/case['file'];assert sha(path)==case['sha256']
            r['inputs'][str(path)]=sha(path)
            system=DenseFixture(2,case['weak'],case['silent_right'])
            with np.load(path) as old:
                assert np.array_equal(system.audio,old['audio']) and np.array_equal(system.A,old['A'])
                run_case(case['label'],'algebra',system,system.audio,old['original'],str(path))
        rng=np.random.default_rng(650923)
        N=4353;positions=np.linspace(0,N-1,9);orders=np.array([1,8,75,187,287]);scale=np.array([1.,.7,.3,.15,.05])[:,None]
        synthesis=WaveSynthesis(N,positions,orders,2)
        truth=rng.normal(size=synthesis.shape)+1j*rng.normal(size=synthesis.shape)
        base=synthesis.synthesize(truth*scale[None])+rng.normal(size=(N,2))*.00001
        for label in ('unequal_LR','silent_right','delayed_right','right_dominant','both_zero'):
            audio=base.copy()
            if label=='silent_right':audio[:,1]=0
            if label=='delayed_right':audio[:,1]=np.r_[np.zeros(37),audio[:-37,1]]*.4
            if label=='right_dominant':audio[:,0]*=.001
            if label=='both_zero':audio[:]=0
            metric=SupportedMetric(audio,64.);system=SupportedSystem(synthesis,scale,metric)
            run_case(label,'Hann',system,audio)
            if label=='unequal_LR':
                bads=[]
                for field in ('weights','wave_scale','amplitude_scale','root_hz','keep'):
                    bad=copy.deepcopy(metric)
                    if field=='weights':bad.weights[123]*=1.01
                    elif field=='keep':bad.keep[0]=not bad.keep[0]
                    else:setattr(bad,field,getattr(bad,field)*1.01)
                    bads.append((field,dict(channel_metrics=[metric,bad])))
                bads.append(('separately_refit_side_metrics',dict(channel_metrics=[SupportedMetric(audio[:,:1],64.),SupportedMetric(audio[:,1:],64.)])))
                bads.append(('source_scale',dict(channel_scales=[scale,scale*1.01])))
                for name,kwargs in bads:
                    try:SharedSupportedGeometry(system,**kwargs)
                    except ValueError as error:r['rejections'].append(dict(label=name,rejected=True,error=str(error)))
                    else:raise AssertionError('Mismatched operator accepted: '+name)
        assert len(r['cases'])==8 and len(r['rejections'])==7
        r.update(result='waveform_shared_known_measured',all_qualified=all(c['qualified'] for c in r['cases']),
            no_target_or_node_averaging=True,full_or_real_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json',r)
        print(r['result'],r['all_qualified'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
