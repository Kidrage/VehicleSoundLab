"""Independent complex construction and QR checks of all72 conditional subspaces."""
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
from line_motion_v1.sideband_subspace_controls import controls


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


def matrices(f,q,central,t):
    z=np.column_stack([np.exp(2j*np.pi*(hz*t+.5*rate*t*t)) for hz,rate in zip(f,q)])
    base=np.column_stack([z[:,j].real for j in range(len(f))]+[z[:,j].imag for j in range(len(f))]+[np.ones(len(t))])
    v=z*central
    # Real/imaginary parts of complex sum/difference produce cosine/sine modulation.
    rotation=np.exp(2j*np.pi*3*t[:,None]);cosine=(rotation+np.conj(rotation))/2;sine=(rotation-np.conj(rotation))/(2j)
    a=np.column_stack(((v*cosine).real,(v*sine).real))
    qcols=np.column_stack(((1j*v*cosine).real,(1j*v*sine).real))
    return dict(base=base,amplitude=np.column_stack((base,a)),quadrature=np.column_stack((base,qcols)),joint=np.column_stack((base,a,qcols)))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-sideband-subspaces-audit/1',result='running',sources={},real_audio_read=False,
    independent_linear_QR_check=True,nonlinear_fit_run=False,shared_phase_clock_fit=False,model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_sideband_v1';actual=load(root/'subspaces1/report.json');parent=load(root/'observe1/report.json')
    assert actual['controls']['passed'];same(controls(),actual['controls'])
    assert actual['parent_report_sha256']==sha(root/'observe1/report.json')
    arrays=np.load(root/'subspaces1/subspaces.npz');full=np.load(root/'observe1/observations.npz')
    assert sha(root/'subspaces1/subspaces.npz')==actual['arrays_sha256']
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==actual['provenance']==parent['provenance'] and np.array_equal(audio,full['audio'])
    t=np.arange(48000)/48000-.5;weight=np.sin(np.pi*(t+.5))/np.sqrt(48000)
    errors=dict(waveform=0.,coefficients_QR=0.,cost=0.,gradient=0.,singular=0.,joint_equivalence=0.)
    rows=[];wins=0;projection_count=0;conditions=[]
    for i,row in enumerate(actual['observations']):
        assert row['source_seconds']==parent['observations'][i]['source_seconds']
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000];channels=[]
        for ch,item in enumerate(row['channels']):
            original=parent['observations'][i]['fits'][ch]['parent_fit'];p0=np.array(original['fitted_parameters']);nominal=np.array(original['nominal_Hz']);m=len(nominal)
            assert item['parent_main_at_bound']==original['at_bound'][:3]
            central=p0[2*m:3*m]-1j*p0[3*m:4*m];costs={}
            for name,matrix in matrices(nominal+p0[:m],p0[m:2*m],central,t).items():
                fitted=item['models'][name];coeff=np.array(fitted['coefficients']);a=weight[:,None]*matrix
                orthogonal,upper=np.linalg.qr(a,mode='reduced');qr=np.linalg.solve(upper,orthogonal.T@(weight*part[:,ch]))
                singular=np.linalg.svd(upper,compute_uv=False);rank=int(np.sum(singular>singular[0]*max(a.shape)*np.finfo(float).eps))
                assert rank==fitted['rank']==fitted['columns']==matrix.shape[1]
                assert abs(singular[0]/singular[-1]-fitted['condition'])<1e-9
                predicted=matrix@coeff;residual=predicted-part[:,ch];cost=float(.5*np.dot(weight**2,residual**2))
                gradient=float(abs(matrix.T@(weight**2*residual)).max());assert gradient<1e-10
                errors['waveform']=max(errors['waveform'],float(abs(predicted-arrays[name][i,:,ch]).max()))
                errors['coefficients_QR']=max(errors['coefficients_QR'],float(abs(qr-coeff).max()))
                errors['cost']=max(errors['cost'],abs(cost-fitted['cost']))
                errors['gradient']=max(errors['gradient'],abs(gradient-fitted['gradient_infinity']))
                errors['singular']=max(errors['singular'],float(abs(singular-np.array(fitted['singular_values'])).max()))
                if name=='joint':errors['joint_equivalence']=max(errors['joint_equivalence'],float(abs(predicted-full['after'][i,:,ch]).max()))
                costs[name]=cost;conditions.append(fitted['condition']);projection_count+=1
            assert item['models']['amplitude']['columns']==item['models']['quadrature']['columns']==4*m+1
            for name in ('amplitude','quadrature','joint'):
                assert abs(item[name+'_reduction_percent']-100*(1-costs[name]/costs['base']))<1e-10
            assert costs['joint']<=min(costs['amplitude'],costs['quadrature'])+1e-12
            channels.append(dict(channel=ch,amplitude_reduction_percent=item['amplitude_reduction_percent'],
                quadrature_reduction_percent=item['quadrature_reduction_percent'],joint_reduction_percent=item['joint_reduction_percent'],
                quadrature_lower_training_cost=costs['quadrature']<costs['amplitude']))
        wins+=int(all(c['quadrature_lower_training_cost'] for c in channels));rows.append(dict(source_seconds=row['source_seconds'],channels=channels))
    assert errors['waveform']<1e-10 and errors['coefficients_QR']<1e-10 and errors['cost']<1e-12
    assert errors['gradient']<1e-12 and errors['singular']<1e-10 and errors['joint_equivalence']<1e-10
    for file,digest in actual['sources'].items():assert sha(repo/file)==sha(root/'subspaces1/exact_sources'/file)==digest
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/line_motion_v1/sideband_subspace_controls.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='all72_equal_dimension_conditional_subspace_projections_independently_QR_audited',
        actual_report_sha256=sha(root/'subspaces1/report.json'),parent_report_sha256=sha(root/'observe1/report.json'),controls_replayed=True,
        source_samples_exact=True,errors=errors,comparisons=rows,condition_range=[min(conditions),max(conditions)],
        counts=dict(projections=projection_count,quadrature_lower_training_cost_windows=wins,windows=9,physical_AM_FM_classifications=0),
        phase_extracted_real_model_permitted=False,RPM_inferred=False,
        limits=['Nine conditional Q-only wins are not nine independent recordings or a physical FM conclusion',
            'Existing input frequency/chirp errors and parent boundaries can create quadrature-like residuals',
            'Spaces are not necessarily orthogonal; separate training reductions are not additive source energies',
            'No high-frequency reconstruction, realtime DNA or subjective timbre acceptance'])
    print(json.dumps({k:report[k] for k in ('result','counts','condition_range','errors')}),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
