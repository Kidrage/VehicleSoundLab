"""One original-marginal stream control on every saved frozen dual-state path."""
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
    from phase_stream_control_v1.replay import generate
    from conditional_phase_time_v1.observer import analyze,summary,power_statistics
    from carrier_transfer_v1.spectral import measure,summary as signed_summary,collapse
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',cases=[],sources={},inputs={})
    try:
        known=load(a.known/'report.json');ka=load(a.known_audit/'report.json')
        assert known['result']=='phase_stream_known_ready' and ka['result']=='independent_phase_stream_known_passed'
        assert ka['producer_sha256']==sha(a.known/'report.json') and ka['cases']==8
        assert ka['auditor_sha256']==sha(repo/'tools/audit_phase_stream_known_v1.py')
        for name,digest in known['sources'].items():assert sha(repo/name)==sha(a.known/'exact_sources'/name)==digest
        report['known_report_sha256']=sha(a.known/'report.json');report['known_audit_sha256']=sha(a.known_audit/'report.json')
        names=['research/phase_stream_control_v1_plan.json','tools/run_phase_stream_real_v1.py',
            'tools/phase_stream_control_v1/replay.py','tools/radial_copula_v1/latent.py',
            'tools/radial_copula_v1/quantiles.py','tools/conditional_phase_time_v1/observer.py',
            'tools/sound_dna/windowed.py','tools/carrier_transfer_v1/groups.py','tools/carrier_transfer_v1/spectral.py']
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);report['sources'][name]=sha(dest)
        plan=load(repo/names[0]);gate=plan['checks']
        parent=a.workspace/'baselines/conditional_phase_time_v1'
        assert sha(parent/'manifest.json')==load(repo/'research/conditional_phase_time_v1_summary.json')['manifest_sha256']
        entries={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
        def frozen(name):
            path=parent/name;digest=sha(path);assert digest==entries[name]
            report['inputs'][str(path)]=digest;return path
        old=load(frozen('evidence/real1/report.json'))
        for case in old['cases']:
            label,root=case['label'],case['root_hz'];folder=a.out/label;folder.mkdir()
            with np.load(frozen(f'evidence/real1/{label}/bundle.npz')) as z:bundle={k:z[k] for k in z.files}
            frozen(f'evidence/real1/{label}/source.npz')
            row=dict(label=label,root_hz=root,source_rows=case['source_rows'],seeds=[])
            for seed in case['seeds']:
                with np.load(frozen(f'evidence/real1/{label}/probe_{seed["seed"]}.npz')) as z:
                    capture={key:z[key] for key in ('state','independent_state','probe_positions','relative_audio','probe_amplitude','probe_common')}
                group,diagnostic,old_error,partition=generate(bundle,capture,root,plan['carrier_edges_Hz'],plan['frames'],plan['block'])
                assert old_error<gate['original_probe_FS'] and partition<gate['original_probe_FS']
                assert abs(diagnostic['probe_amplitude']-capture['probe_amplitude']).max()<gate['known_phase_radians']
                assert abs(diagnostic['probe_common']-capture['probe_common']).max()<gate['known_phase_radians']
                extra={}
                if not report['cases'] and seed['seed']==plan['seeds'][0]:
                    paired,_,_,_=generate(bundle,capture,root,plan['carrier_edges_Hz'],plan['frames'],plan['identity_block'])
                    extra['chunk_error_FS']=float(abs(paired-group).max());assert extra['chunk_error_FS']<gate['chunk_identity_FS']
                    del paired
                observed=analyze(group.sum(axis=1),288,root,plan['bands_Hz'])
                spectral=measure(group,root,plan['bands_Hz'])
                values=dict(audio=group.sum(axis=1),grouped_audio=group,**observed,**spectral,**diagnostic)
                for prefix in ('line','broad'):
                    values.update({prefix+'_group_'+k:v for k,v in signed_summary(spectral[prefix+'_Gram']).items()})
                    power=observed['power' if prefix=='line' else 'broadband_power']
                    cross=observed['cross' if prefix=='line' else 'broadband_cross']
                    matrix=collapse(spectral[prefix+'_Gram'])
                    recovered=matrix[:,:,[0,1],[0,1]].real.reshape(241,8)
                    scale=np.maximum(power.reshape(241,4,2).mean(axis=(0,2)),1e-24)
                    assert (abs(recovered-power).reshape(241,4,2)/scale[None,:,None]).max()<gate['Gram_per_band_scaled']
                    count=case['source_rows']
                    chunks=[power_statistics(power[j:j+count],cross[j:j+count]) for j in range(0,len(power)-count+1,count)]
                    for field in ('mean','CV','complex_coherence'):values['chunks_'+prefix+'_'+field]=np.stack([c[field] for c in chunks])
                path=folder/f'independent_marginal_{seed["seed"]}.npz';np.savez_compressed(path,**values)
                row['seeds'].append(dict(seed=seed['seed'],file=path.name,sha256=sha(path),observed_rows=241,
                    original_probe_error_FS=old_error,partition_error_FS=partition,statistics=summary(observed),**extra))
                print('GENERATED independent original marginal',label,seed['seed'],flush=True)
            report['cases'].append(row);save(a.out/'report.json',report)
        assert len(report['cases'])==6 and sum(len(r['seeds']) for r in report['cases'])==18
        report.update(result='phase_stream_all18_ready',no_new_random_draws=True,normalized_coordinate_only=True,
            native48k_or_C_or_listening=False);save(a.out/'report.json',report);print(report['result'],flush=True)
    except BaseException as e:
        report.update(result='failed',error=repr(e));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
