"""Independent explicit three-entry audit of all12 fixed variation observations."""
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
from line_motion_v1.variation_projection_controls import fixtures,controls


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def same(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for key in a:same(a[key],b[key])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,float):assert abs(a-b)<1e-9
    else:assert a==b


def scalar_formula(d,name):
    x,y,z=d.T
    if name=='harmonic_hypothesis':
        g=(2*x+3*y+5*z)/38;model=np.column_stack((2*g,3*g,5*g))
        omitted=np.column_stack((2*(3*y+5*z)/34,3*(2*x+5*z)/29,5*(2*x+3*y)/13))
    else:
        assert name=='equal_Hz';g=(x+y+z)/3;model=np.column_stack((g,g,g))
        omitted=np.column_stack(((y+z)/2,(x+z)/2,(x+y)/2))
    return model,omitted


def metrics(d,model,omitted):
    count=len(d);total=sum(float(np.dot(d[:,j],d[:,j])) for j in range(3))
    residual=d-model;error=d-omitted;remaining=sum(float(np.dot(residual[:,j],residual[:,j])) for j in range(3))
    return dict(raw_disagreement_squared_sum_Hz2=total,residual_squared_sum_Hz2=remaining,
        residual_squared_fraction=None if total==0 else remaining/total,
        per_line_rms_Hz=[float(np.linalg.norm(d[:,j])/np.sqrt(count)) for j in range(3)],
        omitted_line_prediction_rms_error_Hz=[float(np.linalg.norm(error[:,j])/np.sqrt(count)) for j in range(3)],
        omitted_line_prediction_max_error_Hz=[float(abs(error[:,j]).max()) for j in range(3)])


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-variation-projection-audit/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False,real_nonlinear_resolves=0)
try:
    root=args.workspace/'references/analysis/F2_variation_projection_v1';actual_path=root/'observe1/report.json';actual=load(actual_path)
    checked=controls();same(checked,actual['controls']);assert checked['passed']
    u=np.arange(72000)/48000-.75;known_error=0.
    for case in fixtures():
        r=.24 if case['id']=='common_cubic' else 0.
        source=sum((a*np.exp(1j*p)*np.exp(2j*np.pi*(k*37.6*u+.5*k*.3*u*u+k*r*u**3/6))).real
            for a,p,k in zip((.5,.4,.3),(.2,.5,.8),(2,3,5)))
        source+=(.18*np.exp(.1j)*np.exp(2j*np.pi*(82.3*u-.1*u*u))).real
        if case['id']=='independent_neighbor':source+=(.08*np.exp(.7j)*np.exp(2j*np.pi*78.2*u)).real
        known_error=max(known_error,float(abs(source-case['audio']).max()))
    assert known_error<1e-10
    # Both known descriptive signatures and exact operator controls checked with explicit formulas.
    known_metric_error=0.
    for case in checked['cases']:
        time=np.arange(24000,48000)/48000;d=[]
        for j in range(3):
            lf,rf=case['fits'];l=np.array(lf['fitted_parameters']);r=np.array(rf['fitted_parameters']);m=4
            intercept=rf['nominal_Hz'][j]+r[j]-r[m+j]*1.-lf['nominal_Hz'][j]-l[j]+l[m+j]*.5
            d.append(intercept+(r[m+j]-l[m+j])*time)
        d=np.column_stack(d)
        for name in ('harmonic_hypothesis','equal_Hz'):
            model,omitted=scalar_formula(d,name);found=metrics(d,model,omitted);measured=case['observations'][name]
            for key,value in found.items():known_metric_error=max(known_metric_error,float(np.max(abs(np.array(value)-np.array(measured[key])))))
    assert known_metric_error<1e-9
    parent_root=args.workspace/'references/analysis/F2_overlap_phase_v1';parent_path=parent_root/'observe2/report.json';parent=load(parent_path)
    assert actual['parent_report_sha256']==sha(parent_path)
    assert actual['parent_audit_sha256']==sha(parent_root/'audit1/report.json')
    ancestor=args.workspace/'references/analysis/F2_rate_coordinates_v1/observe1'
    assert actual['ancestor_report_sha256']==parent['parent_report_sha256']==sha(ancestor/'report.json')
    assert actual['ancestor_arrays_sha256']==parent['parent_arrays_sha256']==sha(ancestor/'observations.npz')
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==actual['provenance']==parent['provenance']
    source_arrays=np.load(ancestor/'observations.npz');assert np.array_equal(audio,source_arrays['audio'])
    arrays=np.load(root/'observe1/projections.npz');assert sha(root/'observe1/projections.npz')==actual['arrays_sha256']
    errors=dict(frequency_disagreement=0.,projection=0.,omitted_prediction=0.,metric=0.)
    observations=0;projections=0;omitted_lines=0;comparisons=[]
    assert len(actual['observations'])==len(parent['observations'])==6
    for i,(row,old) in enumerate(zip(actual['observations'],parent['observations'])):
        for key in ('left_window','right_window','first_sample','stop_sample','source_overlap_seconds'):assert row[key]==old[key]
        time=np.arange(row['first_sample'],row['stop_sample'])/48000
        assert len(time)==24000
        for ch,(channel,parent_channel) in enumerate(zip(row['channels'],old['channels'])):
            assert channel['channel']==ch and channel['left']==[x['new']['left'] for x in parent_channel['comparisons']]
            assert channel['right']==[x['new']['right'] for x in parent_channel['comparisons']]
            d=[]
            for l,r in zip(channel['left'],channel['right']):
                intercept=r['frequency_Hz']-r['chirp_Hz_per_s']*r['centre_seconds']-l['frequency_Hz']+l['chirp_Hz_per_s']*l['centre_seconds']
                d.append(intercept+(r['chirp_Hz_per_s']-l['chirp_Hz_per_s'])*time)
            d=np.column_stack(d);errors['frequency_disagreement']=max(errors['frequency_disagreement'],float(abs(d-arrays['disagreement'][i,:,ch,:]).max()))
            fractions={};rms={}
            for name in ('harmonic_hypothesis','equal_Hz'):
                model,omitted=scalar_formula(d,name);result=metrics(d,model,omitted);record=channel['observations'][name]
                errors['projection']=max(errors['projection'],float(abs(model-arrays[name][i,:,ch,:]).max()))
                errors['omitted_prediction']=max(errors['omitted_prediction'],float(abs(omitted-arrays[name+'_omitted'][i,:,ch,:]).max()))
                for key,value in result.items():
                    errors['metric']=max(errors['metric'],float(np.max(abs(np.array(value)-np.array(record[key])))))
                expected=[2.,3.,5.] if name=='harmonic_hypothesis' else [1.,1.,1.]
                assert record['vector']==expected and record['omitted_line_comparison']=='conditional_shared_joint_fit_NOT_independent_heldout'
                # Projection orthogonality and exact omitted-line exclusion checked independently.
                assert np.max(abs((d-model)@np.array(expected)))<1e-10
                fractions[name]=record['residual_squared_fraction'];rms[name]=record['omitted_line_prediction_rms_error_Hz']
                projections+=1;omitted_lines+=3
            comparisons.append(dict(pair=[row['left_window'],row['right_window']],channel=ch,
                residual_squared_fractions=fractions,conditional_omitted_line_rms_error_Hz=rms))
            observations+=1
    assert max(errors.values())<1e-9
    for file,digest in actual['sources'].items():assert sha(repo/file)==sha(root/'observe1/exact_sources'/file)==digest
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/line_motion_v1/variation_projection_controls.py'):
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='known_sources_and_all12groups24projections72conditional_predictions_independently_audited',
        actual_report_sha256=sha(actual_path),known_controls_replayed=True,known_complex_source_error=known_error,
        known_scalar_metric_error=known_metric_error,source_samples_exact=True,errors=errors,
        counts=dict(three_line_observations=observations,rank_one_projections=projections,
            conditional_omitted_line_predictions=omitted_lines,native_frequency_differences=12*24000*3),
        comparisons=comparisons,physical_source_classifications=0,phase_extracted_real_model_permitted=False,
        limits=['All6pairs favor the predeclared2/3/5 geometry over equal-Hz; this is a descriptive comparison without physical orders or source identity',
            'Independent proportional phase programs can produce the same waveform as a shared expression',
            'Parent fits share samples and nuisance parameters; conditional omitted-line predictions are not independent validation',
            'No real nonlinear fit, common phase recovery, RPM, new DNA, high-frequency recovery or timbre acceptance'])
    print(json.dumps({k:report[k] for k in ('result','counts','errors','known_complex_source_error','known_scalar_metric_error')}),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
