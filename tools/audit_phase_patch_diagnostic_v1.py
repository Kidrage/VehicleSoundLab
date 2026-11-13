"""Independent FFT/peak arithmetic and QR oracle for the failed known case."""
import argparse
import math
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','diagnostic','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.linalg import qr,solve_triangular
from research_archive_v1 import load,save,sha
from native_chirp_audit_v1.wave import near
a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_audit.py')
r=dict(result='running',windows=0,raw_peaks=0,maximum_power_error=0.,maximum_projection_error=0.,omitted=[])
try:
    report=load(a.diagnostic/'report.json')
    assert report['result']=='all12_failed_control_raw_peaks_and_truth_conditioned_projections_recorded'
    assert report['input_report_sha256']==sha(a.input/'report.json')
    for name,h in report['sources'].items():assert sha(repo/name)==h==sha(a.diagnostic/'exact_sources'/name)
    folder=a.input/'cubic_control'
    truth=load(folder/'truth.json')['rows']
    observed=load(folder/'initialization.json')
    fits=load(folder/'fits.json')
    n=12000
    time=np.array([(j-6000)/48000 for j in range(n)])
    window=np.hanning(n+1)[:-1]
    weight=np.sqrt(window/n)
    for i,row in enumerate(report['rows']):
        audio=np.load(folder/f'tile_{i:02d}.npz')['audio']
        saved=np.load(a.diagnostic/f'tile_{i:02d}.npz')
        z=np.fft.rfft(audio*window[:,None],axis=0)
        power=2*abs(z)**2/(n*math.fsum(window*window))
        power[[0,-1]]*=.5
        r['maximum_power_error']=max(r['maximum_power_error'],near(power,saved['power'],1e-12))
        # Absolute powers are checked independently. Formula replay uses the
        # exact saved cells: normalized descriptors at roundoff nulls have no
        # physical precision. The 115.7Hz diagnostic is well above these nulls.
        total=saved['power'].sum(axis=1)
        log=10*np.log10(np.maximum(total,np.finfo(float).tiny))
        near(log,saved['logged'])
        peaks=[j for j in range(1,len(log)-1) if log[j]>log[j-1] and log[j]>log[j+1]]
        raw=load(a.diagnostic/f'raw_peaks_{i:02d}.json')
        assert [v['bin'] for v in raw]==peaks
        for v,j in zip(raw,peaks):
            left=j
            while left>0 and log[left-1]<=log[j]:left-=1
            right=j
            while right<len(log)-1 and log[right+1]<=log[j]:right+=1
            prominence=log[j]-max(min(log[left:j+1]),min(log[j:right+1]))
            near(prominence,v['prominence_db'])
            assert v['hz']==j*4 and v['selected']==(j in observed['inventories'][i]['bin'])
            if 30<=j*4<7000:
                lo,hi=(30,200) if j*4<200 else (200,7000)
                maximum=max(total[k] for k in range(len(total)) if lo<=k*4<hi)
                near(10*math.log10(total[j]/maximum),v['power_relative_db'])
                assert v['selected']==(prominence>=8 and v['power_relative_db']>=-42)
            else:assert v['power_relative_db'] is None
        r['raw_peaks']+=len(raw)
        full=[]
        restricted=[]
        omitted=[]
        for k,known in enumerate(truth[i]['lines']):
            angle=np.array([phase/math.tau+known['frequency_hz']*t+.5*known['chirp_hz_per_second']*t*t+known['curvature_hz_per_second2']*t**3/6
                for t,phase in zip(time,np.full(n,known['phase_at_midpoint_LR'][0]))])*math.tau
            carrier=np.exp(1j*angle)
            full.extend([carrier.real,carrier.imag])
            covered=any(abs(f*4-known['frequency_hz'])<=2 for f in observed['inventories'][i]['bin'])
            assert covered==row['components'][k]['covered_by_original_center_box']
            near(known['frequency_hz'],row['components'][k]['frequency_hz'])
            assert row['components'][k]['component']==k
            assert row['components'][k]['raw_nearby_peaks']==[v for v in raw if abs(v['hz']-known['frequency_hz'])<=8]
            if covered:restricted.extend([carrier.real,carrier.imag])
            else:omitted.append(k)
        r['omitted'].append(dict(window=i,components=omitted))
        for name,cols in [('full_known_basis',full),('known_basis_for_detected_components',restricted)]:
            design=np.column_stack(cols+[np.ones(n)])
            weighted=weight[:,None]*design
            Q,R=qr(weighted,mode='economic')
            co=solve_triangular(R,Q.T@(weight[:,None]*audio))
            residual=audio-design@co
            actual=row['projections'][name]
            assert actual['rank']==actual['columns']==design.shape[1]
            relative=np.linalg.norm(weight[:,None]*residual,axis=0)/np.linalg.norm(weight[:,None]*audio,axis=0)
            error=max(near(relative,actual['weighted_relative_residual_LR']),near(abs(residual).max(),actual['maximum_absolute_residual']))
            r['maximum_projection_error']=max(r['maximum_projection_error'],error)
        assert row['candidate_weighted_relative_residual_LR']==fits[i]['weighted_relative_residual_LR']
        r['windows']+=1
    assert r['windows']==12 and [v['window'] for v in r['omitted'] if v['components']]==[9,10,11]
    assert all(v['components']==[3] for v in r['omitted'][9:])
    r.update(result='all12_raw_peak_arithmetic_and_truth_projection_omission_diagnostics_verified',
        input_report_sha256=sha(a.input/'report.json'),diagnostic_report_sha256=sha(a.diagnostic/'report.json'),
        absolute_power_independent_and_exact_cells_formula_replay=True,roundoff_null_normalized_values_not_physical=True,
        original_prerequisite_still_failed=True,no_new_estimator_or_optimization=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
print({key:r[key] for key in ['result','windows','raw_peaks','maximum_power_error','maximum_projection_error']})
