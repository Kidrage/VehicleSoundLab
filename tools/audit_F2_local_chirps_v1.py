"""Audit native peaks, independent chirp reconstruction and all18 actual local fits."""
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
from line_motion_v1.peak_controls import peak_controls
from line_motion_v1.local_chirps import local_chirps,evaluate

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

def frozen_controls(path,name):
    package=path/'exact_sources/tools/line_motion_v1'
    spec=importlib.util.spec_from_file_location(name,package/'__init__.py',submodule_search_locations=[str(package)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return importlib.import_module(name+'.peak_controls').peak_controls

def independent_chirp(parameters,nominal,time):
    m=len(nominal);f=nominal+parameters[:m];q=parameters[m:2*m]
    z=parameters[2*m:3*m]-1j*parameters[3*m:4*m]
    exponent=np.exp(2j*np.pi*(time[:,None]*f+.5*time[:,None]**2*q))
    values=exponent*z
    wave=values.real.sum(axis=1)+parameters[-1]
    derivative=np.column_stack(((2j*np.pi*time[:,None]*values).real,
        (1j*np.pi*time[:,None]**2*values).real,exponent.real,exponent.imag,np.ones(len(time))))
    return wave,derivative

args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-local-chirps-audit/1',result='running',sources={},real_audio_read=False,
    actual_local_fits_resolved_again=False,shared_phase_clock_fit=False,model_exported=False,runtime_changed=False)
try:
    base=args.workspace/'references/analysis';peaks=base/'F2_native_peaks_v1';root=base/'F2_local_chirps_v1'
    first=load(peaks/'observe1/report.json');second=load(peaks/'observe2/report.json');actual=load(root/'observe1/report.json')
    assert first['result']==second['result']=='failed' and not first['real_audio_read'] and not second['real_audio_read']
    try:frozen_controls(peaks/'observe1','first_frozen_peaks')()
    except AssertionError as exc:assert str(exc)=='No strict local maximum in observation cell; retain failed attempt'
    else:raise AssertionError('Original missing-peak failure did not reproduce')
    same(frozen_controls(peaks/'observe2','second_frozen_peaks')(),second['controls'])
    same(peak_controls(observer=local_chirps),actual['controls'])
    assert actual['controls']['passed'] and not second['controls']['passed']
    numbers=np.load(root/'observe1/observations.npz')
    assert sha(root/'observe1/observations.npz')==actual['arrays_sha256']
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==actual['provenance'] and np.array_equal(audio,numbers['audio'])
    time=np.arange(48000)/48000;hann=np.sin(np.pi*time)**2;local=time-.5
    errors=dict(native_power_relative=0.,waveform=0.,analytic_jacobian=0.,finite_difference_jacobian=0.,
                cost=0.,optimality=0.)
    fit_rows=[];identity_switches=[];complete=0;eligible_count=0
    for i,row in enumerate(actual['observations']):
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000]
        measured=row['measured'];nominal=np.array(row['original_nominal_Hz'])
        order=np.argsort(nominal);mid=(nominal[order][:-1]+nominal[order][1:])/2
        # Direct DTFT of every native bin19..250, including boundary neighbors.
        raw=[]
        for first_bin in range(19,251,24):
            hz=np.arange(first_bin,min(first_bin+24,251))
            kernel=np.exp(-2j*np.pi*hz[:,None]*time)
            raw.append(abs(kernel@(hann[:,None]*part))**2)
        direct=np.concatenate(raw)
        fft=abs(np.fft.rfft(hann[:,None]*part,axis=0))[19:251]**2
        errors['native_power_relative']=max(errors['native_power_relative'],float(abs(direct-fft).max()/max(1,direct.max())))
        for line in range(5):
            for ch in range(2):
                candidates=[]
                for k in range(20,250):
                    label=order[np.searchsorted(mid,k,side='right')]
                    if label==line and direct[k-19,ch]>direct[k-20,ch] and direct[k-19,ch]>direct[k-18,ch]:
                        candidates.append(k)
                candidates.sort(key=lambda k:direct[k-19,ch],reverse=True)
                saved=measured['candidates'][line][ch]
                assert candidates==[x['native_bin_Hz'] for x in saved]
                assert (candidates[0] if candidates else -1)==measured['selected_native_bin_Hz'][line][ch]
        # This is a label for an observation cell, not preserved component identity.
        if measured['selected_native_bin_Hz'][4][0] not in (37,38):
            identity_switches.append(dict(seconds=row['source_seconds'],slot=4,
                original_nominal=float(nominal[4]),selected_bin=measured['selected_native_bin_Hz'][4][0],
                interpretation='37/38Hz observation cell selected a different dominant line; do not call it a heldout37Hz measurement'))
        expected_eligible=np.zeros((5,2),dtype=bool)
        for ch,fit in enumerate(measured['local_chirp_fit']):
            parameters=np.array(fit['fitted_parameters']);selected=np.array(fit['nominal_Hz']);m=len(selected)
            wave,jac=independent_chirp(parameters,selected,local)
            original_wave,original_jac=evaluate(parameters,selected,local)
            errors['waveform']=max(errors['waveform'],float(abs(wave-original_wave).max()))
            errors['analytic_jacobian']=max(errors['analytic_jacobian'],float(abs(jac-original_jac).max()))
            if i==0 and ch==0:
                for j in range(len(parameters)):
                    h=2e-6;plus=parameters.copy();minus=parameters.copy();plus[j]+=h;minus[j]-=h
                    difference=(independent_chirp(plus,selected,local)[0]-independent_chirp(minus,selected,local)[0])/(2*h)
                    errors['finite_difference_jacobian']=max(errors['finite_difference_jacobian'],float(abs(difference-jac[:,j]).max()))
            residual=wave-part[:,ch];weighted=hann/48000
            cost=float(.5*np.dot(weighted,residual**2));gradient=jac.T@(weighted*residual)
            low=np.r_[np.full(m,-.5),np.full(m,-2.),np.full(2*m+1,-np.inf)]
            high=np.r_[np.full(m,.5),np.full(m,2.),np.full(2*m+1,np.inf)]
            assert np.all(parameters>=low) and np.all(parameters<=high)
            distance=np.ones(len(parameters))
            for j,g in enumerate(gradient):
                if g<0 and np.isfinite(high[j]):distance[j]=high[j]-parameters[j]
                elif g>0 and np.isfinite(low[j]):distance[j]=parameters[j]-low[j]
            optimality=float(abs(distance*gradient).max())
            errors['cost']=max(errors['cost'],abs(cost-fit['cost']))
            errors['optimality']=max(errors['optimality'],abs(optimality-fit['optimality']))
            at_bound=(abs(parameters[:m])>=.5-1e-7)|(abs(parameters[m:2*m])>=2-1e-7)
            assert at_bound.tolist()==fit['at_bound']
            used=fit['used_lines'];expected_eligible[used,ch]=fit['success']&~at_bound
            assert np.max(abs(np.array(measured['frequency_Hz'])[used,ch]-selected-parameters[:m]))<1e-12
            assert np.max(abs(np.array(measured['chirp_Hz_per_second'])[used,ch]-parameters[m:2*m]))<1e-12
            fit_rows.append(dict(seconds=row['source_seconds'],channel=ch,cost=cost,optimality=optimality,
                at_bound=at_bound.tolist(),success=fit['success'],evaluations=fit['function_evaluations']))
        assert np.array_equal(expected_eligible,np.array(measured['fit_eligible']))
        assert np.array_equal(expected_eligible,numbers['fit_eligible'][i])
        complete+=int(expected_eligible[:3].all());eligible_count+=int(expected_eligible.sum())
        assert bool(expected_eligible[:3].all())==row['all_anchor_fits_eligible']
    assert errors['native_power_relative']<1e-10 and errors['waveform']<1e-10
    assert errors['analytic_jacobian']<1e-9 and errors['finite_difference_jacobian']<1e-6
    assert errors['cost']<1e-12 and errors['optimality']<1e-10
    assert complete==actual['counts']['complete_anchor_rows']==5
    assert eligible_count==actual['counts']['eligible_frequencies']==62
    diagnostic=load(peaks/'interference2/report.json')
    assert diagnostic['original_direct_exponent_gate_failure_reproduced']
    assert diagnostic['independent_operator_relative_error']<1e-10
    versions={}
    locations={'peak_failure1':peaks/'observe1','peak_failure2':peaks/'observe2',
        'interference_failure':peaks/'interference1','interference':peaks/'interference2','actual':root/'observe1'}
    for name,path in locations.items():
        value=load(path/'report.json')
        for file,digest in value['sources'].items():
            assert sha(path/'exact_sources'/file)==digest
            if name=='actual':assert sha(repo/file)==digest
            versions.setdefault(file,{})[name]=digest
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='native_peak_failures_and_all18_local_chirp_fits_independently_audited',
        actual_report_sha256=sha(root/'observe1/report.json'),replayed_missing_peak_failure=True,
        original_peak_controls_replayed=True,new_chirp_controls_replayed=True,source_samples_exact=True,
        errors=errors,fit_rows=fit_rows,counts=actual['counts'],observation_cell_identity_switches=identity_switches,
        source_versions=versions,shared_phase_qualified=False,RPM_inferred=False,
        limits=['Five rows within numerical fit bounds do not prove constant amplitude/chirp model adequacy or physical period',
            'One observation-cell peak changes to45Hz; its numeric slot is not preserved component identity',
            'All fits are local independent-phase nuisance observations, not an exported Sound DNA model',
            'Four main-line rows hit local frequency/chirp bounds; no bound expansion or missing-row interpolation'])
    print(json.dumps(dict(result=report['result'],counts=actual['counts'],errors=errors,switches=identity_switches)),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
