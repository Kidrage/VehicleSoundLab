"""Independently audit one-step precision corrections and all72 overlap comparisons."""
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
from line_motion_v1.local_precision_controls import controls
from line_motion_v1.local_chirps import evaluate


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def same(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:same(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,float):assert abs(a-b)<1e-9
    else:assert a==b


def complex_model(parameters,nominal,t):
    m=len(nominal);f=nominal+parameters[:m];q=parameters[m:2*m]
    e=np.exp(2j*np.pi*(t[:,None]*f+.5*t[:,None]**2*q));v=e*(parameters[2*m:3*m]-1j*parameters[3*m:4*m])
    return v.real.sum(axis=1)+parameters[-1],np.column_stack(((2j*np.pi*t[:,None]*v).real,
        (1j*np.pi*t[:,None]**2*v).real,e.real,e.imag,np.ones(len(t))))


def independent_line(fit,seconds,j,time):
    m=len(fit['nominal_Hz']);v=fit['fitted_parameters'];f=fit['nominal_Hz'][j]+v[j];q=v[m+j]
    a=v[2*m+j];b=v[3*m+j];c=.5*sum(seconds);t=time-c
    angle=2*np.pi*f*t+np.pi*q*t*t
    # Direct quadratures rather than the production complex exponential.
    real=a*np.cos(angle)+b*np.sin(angle);imag=a*np.sin(angle)-b*np.cos(angle)
    return real+1j*imag,dict(centre_seconds=c,frequency_Hz=f,chirp_Hz_per_s=q,a=a,b=b,
        nominal_bin_Hz=fit['nominal_Hz'][j],success=fit['success'],at_bound=fit['at_bound'][j])


def independent_metrics(a,b,one,two,time):
    p=a['a']**2+a['b']**2;s=b['a']**2+b['b']**2;aa=np.sqrt(p);bb=np.sqrt(s)
    df=(b['frequency_Hz']-b['chirp_Hz_per_s']*b['centre_seconds']
        -a['frequency_Hz']+a['chirp_Hz_per_s']*a['centre_seconds'])
    dq=b['chirp_Hz_per_s']-a['chirp_Hz_per_s'];frequency=df+dq*time
    cross=two.imag*one.real-two.real*one.imag;dot=two.real*one.real+two.imag*one.imag
    wrapped=np.arctan2(cross,dot)/(2*np.pi)
    gc=(np.arctan2(-b['b'],b['a'])-np.arctan2(-a['b'],a['a']))/(2*np.pi)
    for line,sign in ((b,1),(a,-1)):
        gc+=sign*(.5*line['chirp_Hz_per_s']*line['centre_seconds']**2-line['frequency_Hz']*line['centre_seconds'])
    raw=gc+df*time+.5*dq*time*time;mid=.5*(time[0]+time[-1]);raw_mid=gc+df*mid+.5*dq*mid*mid
    # Only remove an integer cycle branch; preserve the full principal midpoint offset.
    cycles=np.floor(raw_mid+.5);middle=raw_mid-cycles;continuous=raw-cycles
    return dict(samples=len(time),amplitude_left=float(aa),amplitude_right=float(bb),
        frequency_difference_rms_Hz=float(np.linalg.norm(frequency)/np.sqrt(len(time))),
        frequency_difference_max_Hz=float(abs(frequency).max()),chirp_difference_Hz_per_s=dq,
        complex_difference_relative_rms=float(np.linalg.norm(two-one)/np.sqrt(len(time)*.5*(p+s))),
        unit_phasor_rms_distance=float(np.linalg.norm(two/bb-one/aa)/np.sqrt(len(time))),
        wrapped_phase_rms_cycles=float(np.linalg.norm(wrapped)/np.sqrt(len(time))),wrapped_phase_max_cycles=float(abs(wrapped).max()),
        midpoint_phase_difference_cycles=float(middle),continuous_phase_rms_cycles=float(np.linalg.norm(continuous)/np.sqrt(len(time))),
        continuous_phase_max_cycles=float(abs(continuous).max()))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-overlap-phase-audit/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False,real_nonlinear_resolves=0)
try:
    root=args.workspace/'references/analysis/F2_overlap_phase_v1';actual_path=root/'observe2/report.json';actual=load(actual_path)
    failed=load(root/'observe1/report.json');assert failed['result']=='failed' and not failed['real_audio_read']
    assert actual['original_failed_observation_report_sha256']==sha(root/'observe1/report.json')
    checked=controls();same(checked,actual['controls'])
    same(failed['controls'],checked['original_overlap_control'])
    assert checked['passed'] and not checked['original_overlap_control']['passed']
    parent_root=args.workspace/'references/analysis/F2_rate_coordinates_v1';parent=load(parent_root/'observe1/report.json')
    assert actual['parent_report_sha256']==sha(parent_root/'observe1/report.json')
    assert actual['parent_arrays_sha256']==parent['arrays_sha256']==sha(parent_root/'observe1/observations.npz')
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    parent_arrays=np.load(parent_root/'observe1/observations.npz')
    assert provenance==actual['provenance']==parent['provenance'] and np.array_equal(audio,parent_arrays['audio'])
    arrays=np.load(root/'observe2/overlaps.npz');assert actual['arrays_sha256']==sha(root/'observe2/overlaps.npz')
    t=np.arange(48000)/48000-.5;w=np.sin(np.pi*np.arange(48000)/48000)/np.sqrt(48000)
    errors={k:0. for k in ('model','jacobian','linear_cost','linear_optimality','nonlinear_cost','raw_gradient','overlap_wave','overlap_metric')}
    accepted=0;bounds=0;main_bounds=0;cost_changes=[];correction_checks=[]
    for i,(row,oldrow) in enumerate(zip(actual['local_fits'],parent['observations'])):
        assert row['source_seconds']==oldrow['source_seconds']
        first=round((row['source_seconds'][0]-6)*48000);part=audio[first:first+48000]
        for ch,item in enumerate(row['channels']):
            fit=item['new_fit'];old=oldrow['channels'][ch]['new_fit'];assert fit['original_fit']==old
            original=np.array(old['fitted_parameters']);nominal=np.array(old['nominal_Hz']);m=len(nominal)
            correction=fit['precision_correction'];step=np.array(correction['step'])
            limit=2*nominal/nominal[0];low=np.r_[np.full(m,-.5),-limit,np.full(2*m+1,-np.inf)];high=-low
            before,jac=complex_model(original,nominal,t);same_wave,same_jac=evaluate(original,nominal,t)
            errors['model']=max(errors['model'],float(abs(before-same_wave).max()))
            errors['jacobian']=max(errors['jacobian'],float(abs(jac-same_jac).max()))
            matrix=w[:,None]*jac;residual=w*(before-part[:,ch]);linear=matrix@step+residual;g=matrix.T@linear
            active_low=abs(step-(low-original))<=1e-12;active_high=abs(step-(high-original))<=1e-12
            kkt=g.copy();kkt[active_low]=np.minimum(kkt[active_low],0);kkt[active_high]=np.maximum(kkt[active_high],0)
            kkt_error=float(abs(kkt).max());assert kkt_error<=1.1e-11
            errors['linear_cost']=max(errors['linear_cost'],abs(float(.5*np.dot(linear,linear))-correction['linear_cost']))
            errors['linear_optimality']=max(errors['linear_optimality'],abs(kkt_error-correction['linear_optimality']))
            raw=original+step;assert np.array_equal(raw,np.array(correction['raw_candidate']))
            candidate=np.minimum(high,np.maximum(low,raw));assert np.array_equal(candidate,np.array(correction['projected_candidate']))
            outside=float(max(0.,np.max(low-raw),np.max(raw-high)));assert outside==correction['box_roundoff_violation']
            # Replay the exact cost acceptance rule; compare its waves/costs independently above/below.
            exact_before,_=evaluate(original,nominal,t);exact_after,_=evaluate(candidate,nominal,t)
            old_cost=float(.5*np.dot((w*(exact_before-part[:,ch])),(w*(exact_before-part[:,ch]))))
            new_cost=float(.5*np.dot(w*w,(exact_after-part[:,ch])**2))
            decision=correction['success'] and np.isfinite(candidate).all() and outside<=1e-12 and new_cost<=old_cost
            assert decision==correction['accepted']
            chosen=candidate if decision else original;assert np.array_equal(chosen,np.array(fit['fitted_parameters']))
            predicted,derivative=complex_model(chosen,nominal,t);cost=float(.5*np.dot(w*w,(predicted-part[:,ch])**2))
            errors['nonlinear_cost']=max(errors['nonlinear_cost'],abs(cost-fit['cost']),abs(new_cost-correction['candidate_actual_cost']))
            gradient=derivative.T@(w*w*(predicted-part[:,ch]))
            errors['raw_gradient']=max(errors['raw_gradient'],abs(float(abs(gradient).max())-fit['raw_gradient_infinity']))
            at_bound=(abs(chosen[:m])>=.5-1e-7)|(abs(chosen[m:2*m])>=limit-1e-7)
            assert at_bound.tolist()==fit['at_bound'] and np.all(chosen>=low) and np.all(chosen<=high)
            accepted+=int(decision);bounds+=int(at_bound.sum());main_bounds+=int(at_bound[:3].sum())
            cost_changes.append(100*(1-fit['cost']/old['cost']))
            correction_checks.append(dict(window=i,channel=ch,accepted=bool(decision),BVLS_KKT_error=kkt_error,
                nonlinear_cost_reduction_percent=cost_changes[-1]))
    expected=[(0,1),(1,2),(3,4),(4,5),(6,7),(7,8)];count=0
    assert [(x['left_window'],x['right_window']) for x in actual['unconnected_adjacent_pairs']]==[(2,3),(5,6)]
    for i,(row,pair) in enumerate(zip(actual['observations'],expected)):
        assert (row['left_window'],row['right_window'])==pair
        l=parent['observations'][pair[0]];r=parent['observations'][pair[1]]
        start=max(round(l['source_seconds'][0]*48000),round(r['source_seconds'][0]*48000))
        stop=min(round(l['source_seconds'][1]*48000),round(r['source_seconds'][1]*48000))
        assert (start,stop)==(row['first_sample'],row['stop_sample']) and stop-start==24000
        time=np.arange(start,stop)/48000
        for ch,item in enumerate(row['channels']):
            for j,comparison in enumerate(item['comparisons']):
                assert comparison['main_slot']==j
                for name,source in (('old',parent['observations']),('new',actual['local_fits'])):
                    lf=source[pair[0]]['channels'][ch]['new_fit'];rf=source[pair[1]]['channels'][ch]['new_fit']
                    one,a=independent_line(lf,l['source_seconds'],j,time);two,b=independent_line(rf,r['source_seconds'],j,time)
                    value=comparison[name];assert value['left']==a and value['right']==b
                    errors['overlap_wave']=max(errors['overlap_wave'],float(abs(one-arrays[name+'_left'][i,:,ch,j]).max()),
                        float(abs(two-arrays[name+'_right'][i,:,ch,j]).max()))
                    metrics=independent_metrics(a,b,one,two,time)
                    errors['overlap_metric']=max(errors['overlap_metric'],max(abs(value[k]-v) for k,v in metrics.items()))
                    assert value['phase_defined'] and value['phase_status']=='observed_modulo_integer_cycle_NOT_aligned'
                    count+=1
    assert count==72
    assert errors['model']<1e-10 and errors['jacobian']<1e-9 and errors['linear_cost']<1e-12
    assert errors['linear_optimality']<1e-10 and errors['nonlinear_cost']<1e-12 and errors['raw_gradient']<1e-10
    assert errors['overlap_wave']<1e-10 and errors['overlap_metric']<1e-9
    versions={}
    for name in ('observe1','observe2'):
        for file,digest in load(root/name/'report.json')['sources'].items():
            assert sha(root/name/'exact_sources'/file)==digest
            if name=='observe2':assert sha(repo/file)==digest
            versions.setdefault(file,{})[name]=digest
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/line_motion_v1/local_precision_controls.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='original_failure_precision_repair_all18_corrections_and72_overlap_comparisons_independently_audited',
        actual_report_sha256=sha(actual_path),failed_report_sha256=sha(root/'observe1/report.json'),known_controls_replayed=True,
        source_samples_exact=True,source_versions=versions,errors=errors,corrections=correction_checks,
        counts=dict(local_corrections=18,accepted_corrections=accepted,remaining_bound_components=bounds,
            main_bound_components=main_bounds,overlap_comparisons=72,overlap_sample_pairs=72*24000),
        actual_cost_reduction_percent_range=[min(cost_changes),max(cost_changes)],phase_extracted_real_model_permitted=False,
        limits=['A cost-accepted single linear correction is not a global local-fit convergence certificate',
            'Persistent real overlap disagreement is diagnostic, not quantified true phase error or physical source identity',
            'Shared samples are not independent heldouts; no new DNA, high-frequency recovery, RPM or timbre acceptance'])
    print(json.dumps({k:report[k] for k in ('result','counts','errors','actual_cost_reduction_percent_range')}),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
