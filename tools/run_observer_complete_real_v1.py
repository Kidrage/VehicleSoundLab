"""All6 frozen sources under one declared complete-record inference objective."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','known','known-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_complete_v1.frame import CompleteHann
    from observer_complete_v1.fit import infer,CompleteSystem
    from observer_inverse_v1.fit import real_vector
    from observer_inverse_v1.diagnostics import capture
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',pid=os.getpid(),cases=[],sources={},inputs={},in_sample_only=True)
    print('COMPLETE_SOURCE_PID',os.getpid(),flush=True)
    try:
        known=load(a.known/'report.json');audit=load(a.known_audit/'report.json')
        assert known['result']=='observer_complete_known_ready' and audit['result']=='independent_observer_complete_known_passed'
        assert audit['producer_sha256']==sha(a.known/'report.json') and audit['auditor_sha256']==sha(repo/'tools/audit_observer_complete_known_v1.py')
        for name,digest in known['sources'].items():assert sha(repo/name)==sha(a.known/'exact_sources'/name)==digest
        names=('research/observer_complete_v1_plan.json','tools/run_observer_complete_real_v1.py',
            'tools/observer_complete_v1/frame.py','tools/observer_complete_v1/synthesis.py','tools/observer_complete_v1/fit.py',
            'tools/observer_forward_v1/operator.py','tools/observer_forward_v1/polyphase.py',
            'tools/observer_inverse_v1/fit.py','tools/observer_inverse_v1/regularizer.py','tools/observer_inverse_v1/refinement.py',
            'tools/observer_inverse_v1/diagnostics.py','tools/conditional_phase_time_v1/observer.py',
            'tools/carrier_transfer_v1/spectral.py','tools/carrier_transfer_v1/groups.py','tools/sound_dna/windowed.py')
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        def consume(path):r['inputs'][str(path)]=sha(path);return path
        for path in (a.known/'report.json',a.known_audit/'report.json'):consume(path)
        parent=a.workspace/'baselines/observer_inverse_v1'
        assert sha(parent/'manifest.json')==load(repo/'research/observer_inverse_v1_summary.json')['manifest_sha256']
        entries={row['path']:row['sha256'] for row in load(parent/'manifest.json')['files']}
        def frozen(name):
            path=parent/name;assert sha(path)==entries[name];return consume(path)
        old={n:load(frozen(f'evidence/{n}/report.json')) for n in ('real1','real2','real3')}
        bands,edges=old['real2']['bands'],old['real2']['carrier_edges']
        r.update(parent_manifest_sha256=sha(parent/'manifest.json'),bands=bands,carrier_edges=edges,
            known_sha256=sha(a.known/'report.json'),known_audit_sha256=sha(a.known_audit/'report.json'))
        save(a.out/'report.json',r)
        for j,case in enumerate(old['real2']['cases']):
            label=case['label'];folder=a.out/label;folder.mkdir()
            for name in ('source.npz','scale.npz'):
                shutil.copy2(frozen(f'evidence/real2/{label}/{name}'),folder/name)
            with np.load(folder/'source.npz') as z:audio,target,positions=z['audio'],z['coefficients'],z['positions']
            with np.load(folder/'scale.npz') as z:scale=z['scale']
            sigma=float(np.sqrt(np.mean(audio**2)));assert sigma>1e-24
            synthesis=WaveSynthesis(len(audio),positions,np.arange(1,289))
            system=CompleteSystem(synthesis,scale,sigma);frame=CompleteHann(len(audio))
            row=dict(label=label,root_hz=case['root_hz'],frames=len(audio),source_rows=len(target),
                source_sha256=sha(folder/'source.npz'),scale_sha256=sha(folder/'scale.npz'),
                floored_orders=case['floored_orders'],wave_scale=sigma,variants={})
            for tag,attempt,key in (('interpolated','real1','interpolated_observations'),
                                     ('old_original4000','real1','inverse'),('old_corrected','real3','inverse')):
                previous=old[attempt]['cases'][j];assert previous['label']==label
                desc=previous['variants'][key]
                path=frozen(f'evidence/{attempt}/{label}/'+desc['file'])
                assert sha(path)==desc['sha256'];dest=folder/(tag+'.npz');shutil.copy2(path,dest)
                with np.load(dest) as z:
                    latent=z['nodes'];vector=real_vector(latent/scale[None]);res=system@vector-system.rhs(audio)
                    objective=float(res@res)
                row['variants'][tag]=dict(file=dest.name,sha256=sha(dest),new_objective=objective)
            print('COMPLETE FIT START',label,flush=True)
            nodes,info,right=infer(synthesis,audio,scale,sigma)
            np.savez_compressed(folder/'right.npz',time=right.time,real_scale=right.real_scale,imag_scale=right.imag_scale)
            values=capture(synthesis,nodes,case['root_hz'],bands,edges,audio,target)
            residual=values['audio']-audio;spec=frame.forward(residual)
            waveform_energy=float(np.sum(residual**2));frame_energy=float(np.sum(abs(spec)**2))
            assert abs(frame_energy-waveform_energy)<2e-10*max(waveform_energy,1e-24)
            values.update(complete_coverage=frame.coverage,complete_starts=frame.starts,
                complete_wave_error_energy=waveform_energy,complete_frame_error_energy=frame_energy)
            path=folder/'complete.npz';np.savez_compressed(path,**values)
            row['variants']['complete']=dict(file=path.name,sha256=sha(path),new_objective=info['objective'])
            assert info['objective']<=row['variants']['interpolated']['new_objective']*(1+1e-10)
            row.update(solve=info,right_sha256=sha(folder/'right.npz'))
            r['cases'].append(row);save(a.out/'report.json',r)
            print('COMPLETE FIT DONE',label,info['stop'],info['iterations'],info['relative_stationarity'],float(values['wave_NRMSE']),flush=True)
        r.update(result='observer_complete_all6_measured',all_converged=all(c['solve']['converged'] for c in r['cases']),
            new_stochastic_source=False,real_RPM_or_native48k_or_runtime_C_or_hearing=False)
        save(a.out/'report.json',r);print(r['result'],'all_converged',r['all_converged'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
