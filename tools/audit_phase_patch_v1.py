"""Audit the executed failed prerequisite without executing withheld controls."""
import argparse
import math
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.linalg import lstsq
from research_archive_v1 import load,save,sha
from native_chirp_audit_v1.wave import near
from native_chirp_audit_v1.temporal import audit_temporal
from chirp_motion_controls_v1.audit_inputs import inventory,initialization
from native_phase_patch_v1.audit_wave import check as check_wave
from native_phase_patch_v1.audit_link import check as check_link

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',windows=0,lines=0,maximum_signal_error=0.,maximum_waveform_error=0.,
    maximum_support_error=0.,maximum_normal_error=0.,maximum_optimality_error=0.,maximum_peak_error=0.,prerequisite_failures=[])
for name in ['tools/audit_phase_patch_v1.py','tools/native_phase_patch_v1/audit_wave.py',
    'tools/native_phase_patch_v1/audit_link.py','tools/chirp_motion_controls_v1/audit_inputs.py',
    'tools/native_chirp_audit_v1/wave.py','tools/native_chirp_audit_v1/temporal.py']:
    dest=a.out/'exact_sources'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(repo/name,dest)
try:
    report=load(a.input/'report.json')
    assert report['result']=='failed' and report['error']=='AssertionError()' and report['real_source_read'] is False
    assert 'prerequisite_passed' not in report and len(report['summaries'])==1
    assert [v['case'] for v in report['summaries']]==['cubic_control']
    assert sorted(v.name for v in a.input.iterdir() if v.is_dir())==['cubic_control','exact_sources']
    for name,h in report['sources'].items():assert sha(repo/name)==h==sha(a.input/'exact_sources'/name)
    baseline=a.workspace/'baselines/chirp_motion_controls_v1'
    assert sha(baseline/'manifest.json')==report['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(baseline/'manifest.json')['files']}
    for name,h in report['parent_files'].items():assert sha(baseline/name)==h==table[name]
    p0=load(baseline/'evidence/observe1/report.json')['plan']
    fp=load(repo/'research/accel_chirp_v1_plan.json')
    rp=load(repo/'research/accel_ridges_v1_plan.json')
    lp=load(repo/'research/low_chirp_v1_plan.json')
    control=np.load(a.input/'projection_control.npz')
    nominal,point,t,w,x=[control[k] for k in ['nominal','point','time','weight','audio']]
    def residual(p):
        m=len(nominal)
        f=nominal+p[:m]
        q=(p[m:2*m]+p[2*m:])/2
        curve=(p[2*m:]-p[m:2*m])/.25
        theta=math.tau*(t[:,None]*f+.5*t[:,None]**2*q+t[:,None]**3*curve/6)
        z=np.exp(1j*theta)
        matrix=w[:,None]*np.column_stack((z.real,z.imag,np.ones(len(t))))
        co=lstsq(matrix,w*x,lapack_driver='gelsd')[0]
        return matrix@co-w*x
    near(residual(point),control['residual'],1e-12)
    near(residual(point),control['SVD_residual'],1e-12)
    numeric=[]
    for j in range(9):
        step=np.zeros(9)
        step[j]=1e-5
        numeric.append((residual(point+step)-residual(point-step))/2e-5)
    r['independent_SVD_Jacobian_error']=near(np.column_stack(numeric),control['analytic'],1e-8)
    folder=a.input/'cubic_control'
    audio=np.load(folder/'signal.npz')['audio']
    tt=np.arange(len(audio))/48000
    expected=np.zeros_like(audio)
    for k,base in enumerate(p0['base_hz']):
        q=base*.05*p0['moving'][k]
        curve=base*.015*p0['moving'][k]
        angle=math.tau*base*tt+math.pi*q*tt**2+math.pi*curve*tt**3/3+p0['phase_radians'][k]
        carrier=np.exp(1j*angle)*p0['amplitude_L'][k]
        expected[:,0]+=carrier.real
        expected[:,1]+=(carrier*np.exp(1j*.17)*.71).real
    r['maximum_signal_error']=near(audio,expected,2e-12)
    rows=load(folder/'fits.json')
    obs=load(folder/'initialization.json')
    truth=load(folder/'truth.json')
    assert len(rows)==len(truth['rows'])==12
    for i,(row,true) in enumerate(zip(rows,truth['rows'])):
        center=(i+.5)*.25
        for k,v in enumerate(true['lines']):
            base=p0['base_hz'][k]
            q=base*.05*p0['moving'][k]
            curve=base*.015*p0['moving'][k]
            near([v['frequency_hz'],v['chirp_hz_per_second'],v['curvature_hz_per_second2']],
                [base+q*center+.5*curve*center**2,q+curve*center,curve])
            phase=math.tau*(base*center+.5*q*center**2+curve*center**3/6)+p0['phase_radians'][k]
            near(v['phase_at_midpoint_LR'],[phase,phase+.17])
            near(v['amplitude_LR'],[p0['amplitude_L'][k],p0['amplitude_L'][k]*.71])
            assert v['index']==k and v['visible'] and v['eligible']
        z=np.load(folder/f'tile_{i:02d}.npz')
        near(z['audio'],audio[i*12000:(i+1)*12000],0)
        scanned=inventory(z['audio'],obs['inventories'][i],rp)
        r['maximum_peak_error']=max(r['maximum_peak_error'],scanned['error'])
        assert scanned['strongest_index']==obs['guides'][i]['native_inventory_index']
        near(scanned['strongest_hz'],obs['guides'][i]['observed_hz'],1e-8)
        near(obs['ratios'][i],obs['guides'][i]['observed_hz']/obs['guides'][0]['observed_hz'])
        inv=obs['inventories'][i]
        m=len(inv['bin'])
        near(z['nominal'],np.array(inv['bin'])*4)
        near(z['initial'][:m],np.zeros(m))
        for part in [z['initial'][m:2*m],z['initial'][2*m:]]:
            near(part,np.clip(obs['initial'][i]['initial_chirp'],-500+1e-6,500-1e-6))
        for k,line in enumerate(row['lines']):
            assert (line['native_inventory_index'],line['native_bin'],line['native_peak_hz'])==(k,inv['bin'][k],inv['hz'][k])
        out=check_wave(z,row,fp)
        r['windows']+=1
        r['lines']+=len(row['lines'])
        for key in ['waveform_error','support_error','normal_error','optimality_error']:
            r['maximum_'+key]=max(r['maximum_'+key],out[key])
        reasons=[]
        if not row['success']:reasons.append('optimizer_failure')
        if len(row['lines'])!=10:reasons.append('mode_count')
        if not all(v['eligible'] for v in row['lines']):reasons.append('line_eligibility')
        if len(row['lines'])==10:
            for name,key,limit in [('frequency','frequency_hz',.06),('rate','chirp_hz_per_second',.15),('curvature','curvature_hz_per_second2',1.2)]:
                if max(abs(v[key]-e[key]) for v,e in zip(row['lines'],true['lines']))>=limit:reasons.append(name)
        relative=float(np.linalg.norm(z['residual'])/np.linalg.norm(z['audio']))
        if relative>=1e-5:reasons.append('waveform_relative_error')
        if reasons:r['prerequisite_failures'].append(dict(window=i,reasons=reasons,relative_residual=relative))
    initialization(obs['inventories'],obs['ratios'],obs['initial'])
    links=load(folder/'links.json')
    assert set(links)=={'new_old','new_new'}
    audit_temporal(rows,links['new_old'],lp)
    r['boundary_graph']=check_link(rows,links['new_new'])
    r['exact_boundary_graph']=check_link(truth['rows'],truth['boundary'])
    assert r['prerequisite_failures'][0]['window']==9 and r['prerequisite_failures'][0]['reasons'][0]=='mode_count'
    assert [v['window'] for v in r['prerequisite_failures']]==[9,10,11]
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        invariant=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename)
        assert len(invariant)==count
        for name,h in invariant.items():assert sha(repo/name)==h
    r.update(result='failed_prerequisite_all12_native_inputs_fits_boundaries_and_original_gate_failure_verified',
        input_report_sha256=sha(a.input/'report.json'),first_failed_gate='mode_count_at_window9',
        withheld_cases_run=False,real_source_read=False,C_H_unchanged=612,old_voices_unchanged=67,
        source_or_common_phase_qualification=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
print({key:r[key] for key in ['result','windows','lines','maximum_signal_error','maximum_waveform_error','maximum_peak_error','prerequisite_failures']})
