"""All54 frozen sets: full observer for216 counterfactuals plus signed terms."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','known','known-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from phase_input_paths_v1.replay import fields,generate
    from phase_input_paths_v1.factor import wave_terms,signed_budget,COUNTERFACTUALS
    from conditional_phase_time_v1.observer import analyze,summary,power_statistics
    from carrier_transfer_v1.spectral import measure,collapse
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',cases=[],sources={},inputs={})
    try:
        known=load(a.known/'report.json');ka=load(a.known_audit/'report.json')
        assert known['result']=='phase_input_known_ready' and ka['result']=='independent_phase_input_known_passed' and ka['cases']==9
        assert ka['producer_sha256']==sha(a.known/'report.json') and ka['auditor_sha256']==sha(repo/'tools/audit_phase_input_known_v1.py')
        assert ka['oracle_sha256']==sha(repo/'tools/phase_input_paths_v1/audit_oracle.py')
        for name,digest in known['sources'].items():assert sha(repo/name)==sha(a.known/'exact_sources'/name)==digest
        report.update(known_report_sha256=sha(a.known/'report.json'),known_audit_sha256=sha(a.known_audit/'report.json'))
        names=('research/phase_input_paths_v1_plan.json','tools/run_phase_input_real_v1.py','tools/phase_input_paths_v1/replay.py',
            'tools/phase_input_paths_v1/factor.py','tools/conditional_phase_time_v1/mapping.py','tools/radial_copula_v1/latent.py',
            'tools/radial_copula_v1/quantiles.py','tools/conditional_phase_time_v1/observer.py','tools/sound_dna/windowed.py',
            'tools/carrier_transfer_v1/groups.py','tools/carrier_transfer_v1/spectral.py')
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);report['sources'][name]=sha(dest)
        plan=load(repo/names[0]);gate=plan['checks']
        parent=a.workspace/'baselines/conditional_phase_time_v1';carrier=a.workspace/'baselines/carrier_transfer_v1'
        assert sha(parent/'manifest.json')==load(repo/'research/conditional_phase_time_v1_summary.json')['manifest_sha256']
        assert sha(carrier/'manifest.json')==load(repo/'research/carrier_transfer_v1_summary.json')['manifest_sha256']
        pe={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']};ce={r['path']:r['sha256'] for r in load(carrier/'manifest.json')['files']}
        def frozen(root,entries,name):
            path=root/name;digest=sha(path);assert digest==entries[name];report['inputs'][str(path)]=digest;return path
        old=load(frozen(parent,pe,'evidence/real1/report.json'))
        original=load(frozen(carrier,ce,'evidence/real1/report.json'))
        descriptors={(r['label'],s['seed'],v):d for r in original['cases'] for s in r['seeds'] for v,d in s['variants'].items()}
        for row in old['cases']:
            label,root=row['label'],row['root_hz'];folder=a.out/label;folder.mkdir()
            with np.load(frozen(parent,pe,f'evidence/real1/{label}/bundle.npz')) as z:bundle={k:z[k] for k in z.files}
            frozen(parent,pe,f'evidence/real1/{label}/source.npz')
            case=dict(label=label,root_hz=root,source_rows=row['source_rows'],seeds=[])
            for seed in row['seeds']:
                with np.load(frozen(parent,pe,f'evidence/real1/{label}/probe_{seed["seed"]}.npz')) as z:
                    capture={k:z[k] for k in ('state','independent_state','probe_positions','probe_amplitude','probe_common')}
                amplitude,common,uniform=fields(bundle,capture,plan['frames'],plan['block'])
                assert abs(amplitude[capture['probe_positions']]-capture['probe_amplitude']).max()<2e-12
                assert abs(common[capture['probe_positions']]-capture['probe_common']).max()<2e-12
                generated,diagnostics=generate(bundle,amplitude,common,uniform,root,plan['carrier_edges_Hz'],plan['decoders'])
                seed_row=dict(seed=seed['seed'],decoders={})
                if not report['cases'] and seed['seed']==plan['seeds'][0]:
                    fa,fc,fu=fields(bundle,capture,plan['frames'],plan['identity_block'])
                    paired,_=generate(bundle,fa,fc,fu,root,plan['carrier_edges_Hz'],plan['decoders'])
                    seed_row['chunk_errors_FS']={k:float(abs(paired[k]-generated[k]).max()) for k in plan['decoders']}
                    assert max(seed_row['chunk_errors_FS'].values())<gate['wave_identity_FS']
                    del fa,fc,fu,paired
                for name in plan['decoders']:
                    group=generated[name];counter=group.sum(axis=2);terms=wave_terms(counter)
                    identity=float(abs(terms.sum(axis=1)-counter[:,3]).max());assert identity<gate['wave_identity_FS']
                    desc=descriptors[label,seed['seed'],name]
                    with np.load(frozen(carrier,ce,f'evidence/real1/{label}/{desc["file"]}')) as z:
                        original_error=float(abs(group[:,3]-z['grouped_audio']).max())
                    assert original_error<gate['wave_identity_FS'],(label,name,original_error)
                    spectral=measure(terms,root,plan['bands_Hz'])
                    values=dict(grouped_counterfactual_audio=group,counterfactual_audio=counter,term_audio=terms,**diagnostics[name])
                    values.update({'term_'+k:v for k,v in spectral.items()})
                    for prefix in ('line','broad'):values.update({'term_'+prefix+'_'+k:v for k,v in signed_budget(spectral[prefix+'_Gram']).items()})
                    cf={}
                    for j,tag in enumerate(COUNTERFACTUALS):
                        observed=analyze(counter[:,j],288,root,plan['bands_Hz'])
                        values.update({tag+'_'+k:v for k,v in observed.items()})
                        for prefix in ('line','broad'):
                            power=observed['power' if prefix=='line' else 'broadband_power'];cross=observed['cross' if prefix=='line' else 'broadband_cross']
                            width=row['source_rows'];chunks=[power_statistics(power[t:t+width],cross[t:t+width]) for t in range(0,len(power)-width+1,width)]
                            for field in ('mean','CV','complex_coherence'):values[tag+'_chunks_'+prefix+'_'+field]=np.stack([c[field] for c in chunks])
                            if tag=='joint':
                                collapsed=collapse(spectral[prefix+'_Gram']);recovered=collapsed[:,:,[0,1],[0,1]].real.reshape(241,8)
                                scale=np.maximum(power.reshape(241,4,2).mean(axis=(0,2)),1e-24)
                                assert (abs(recovered-power).reshape(241,4,2)/scale[None,:,None]).max()<gate['Gram_per_band_scaled']
                        cf[tag]=summary(observed)
                    path=folder/f'{name}_{seed["seed"]}.npz';np.savez_compressed(path,**values)
                    seed_row['decoders'][name]=dict(file=path.name,sha256=sha(path),original_joint_error_FS=original_error,
                        wave_identity_FS=identity,statistics=cf,observer_rows_per_counterfactual=241)
                    print('GENERATED input paths',label,seed['seed'],name,flush=True)
                case['seeds'].append(seed_row)
                del amplitude,common,uniform,generated
            report['cases'].append(case);save(a.out/'report.json',report)
        assert len(report['cases'])==6
        report.update(result='phase_input_all54_sets_ready',counterfactuals=216,new_random_draws=False,normalized_coordinate_only=True,native48k_or_C_or_listening=False)
        save(a.out/'report.json',report);print(report['result'],flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
