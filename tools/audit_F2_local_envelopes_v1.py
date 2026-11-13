"""Audit saved affine-envelope fits using complex algebra; no real re-solves."""
import argparse
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from line_motion_v1.envelope_controls import controls,fixtures
from line_motion_v1.local_envelopes import evaluate


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def same(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:same(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,float):assert abs(a-b)<=1e-9
    else:assert a==b


def wave(parameters,nominal,t,affine):
    m=len(nominal);f=nominal+parameters[:m];q=parameters[m:2*m]
    z=parameters[2*m:3*m]-1j*parameters[3*m:4*m]
    e=np.exp(2j*np.pi*(t[:,None]*f+.5*t[:,None]**2*q));v=e*z
    gain=1+t[:,None]*parameters[4*m:5*m] if affine else np.ones((len(t),m))
    scaled=gain*v
    columns=[(2j*np.pi*t[:,None]*scaled).real,(1j*np.pi*t[:,None]**2*scaled).real,
        gain*e.real,gain*e.imag]
    if affine:columns.append(t[:,None]*v.real)
    columns.append(np.ones((len(t),1)))
    return scaled.real.sum(axis=1)+parameters[-1],np.column_stack(columns)


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-local-envelopes-audit/1',result='running',sources={},real_audio_read=False,
    actual_fits_resolved_again=False,shared_phase_clock_fit=False,model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_local_envelopes_v1';actual=load(root/'observe2/report.json')
    failed=load(root/'observe1/report.json');assert failed['result']=='failed' and not failed['real_audio_read']
    package=root/'observe1/exact_sources/tools/line_motion_v1'
    spec=importlib.util.spec_from_file_location('failed_affine_fixture',package/'__init__.py',submodule_search_locations=[str(package)])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    original=importlib.import_module(spec.name+'.envelope_controls')
    try:list(original.fixtures())
    except AssertionError as exc:assert str(exc)=='Fixed six-tone fixture must have exactly two low-region observed peaks'
    else:raise AssertionError('Original negative fixture failure did not reproduce')
    assert actual['controls']['passed'];same(controls(),actual['controls'])
    # Independently synthesize the four specified in-model fixtures in complex form.
    t=np.arange(48000)/48000-.5;known_error=0.
    f=np.array([75.2,112.8,188.,82.3,37.6,45.1]);q=np.array([.3,.4,.6,-.2,.1,-.1])
    amp=np.array([.5,.4,.3,.18,.14,.17]);phase=np.array([.2,.5,.8,.1,.4,.7])
    for fixture in fixtures():
        if fixture.get('inventory_unresolved'):
            assert fixture['additional_low_candidates_Hz']==[38,42,48,34]
            continue
        name=fixture['id'];indices=np.array([0] if name=='single_affine' else ([0,3] if name=='neighbor_pair_affine' else list(range(6))))
        freq=f[indices].copy();chirp=q[indices].copy()
        if name=='single_affine':freq[:]=75.19;chirp[:]=0
        s=np.zeros(6) if name=='six_constant' else (np.array([.8]) if name=='single_affine' else (np.array([.8,-.6]) if name=='neighbor_pair_affine' else np.array([.8,-.6,.4,-.8,.6,-.4])))
        independent=((1+t[:,None]*s)*amp[indices]*np.exp(1j*(2*np.pi*(t[:,None]*freq+.5*t[:,None]**2*chirp)+phase[indices]))).sum(axis=1).real
        known_error=max(known_error,float(abs(independent-fixture['audio']).max()))
    assert known_error<1e-12
    prior_path=args.workspace/'references/analysis/F2_local_chirps_v1/observe1/report.json';prior=load(prior_path)
    counter_path=args.workspace/'references/analysis/F2_peak_identity_v1/observe1/report.json';counter=load(counter_path)
    assert actual['prior_report_sha256']==sha(prior_path) and actual['counterfactual_report_sha256']==sha(counter_path)
    arrays=np.load(root/'observe2/observations.npz');assert sha(root/'observe2/observations.npz')==actual['arrays_sha256']
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==actual['provenance'] and np.array_equal(audio,arrays['audio'])
    hann=np.sin(np.pi*np.arange(48000)/48000)**2;weight=hann/48000
    errors=dict(waveform=0.,jacobian=0.,finite_difference=0.,cost=0.,optimality=0.,initial=0.)
    comparisons=[];old_main_rows=0;new_main_rows=0;new_eligible_rows=0;slopes_at_bound=0;frequencies_at_bound=0
    converged=0;budget_exhausted=0;raw_main_rows=0
    for i,row in enumerate(actual['observations']):
        assert row['source_seconds']==prior['observations'][i]['source_seconds']
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000]
        old_good=[];new_good=[];eligible=[];saturated=[];raw_inside=[];successes=[]
        for ch,item in enumerate(row['fits']):
            reference=counter['counterfactual'][ch]['fit'] if i==1 else prior['observations'][i]['measured']['local_chirp_fit'][ch]
            assert item['constant_fit']==reference
            for key,fit,affine in [('before',reference,False),('after',item['affine_fit'],True)]:
                p0=np.array(fit['fitted_parameters']);nominal=np.array(fit['nominal_Hz']);m=len(nominal)
                predicted,jac=wave(p0,nominal,t,affine)
                errors['waveform']=max(errors['waveform'],float(abs(predicted-arrays[key][i,:,ch]).max()))
                residual=predicted-part[:,ch];cost=float(.5*np.dot(weight,residual**2));gradient=jac.T@(weight*residual)
                low=np.r_[np.full(m,-.5),np.full(m,-2.),np.full(2*m,-np.inf),np.full(m,-1.),-np.inf] if affine else np.r_[np.full(m,-.5),np.full(m,-2.),np.full(2*m+1,-np.inf)]
                high=-low;assert np.all(p0>=low) and np.all(p0<=high)
                bound=(abs(p0[:m])>=.5-1e-7)|(abs(p0[m:2*m])>=2-1e-7)
                assert bound.tolist()==fit['at_bound']
                distance=np.ones(len(p0))
                for k,g in enumerate(gradient):
                    if g<0 and np.isfinite(high[k]):distance[k]=high[k]-p0[k]
                    elif g>0 and np.isfinite(low[k]):distance[k]=p0[k]-low[k]
                errors['cost']=max(errors['cost'],abs(cost-fit['cost']))
                errors['optimality']=max(errors['optimality'],abs(float(abs(distance*gradient).max())-fit['optimality']))
                if affine:
                    slope=abs(p0[4*m:5*m])>=1-1e-7;assert slope.tolist()==fit['slope_at_bound']
                    assert float(1-.5*abs(p0[4*m:5*m]).max())>=.5
                    frequencies_at_bound+=int(bound.sum());slopes_at_bound+=int(slope.sum())
                    converged+=int(fit['success']);budget_exhausted+=int(fit['status']==0)
                    raw_inside.append(not any(bound[:3]));successes.append(fit['success'])
                    new_good.append(fit['success'] and not any(bound[:3]));eligible.append(fit['success'] and not any(bound[:3]|slope[:3]))
                    saturated.append(slope.tolist())
                    e=np.exp(2j*np.pi*t[:,None]*nominal);linear=np.column_stack((e.real,e.imag,np.ones(len(t))))
                    coeff=np.linalg.lstsq(np.sqrt(weight)[:,None]*linear,np.sqrt(weight)*part[:,ch],rcond=None)[0]
                    initial=np.zeros(5*m+1);initial[2*m:4*m]=coeff[:-1];initial[-1]=coeff[-1]
                    errors['initial']=max(errors['initial'],float(abs(initial-np.array(fit['initial'])).max()))
                    original_wave,original_jac=evaluate(p0,nominal,t)
                    errors['jacobian']=max(errors['jacobian'],float(abs(original_jac-jac).max()))
                    if i==0 and ch==0:
                        for k in range(len(p0)):
                            h=2e-6;plus=p0.copy();minus=p0.copy();plus[k]+=h;minus[k]-=h
                            finite=(wave(plus,nominal,t,True)[0]-wave(minus,nominal,t,True)[0])/(2*h)
                            errors['finite_difference']=max(errors['finite_difference'],float(abs(finite-jac[:,k]).max()))
                    old=np.array(reference['fitted_parameters'])
                    assert np.max(abs(np.array(item['main_frequency_change_Hz'])-(p0[:3]-old[:3])))<1e-12
                    assert np.max(abs(np.array(item['main_chirp_change_Hz_per_s'])-(p0[m:m+3]-old[m:m+3])))<1e-12
                else:old_good.append(fit['success'] and not any(bound[:3]))
            assert abs(item['cost_reduction_fraction']-(1-item['affine_fit']['cost']/reference['cost']))<1e-14
        old_main_rows+=int(all(old_good));new_main_rows+=int(all(new_good));new_eligible_rows+=int(all(eligible))
        raw_main_rows+=int(all(raw_inside))
        comparisons.append(dict(source_seconds=row['source_seconds'],old_main_fit_eligible=all(old_good),new_main_fit_eligible=all(new_good),
            new_main_fit_and_slope_eligible=all(eligible),new_main_raw_fq_inside=all(raw_inside),new_channel_success=successes,
            left_cost_reduction_percent=100*row['fits'][0]['cost_reduction_fraction'],
            slope_bounds=saturated))
    assert errors['waveform']<1e-10 and errors['jacobian']<1e-9 and errors['finite_difference']<1e-6
    assert errors['cost']<1e-12 and errors['optimality']<1e-10 and errors['initial']<1e-10
    versions={}
    for name in ('observe1','diagnosis1','observe2'):
        value=load(root/name/'report.json')
        for file,digest in value['sources'].items():
            assert sha(root/name/'exact_sources'/file)==digest
            if name!='observe1':assert sha(repo/file)==digest
            versions.setdefault(file,{})[name]=digest
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/line_motion_v1/envelope_controls.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='all18_affine_envelope_local_fits_and_original_negative_failure_independently_audited',
        actual_report_sha256=sha(root/'observe2/report.json'),failed_report_sha256=sha(root/'observe1/report.json'),
        original_failure_replayed=True,controls_replayed=True,independent_known_wave_error=known_error,source_samples_exact=True,
        errors=errors,source_versions=versions,comparisons=comparisons,
        counts=dict(real_channel_fits=18,old_main_fq_rows=old_main_rows,new_main_fq_rows=new_main_rows,
            new_main_fq_and_slope_rows=new_eligible_rows,new_fq_bound_components=frequencies_at_bound,new_slope_bound_components=slopes_at_bound,
            converged_channel_fits=converged,evaluation_limit_channel_fits=budget_exhausted,new_raw_main_fq_rows=raw_main_rows),
        phase_extracted_real_model_permitted=False,RPM_inferred=False,
        limits=['Positive affine amplitudes do not cover arbitrary AM or missing nearby components',
            'Out-of-model sinusoidal AM candidate inventory is unresolved; no six-line fit was forced or accepted',
            'Additional local amplitude parameters can lower training error without identifying real frequency or shared phase',
            'Fit eligibility includes numerical success: at7..8s raw bounds are inside but max60 evaluations are exhausted in both channels',
            'Main-frequency bounds and amplitude bounds are separate; neither alone establishes model adequacy or naturalness'])
    print(json.dumps({k:report[k] for k in ('result','counts','errors','comparisons')}),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
