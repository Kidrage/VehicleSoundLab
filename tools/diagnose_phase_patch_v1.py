"""Post-failure raw-peak and truth-conditioned representation diagnostics only."""
import argparse
import math
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.fft import rfft
from scipy.linalg import lstsq
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},rows=[],real_source_read=False)
try:
    for name in ['tools/diagnose_phase_patch_v1.py','research/phase_patch_failure_v1_plan.json','tools/research_archive_v1.py']:
        dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    audit=load(a.audit/'report.json')
    assert audit['result']=='failed_prerequisite_all12_native_inputs_fits_boundaries_and_original_gate_failure_verified'
    assert audit['input_report_sha256']==sha(a.input/'report.json')
    folder=a.input/'cubic_control'
    truth=load(folder/'truth.json')['rows']
    initial=load(folder/'initialization.json')
    fits=load(folder/'fits.json')
    n=12000
    t=(np.arange(n)-n/2)/48000
    window=np.hanning(n+1)[:-1]
    weight=np.sqrt(window/n)
    for i,true in enumerate(truth):
        z=np.load(folder/f'tile_{i:02d}.npz')
        audio=z['audio']
        transform=rfft(audio*window[:,None],axis=0)
        power=(transform.real**2+transform.imag**2)*2/(n*math.fsum(window*window))
        power[[0,-1]]*=.5
        total=power.sum(axis=1)
        logged=10*np.log10(np.maximum(total,np.finfo(float).tiny))
        raw=[]
        for j in range(1,len(logged)-1):
            if not logged[j]>max(logged[j-1],logged[j+1]):continue
            minima=[]
            for direction in [-1,1]:
                k=j
                low=logged[j]
                while 0<=k<len(logged) and logged[k]<=logged[j]:
                    low=min(low,logged[k])
                    k+=direction
                minima.append(low)
            maximum=max(total[k] for k in range(len(total)) if (30<=k*4<200 if j*4<200 else 200<=k*4<7000)) if 30<=j*4<7000 else None
            raw.append(dict(bin=j,hz=j*4,prominence_db=float(logged[j]-max(minima)),
                power_relative_db=float(10*np.log10(total[j]/maximum)) if maximum else None,
                selected=j in initial['inventories'][i]['bin']))
        full=[]
        retained=[]
        components=[]
        for line in true['lines']:
            f,q,c=line['frequency_hz'],line['chirp_hz_per_second'],line['curvature_hz_per_second2']
            theta=math.tau*(f*t+.5*q*t*t+c*t**3/6)+line['phase_at_midpoint_LR'][0]
            full.extend([np.cos(theta),np.sin(theta)])
            covered=any(abs(bin_number*4-f)<=2 for bin_number in initial['inventories'][i]['bin'])
            if covered:retained.extend([np.cos(theta),np.sin(theta)])
            nearby=[v for v in raw if abs(v['hz']-f)<=8]
            components.append(dict(component=line['index'],frequency_hz=f,covered_by_original_center_box=covered,raw_nearby_peaks=nearby))
        projections={}
        for name,columns in [('full_known_basis',full),('known_basis_for_detected_components',retained)]:
            design=np.column_stack(columns+[np.ones(n)])
            coefficients,_,rank,_=lstsq(weight[:,None]*design,weight[:,None]*audio,lapack_driver='gelsd')
            residual=audio-design@coefficients
            projections[name]=dict(rank=int(rank),columns=design.shape[1],
                weighted_relative_residual_LR=(np.linalg.norm(weight[:,None]*residual,axis=0)/np.linalg.norm(weight[:,None]*audio,axis=0)).tolist(),
                maximum_absolute_residual=float(abs(residual).max()))
        row=dict(window=i,selected_modes=len(initial['inventories'][i]['bin']),components=components,
            candidate_weighted_relative_residual_LR=fits[i]['weighted_relative_residual_LR'],projections=projections)
        np.savez_compressed(a.out/f'tile_{i:02d}.npz',power=power,logged=logged)
        save(a.out/f'raw_peaks_{i:02d}.json',raw)
        r['rows'].append(row)
    r.update(result='all12_failed_control_raw_peaks_and_truth_conditioned_projections_recorded',
        input_report_sha256=sha(a.input/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
        original_prerequisite_still_failed=True,nonlinear_fit_or_candidate_reselection=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
print([dict(window=v['window'],omitted=[x['component'] for x in v['components'] if not x['covered_by_original_center_box']],
    full=v['projections']['full_known_basis']['weighted_relative_residual_LR'],
    retained=v['projections']['known_basis_for_detected_components']['weighted_relative_residual_LR']) for v in r['rows']])
