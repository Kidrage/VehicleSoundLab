"""Publish the entire frozen comparison plus each saved-solution correction."""
import numpy as np
from research_archive_v1 import load, sha
from conditional_phase_time_v1.observer import power_statistics
from observer_complete_v1.metrics import ERRORS

VARIANTS=('interpolated','old_original4000','old_corrected','complete','weighted','block_refined')


def collect(original_review,study):
    old=load(original_review/'report.json');verification=load(original_review/'metrics_verification.json')
    assert old['result']=='observer_frequency_review_ready'
    assert verification['result']=='independent_observer_frequency_publication_passed'
    rows=load(original_review/'figure_inputs.json')
    assert sha(original_review/'figure_inputs.json')==old['figure_inputs_sha256']
    inputs={str(original_review/n):sha(original_review/n) for n in ('report.json','metrics_verification.json','figure_inputs.json')}
    record=load(study/'report.json');assert record['result']=='observer_frequency_correction_all6_measured'
    inputs[str(study/'report.json')]=sha(study/'report.json');solves=[]
    for case in record['cases']:
        folder=study/case['label'];path=folder/'source.npz';inputs[str(path)]=sha(path)
        with np.load(path) as z:source={k:z[k] for k in z.files}
        parts=[power_statistics(source['broadband_power'][ii],source['broadband_cross'][ii]) for ii in np.array_split(np.arange(case['source_rows']),3)]
        for field in ('mean','CV','complex_coherence'):source['chunks_broad_'+field]=np.stack([p[field] for p in parts])
        path=folder/case['file'];assert sha(path)==case['sha256'];inputs[str(path)]=sha(path)
        with np.load(path) as z:
            row=dict(label=case['label'],variant='block_refined',root_hz=case['root_hz'],weighted_objective=case['solve']['objective'],
                wave_NRMSE=float(z['wave_NRMSE']),wave_region_NRMSE=z['wave_region_NRMSE'].tolist(),
                source_broad_mean=source['broad_mean'].reshape(-1,2).tolist(),rendered_broad_mean=z['broad_mean'].reshape(-1,2).tolist())
            for prefix in ('line','broad','chunks_broad'):
                shape=(3,-1,2) if prefix=='chunks_broad' else (-1,2)
                row[prefix+'_power_error_dB']=(10*np.log10(np.maximum(z[prefix+'_mean'],1e-24)/np.maximum(source[prefix+'_mean'],1e-24))).reshape(shape).tolist()
                row[prefix+'_coherence_error']=abs(z[prefix+'_complex_coherence']-source[prefix+'_complex_coherence']).tolist()
                row[prefix+'_CV_error']=abs(z[prefix+'_CV']-source[prefix+'_CV']).reshape(shape).tolist()
            rows.append(row)
        solves.append(dict(label=case['label'],**case['solve']))
    assert len(rows)==36 and len(solves)==6
    return rows,solves,inputs


def summarize(rows,solves):
    out=dict(source_models=6,engines=1,ascents=2,in_sample_only=True,original_solver_converged=sum(s['converged'] for s in solves),
        stops=[s['stop'] for s in solves],variants={},paired={})
    for tag in VARIANTS:
        rr=[r for r in rows if r['variant']==tag]
        out['variants'][tag]=dict(weighted_objective_mean=float(np.mean([r['weighted_objective'] for r in rr])),
            **{k+'_mean':float(np.mean(abs(np.array([r[k] for r in rr])))) for k in ERRORS},
            broad_signed_power_error_dB_by_band=np.mean([r['broad_power_error_dB'] for r in rr],axis=(0,2)).tolist())
    candidate={r['label']:r for r in rows if r['variant']=='block_refined'}
    for tag in VARIANTS[:-1]:
        comparison={}
        for k in ERRORS:
            delta=np.array([abs(np.asarray(candidate[r['label']][k]))-abs(np.asarray(r[k])) for r in rows if r['variant']==tag])
            comparison[k]=dict(mean_change=float(delta.mean()),improved=int((delta < -1e-12).sum()),
                regressed=int((delta > 1e-12).sum()),equivalent=int((abs(delta)<=1e-12).sum()),count=int(delta.size))
        out['paired']['block_refined_minus_'+tag]=comparison
    return out
