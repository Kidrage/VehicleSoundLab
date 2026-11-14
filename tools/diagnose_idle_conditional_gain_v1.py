"""Fixed rejected source parameters only; no refit, fallback, or audible candidate."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from idle_conditional_gain_v1.forward import prepare,response,gains,waveform
from idle_conditional_gain_v1.model import metrics,uncertainty

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_diagnosis.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),cases=[])
source=load(a.input/'report.json');model=source['models']['source']
assert source['result']=='native_conditional_mean_fitted_pending_audit' and not model['conditional']['available']
assert model['conditional']['success'] and model['conditional']['active_mask'].count(-1)==3
plan=repo/'research/idle_conditional_gain_v1_diagnosis_plan.json';shutil.copy2(plan,a.out/plan.name);r['plan_sha256']=sha(plan)
try:
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    freq=np.array(profile['modal']['frequencies_hz'])
    for part in ['train','check']:
        file=Path(model['source_file']).with_name('source_'+part+'.npz')
        assert source['inputs'][str(file)]==sha(file) if str(file) in source['inputs'] else file.is_file()
        with np.load(file) as f:z=f['phasors'];target=f['local_coefficients'][:,[1,2,4]]
        q=prepare(freq,z,np.array(model['TRAIN_beta']),model['conditional']['center'])
        arrays=dict(frequencies=freq,phasors=z,beta=np.array(model['TRAIN_beta']),center=q['center'],target=target)
        scores={};native={};interior={}
        for key in ['constant','conditional']:
            prediction=response(q,model[key]['parameters']);g=gains(model[key]['parameters'],q['x'])
            arrays[key+'_prediction']=prediction;arrays[key+'_gain']=g;arrays[key+'_audio']=waveform(q,model[key]['parameters'])
            scores[key]=metrics(target,prediction);e=prediction-target
            scores[key]['real_MSE']=np.mean(e.real**2,axis=0).tolist()
            scores[key]['imag_MSE']=np.mean(e.imag**2,axis=0).tolist()
            native[key]=np.column_stack((g.min(axis=0),g.max(axis=0))).tolist()
            inside=g[12000:-12000]
            interior[key]=np.column_stack((inside.min(axis=0),inside.max(axis=0))).tolist()
        arrays['error_covariance_signed_lags']=uncertainty(arrays['conditional_prediction']-target)
        out=a.out/('source_'+part+'.npz');np.savez_compressed(out,**arrays)
        base=np.array(scores['constant']['complex_MSE']);new=np.array(scores['conditional']['complex_MSE'])
        r['cases'].append(dict(family='source',part=part,file=out.name,sha256=sha(out),original_file=str(file),original_sha256=sha(file),
            metrics=scores,fractional_complex_MSE_reduction=(1-new/base).tolist(),native_gain_range=native,interior_gain_range=interior,
            model_available=False,diagnostic_only=True))
        del q
    r.update(result='rejected_source_fixed_diagnosis',bounds_or_parameters_changed=False,refit=False,
        new_source_voice_or_audition=False,latent_amplitude_covariance_identified=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
