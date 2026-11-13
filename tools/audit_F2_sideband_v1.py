"""Independent complex columns and QR audit of all18 fixed sideband observations."""
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
from line_motion_v1.sideband_controls import controls


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def number(pair):return complex(*pair)


def same(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:same(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,float):assert abs(a-b)<=1e-9
    else:assert a==b


def columns(frequency,chirp,time):
    values=[]
    for f,q in zip(frequency,chirp):
        center=np.exp(2j*np.pi*(f*time+.5*q*time**2))
        values.extend(center*np.exp(2j*np.pi*offset*time) for offset in (0,3,-3))
    return np.column_stack([z.real for z in values]+[z.imag for z in values]+[np.ones(len(time))])


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-sideband-audit/1',result='running',sources={},real_audio_read=False,
    nonlinear_fit_run=False,independent_linear_QR_check=True,shared_phase_clock_fit=False,
    model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_sideband_v1';actual=load(root/'observe1/report.json')
    assert actual['controls']['passed'];same(controls(),actual['controls'])
    # Independent periodic quadrature of exp(i beta cos(phi+psi)), no special-function formula.
    phi=2*np.pi*np.arange(512)/512;mod=np.exp(.2j*np.cos(phi+.4));c=.5*np.exp(.2j)
    expected=c*np.array([mod.mean(),np.mean(mod*np.exp(-1j*phi)),np.mean(mod*np.exp(1j*phi))])
    pm=next(case for case in actual['controls']['cases'] if case['id']=='true_phase_modulation')
    pm_values=np.array([number(pm['measurement']['parity'][0][key]) for key in ('central','upper','lower')])
    true_pm_coefficient_error=float(abs(pm_values-expected).max());assert true_pm_coefficient_error<=1e-5
    # Scalar cosine identity shows independent pairs and AM can be the exact same samples.
    t=np.arange(48000)/48000-.5;theta=2*np.pi*(75.25*t+.15*t*t)+.2
    am=.5*(1+.4*np.cos(2*np.pi*3*t+.6))*np.cos(theta)
    pairs=.5*np.cos(theta)+.1*np.cos(theta+2*np.pi*3*t+.6)+.1*np.cos(theta-2*np.pi*3*t-.6)
    identity_error=float(abs(am-pairs).max());assert identity_error<=1e-12
    arrays=np.load(root/'observe1/observations.npz');assert sha(root/'observe1/observations.npz')==actual['arrays_sha256']
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==actual['provenance'] and np.array_equal(audio,arrays['audio'])
    prior_path=args.workspace/'references/analysis/F2_local_chirps_v1/observe1/report.json';prior=load(prior_path)
    counter_path=args.workspace/'references/analysis/F2_peak_identity_v1/observe1/report.json';counter=load(counter_path)
    assert actual['prior_report_sha256']==sha(prior_path) and actual['counterfactual_report_sha256']==sha(counter_path)
    w=np.sqrt((1+np.cos(2*np.pi*t))/2/48000)
    errors=dict(waveform=0.,coefficients_QR=0.,cost=0.,gradient=0.,singular_values=0.,parity=0.,baseline_cost=0.)
    summaries=[];ranks=[];conditions=[];qr_normal=[]
    for i,row in enumerate(actual['observations']):
        assert row['source_seconds']==prior['observations'][i]['source_seconds']
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000]
        channel_rows=[]
        for ch,item in enumerate(row['fits']):
            parent=counter['counterfactual'][ch]['fit'] if i==1 else prior['observations'][i]['measured']['local_chirp_fit'][ch]
            assert item['parent_fit']==parent
            parameters=np.array(parent['fitted_parameters']);nominal=np.array(parent['nominal_Hz']);m=len(nominal)
            f=nominal+parameters[:m];q=parameters[m:2*m];measured=item['measurement']
            assert np.array_equal(f,np.array(measured['frequency_Hz'])) and np.array_equal(q,np.array(measured['chirp_Hz_per_s']))
            assert measured['offset_Hz']==3 and not measured['phase_coordinate_qualified'] and not measured['physical_source_classified']
            matrix=columns(f,q,t);coeff=np.array(measured['coefficients']);a=w[:,None]*matrix
            orthogonal,upper=np.linalg.qr(a,mode='reduced');independent=np.linalg.solve(upper,orthogonal.T@(w*part[:,ch]))
            singular=np.linalg.svd(upper,compute_uv=False)
            rank=int(np.sum(singular>singular[0]*max(a.shape)*np.finfo(float).eps))
            assert rank==measured['rank']==measured['columns']==matrix.shape[1]
            errors['coefficients_QR']=max(errors['coefficients_QR'],float(abs(independent-coeff).max()))
            errors['singular_values']=max(errors['singular_values'],float(abs(singular-np.array(measured['singular_values'])).max()))
            assert abs(singular[0]/singular[-1]-measured['condition'])<1e-10
            predicted=matrix@coeff;residual=predicted-part[:,ch];gradient=matrix.T@(w*w*residual)
            errors['waveform']=max(errors['waveform'],float(abs(predicted-arrays['after'][i,:,ch]).max()))
            cost=float(.5*np.dot(w*w,residual**2));errors['cost']=max(errors['cost'],abs(cost-measured['cost']))
            errors['gradient']=max(errors['gradient'],abs(float(abs(gradient).max())-measured['gradient_infinity']))
            assert abs(gradient).max()<1e-10
            qr_normal.append(float(abs(a.T@(a@independent-w*part[:,ch])).max()))
            z=coeff[:3*m]-1j*coeff[3*m:6*m];z=z.reshape(m,3)
            for j,(central,up,down) in enumerate(z):
                saved=measured['parity'][j]
                for key,value in zip(('central','upper','lower'),(central,up,down)):
                    errors['parity']=max(errors['parity'],abs(value-number(saved[key])))
                am=(up/central+np.conj(down/central))/2;quadrature=(up/central-np.conj(down/central))/(2j)
                errors['parity']=max(errors['parity'],abs(am-number(saved['am_relative'])),abs(quadrature-number(saved['quadrature_relative'])),
                    abs(am*abs(central)**2-number(saved['am_cross'])),abs(quadrature*abs(central)**2-number(saved['quadrature_cross'])),
                    abs(abs(central)**2-saved['central_power']))
            old=((parameters[2*m:3*m]-1j*parameters[3*m:4*m])*np.exp(2j*np.pi*(t[:,None]*f+.5*t[:,None]**2*q))).sum(axis=1).real+parameters[-1]
            errors['waveform']=max(errors['waveform'],float(abs(old-arrays['before'][i,:,ch]).max()))
            oldcost=float(.5*np.dot(w*w,(old-part[:,ch])**2));errors['baseline_cost']=max(errors['baseline_cost'],abs(oldcost-parent['cost']))
            assert abs(item['cost_reduction_fraction']-(1-cost/oldcost))<1e-12
            assert measured['rank']==len(coeff);ranks.append(rank);conditions.append(measured['condition'])
            channel_rows.append(dict(channel=ch,cost_reduction_percent=100*item['cost_reduction_fraction'],
                parent_main_at_bound=parent['at_bound'][:3],rank=rank,condition=measured['condition'],
                main_am_relative_magnitude=[float(abs(number(v['am_relative']))) for v in measured['parity'][:3]],
                main_quadrature_relative_magnitude=[float(abs(number(v['quadrature_relative']))) for v in measured['parity'][:3]]))
        summaries.append(dict(source_seconds=row['source_seconds'],channels=channel_rows))
    assert errors['waveform']<1e-10 and errors['coefficients_QR']<1e-10 and errors['cost']<1e-12
    assert errors['gradient']<1e-12 and errors['singular_values']<1e-10 and errors['parity']<1e-10 and errors['baseline_cost']<1e-12
    for file,digest in actual['sources'].items():assert sha(repo/file)==sha(root/'observe1/exact_sources'/file)==digest
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/line_motion_v1/sideband_controls.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='all18_conditional_sideband_projections_independently_QR_audited_not_source_classification',
        actual_report_sha256=sha(root/'observe1/report.json'),controls_replayed=True,source_samples_exact=True,
        independent_true_PM_coefficient_error=true_pm_coefficient_error,independent_AM_pair_identity_error=identity_error,
        errors=errors,comparisons=summaries,counts=dict(channel_projections=18,full_rank_projections=18),
        condition_range=[min(conditions),max(conditions)],max_independent_QR_normal_gradient=max(qr_normal),
        phase_extracted_real_model_permitted=False,RPM_inferred=False,
        limits=['No physical AM/FM source classifier is qualified: paired independent tones can exactly equal AM',
            'Half-bin coordinate error alone produces apparent AM/quadrature on a known unmodulated tone',
            'Fixed3Hz coefficients are conditional on the old local phase, including all parent bounds',
            'Training loss reduction and full rank do not establish out-of-window source recovery or naturalness'])
    print(json.dumps({k:report[k] for k in ('result','counts','condition_range','errors','independent_AM_pair_identity_error')}),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
