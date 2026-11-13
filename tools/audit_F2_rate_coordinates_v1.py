"""Independent complex chirp and QR audit of rate-law diagnostics and all18+72 real fits."""
import argparse
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
from line_motion_v1.rate_coordinate_controls import controls
from line_motion_v1.local_chirps import evaluate


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def same(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for key in a:same(a[key],b[key])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,float):assert abs(a-b)<=1e-9
    else:assert a==b


def complex_wave(parameters,nominal,t):
    m=len(nominal);f=nominal+parameters[:m];q=parameters[m:2*m]
    e=np.exp(2j*np.pi*(t[:,None]*f+.5*t[:,None]**2*q));z=parameters[2*m:3*m]-1j*parameters[3*m:4*m];v=e*z
    return v.real.sum(axis=1)+parameters[-1],np.column_stack(((2j*np.pi*t[:,None]*v).real,
        (1j*np.pi*t[:,None]**2*v).real,e.real,e.imag,np.ones(len(t))))


def spaces(f,q,central,t):
    e=np.column_stack([np.exp(2j*np.pi*(hz*t+.5*slope*t*t)) for hz,slope in zip(f,q)])
    base=np.column_stack([e[:,j].real for j in range(len(f))]+[e[:,j].imag for j in range(len(f))]+[np.ones(len(t))])
    v=e*central;shift=np.exp(2j*np.pi*3*t[:,None]);c=(shift+np.conj(shift))/2;s=(shift-np.conj(shift))/(2j)
    a=np.column_stack(((v*c).real,(v*s).real));p=np.column_stack(((1j*v*c).real,(1j*v*s).real))
    return dict(base=base,amplitude=np.column_stack((base,a)),quadrature=np.column_stack((base,p)),joint=np.column_stack((base,a,p)))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-rate-coordinates-audit/1',result='running',sources={},real_audio_read=False,
    real_nonlinear_fits_resolved_again=False,independent_subspace_linear_QR_check=True,
    shared_phase_clock_fit=False,model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_rate_coordinates_v1';first=load(root/'diagnosis1/report.json');second=load(root/'diagnosis2/report.json')
    one=np.load(root/'diagnosis1/known.npz');two=np.load(root/'diagnosis2/known.npz')
    assert one.files==two.files and all(np.array_equal(one[key],two[key]) for key in one.files)
    assert first['cases'][0]['amplitude_cost_reduction_percent'] is not None and second['cases'][0]['amplitude_cost_reduction_percent'] is None
    assert not second['cases'][0]['relative_cost_defined']
    t=np.arange(48000)/48000-.5;weight=np.sin(np.pi*(t+.5))/np.sqrt(48000)
    known_error=0.
    f=np.array([75.2,112.8,188.,82.3]);amp=np.array([.5,.4,.3,.18]);phase=np.array([.2,.5,.8,.1])
    for i,(r1,r2,slope) in enumerate(zip(first['cases'],second['cases'],(.3,.6,-.6))):
        assert r1['original_fit']==r2['original_fit']
        q=np.array([2*slope,3*slope,5*slope,-.2])
        known=((amp*np.exp(1j*phase))*np.exp(2j*np.pi*(t[:,None]*f+.5*t[:,None]**2*q))).sum(axis=1).real
        known_error=max(known_error,float(abs(known-two[r2['id']+'_audio']).max()))
        if i:assert r2['original_fit']['at_bound'][2] and r2['waveform_relative_error']>.1
        assert r2['exact_coordinate_operator_contract']['base']['cost']<=1e-20
    assert known_error<=1e-12
    actual=load(root/'observe1/report.json');assert actual['controls']['passed'];same(controls(),actual['controls'])
    parent_root=args.workspace/'references/analysis/F2_sideband_v1';parent=load(parent_root/'observe1/report.json');prior_spaces=load(parent_root/'subspaces1/report.json')
    assert actual['parent_report_sha256']==sha(parent_root/'observe1/report.json')
    assert actual['old_subspaces_report_sha256']==sha(parent_root/'subspaces1/report.json')
    arrays=np.load(root/'observe1/observations.npz');assert sha(root/'observe1/observations.npz')==actual['arrays_sha256']
    old_arrays=np.load(parent_root/'observe1/observations.npz');assert np.array_equal(arrays['old'],old_arrays['before'])
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==actual['provenance']==parent['provenance'] and np.array_equal(audio,arrays['audio'])
    errors=dict(waveform=0.,jacobian=0.,finite_difference=0.,cost=0.,optimality=0.,initial=0.,subspace_wave=0.,subspace_QR=0.,subspace_cost=0.,subspace_singular=0.)
    rows=[];old_main_rows=0;new_main_rows=0;all_inside_rows=0;old_bound=0;new_bound=0;component_count=0;success_count=0;linear_count=0
    for i,row in enumerate(actual['observations']):
        assert row['source_seconds']==parent['observations'][i]['source_seconds']
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000];old_good=[];new_good=[];all_good=[];channels=[]
        for ch,item in enumerate(row['channels']):
            old=parent['observations'][i]['fits'][ch]['parent_fit'];assert item['old_fit']==old
            fit=item['new_fit'];p0=np.array(fit['fitted_parameters']);nominal=np.array(fit['nominal_Hz']);m=len(nominal)
            assert nominal.tolist()==old['nominal_Hz'] and fit['reference_Hz']==nominal[0] and fit['reference_limit_Hz_per_s']==2
            limit=2*nominal/nominal[0];assert np.array_equal(limit,np.array(fit['chirp_limits_Hz_per_s']))
            assert np.max(abs(limit-(2*nominal[2]/nominal[0])*nominal/nominal[2]))<1e-12
            low=np.r_[np.full(m,-.5),-limit,np.full(2*m+1,-np.inf)];high=-low
            assert np.all(p0>=low) and np.all(p0<=high)
            bound=(abs(p0[:m])>=.5-1e-7)|(abs(p0[m:2*m])>=limit-1e-7);assert bound.tolist()==fit['at_bound']
            predicted,jac=complex_wave(p0,nominal,t);value,analytic=evaluate(p0,nominal,t)
            errors['waveform']=max(errors['waveform'],float(abs(predicted-arrays['new'][i,:,ch]).max()))
            errors['jacobian']=max(errors['jacobian'],float(abs(jac-analytic).max()))
            if i==0 and ch==0:
                for j in range(len(p0)):
                    h=2e-6;plus=p0.copy();minus=p0.copy();plus[j]+=h;minus[j]-=h
                    finite=(complex_wave(plus,nominal,t)[0]-complex_wave(minus,nominal,t)[0])/(2*h)
                    errors['finite_difference']=max(errors['finite_difference'],float(abs(finite-jac[:,j]).max()))
            residual=predicted-part[:,ch];cost=float(.5*np.dot(weight**2,residual**2));gradient=jac.T@(weight**2*residual)
            distance=np.ones(len(p0))
            for j,g in enumerate(gradient):
                if g<0 and np.isfinite(high[j]):distance[j]=high[j]-p0[j]
                elif g>0 and np.isfinite(low[j]):distance[j]=p0[j]-low[j]
            errors['cost']=max(errors['cost'],abs(cost-fit['cost']))
            errors['optimality']=max(errors['optimality'],abs(float(abs(distance*gradient).max())-fit['optimality']))
            z=np.exp(2j*np.pi*t[:,None]*nominal);linear=np.column_stack((z.real,z.imag,np.ones(len(t))))
            initial=np.r_[np.zeros(2*m),np.linalg.lstsq(weight[:,None]*linear,weight*part[:,ch],rcond=None)[0]]
            errors['initial']=max(errors['initial'],float(abs(initial-np.array(fit['initial'])).max()))
            old_good.append(old['success'] and not any(old['at_bound'][:3]));new_good.append(fit['success'] and not any(bound[:3]));all_good.append(fit['success'] and not any(bound))
            old_bound+=sum(old['at_bound']);new_bound+=int(bound.sum());component_count+=m;success_count+=int(fit['success'])
            central=p0[2*m:3*m]-1j*p0[3*m:4*m];costs={}
            for key,matrix in spaces(nominal+p0[:m],p0[m:2*m],central,t).items():
                measured=item['subspaces'][key];coeff=np.array(measured['coefficients']);weighted=weight[:,None]*matrix
                orthogonal,upper=np.linalg.qr(weighted,mode='reduced');qr=np.linalg.solve(upper,orthogonal.T@(weight*part[:,ch]))
                singular=np.linalg.svd(upper,compute_uv=False);rank=int(np.sum(singular>singular[0]*max(weighted.shape)*np.finfo(float).eps))
                assert rank==measured['rank']==measured['columns']==matrix.shape[1]
                assert abs(singular[0]/singular[-1]-measured['condition'])<1e-9
                wave=matrix@coeff;rest=wave-part[:,ch];c=float(.5*np.dot(weight**2,rest**2))
                errors['subspace_wave']=max(errors['subspace_wave'],float(abs(wave-arrays[key][i,:,ch]).max()))
                errors['subspace_QR']=max(errors['subspace_QR'],float(abs(qr-coeff).max()))
                errors['subspace_cost']=max(errors['subspace_cost'],abs(c-measured['cost']))
                errors['subspace_singular']=max(errors['subspace_singular'],float(abs(singular-np.array(measured['singular_values'])).max()))
                assert np.max(abs(matrix.T@(weight**2*rest)))<1e-10
                costs[key]=c;linear_count+=1
            assert abs(item['local_cost_reduction_percent']-100*(1-fit['cost']/old['cost']))<1e-12
            prior=prior_spaces['observations'][i]['channels'][ch]
            for key in ('amplitude','quadrature','joint'):
                assert item['old_subspace_summary'][key+'_reduction_percent']==prior[key+'_reduction_percent']
                assert abs(item[key+'_reduction_percent']-100*(1-costs[key]/costs['base']))<1e-10
            channels.append(dict(channel=ch,old_at_bound=old['at_bound'],new_at_bound=fit['at_bound'],success=fit['success'],
                local_cost_reduction_percent=item['local_cost_reduction_percent'],reference_Hz=fit['reference_Hz'],limits_Hz_per_s=limit.tolist(),
                old_Q_reduction_percent=item['old_subspace_summary']['quadrature_reduction_percent'],new_Q_reduction_percent=item['quadrature_reduction_percent'],
                old_Q_cost_difference=prior['models']['base']['cost']-prior['models']['quadrature']['cost'],
                new_Q_cost_difference=costs['base']-costs['quadrature']))
        old_main_rows+=int(all(old_good));new_main_rows+=int(all(new_good));all_inside_rows+=int(all(all_good));rows.append(dict(source_seconds=row['source_seconds'],channels=channels))
    assert errors['waveform']<1e-10 and errors['jacobian']<1e-9 and errors['finite_difference']<1e-6
    assert errors['cost']<1e-12 and errors['optimality']<1e-10 and errors['initial']<1e-10
    assert errors['subspace_wave']<1e-10 and errors['subspace_QR']<1e-10 and errors['subspace_cost']<1e-12 and errors['subspace_singular']<1e-10
    versions={}
    for name in ('diagnosis1','diagnosis2','observe1'):
        value=load(root/name/'report.json')
        for file,digest in value['sources'].items():
            assert sha(root/name/'exact_sources'/file)==digest
            if name!='diagnosis1':assert sha(repo/file)==digest
            versions.setdefault(file,{})[name]=digest
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/line_motion_v1/rate_coordinate_controls.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='known_flat_clipping_and_all18_rate_fits_plus72_subspaces_independently_audited',
        actual_report_sha256=sha(root/'observe1/report.json'),diagnostic_reports_sha256={name:sha(root/name/'report.json') for name in ('diagnosis1','diagnosis2')},
        known_diagnostic_arrays_and_fits_exact_between_revisions=True,known_complex_wave_error=known_error,controls_replayed=True,source_samples_exact=True,
        counts=dict(channel_fits=18,successful_channel_fits=success_count,components=component_count,old_bound_components=old_bound,new_bound_components=new_bound,
            old_main_eligible_rows=old_main_rows,new_main_eligible_rows=new_main_rows,new_all_component_eligible_rows=all_inside_rows,linear_subspace_projections=linear_count),
        comparisons=rows,errors=errors,source_versions=versions,phase_extracted_real_model_permitted=False,RPM_inferred=False,
        limits=['Nine main-fit rows within the new relative prior do not prove a complete common engine clock or model adequacy',
            'Some other lines remain at bounds; independent sources and nonquadratic phase remain unresolved',
            'Conditional Q residuals largely persist, so flat main-line clipping cannot alone explain them',
            'The engineering prior changes; training cost and boundary counts are not timbre acceptance or measured acceleration'])
    print(json.dumps({k:report[k] for k in ('result','counts','errors')}),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
