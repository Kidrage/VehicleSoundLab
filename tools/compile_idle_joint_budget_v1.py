"""Compile coherent RMS and low residual power jointly from one source partition."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from idle_local_partition_v1.power import known,expected,solve
from idle_phase_amplitude_v1.residual import filters
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},assessment=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
try:
    names=['tools/compile_idle_joint_budget_v1.py','tools/idle_local_partition_v1/power.py','tools/idle_local_partition_v1/partition.py',
      'tools/idle_phase_amplitude_v1/residual.py','tools/idle_texture_v2/spectral.py','tools/idle_phase_difference_v1/features.py',
      'tools/idle_positive_power_v1/model.py','tools/research_archive_v1.py','research/idle_local_partition_v1_audio_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    assert load(track(a.audit/'report.json'))['result']=='passed'
    r['known']=known();print(dict(stage='known',results=r['known']),flush=True)
    report=load(track(a.input/'report.json'));parent=a.workspace/'baselines'
    profile=load(track(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    law=load(track(parent/'idle_local_shape_v1/evidence/fit1/report.json'))['law']
    train=next(row for row in report['cases'] if row['label']=='source_train')
    with np.load(track(a.input/train['file'])) as f:residual=f['dynamic_residual'];coefficient=f['variable_coefficients'];ratio=f['stereo_ratio']
    h=filters(residual,[k['band_hz'] for k in profile['kernels'][:2]])
    main=np.sqrt(np.mean(abs(coefficient)**2,axis=0));main=np.column_stack((main,main*abs(ratio)))
    kernels=[dict(taps=h[j].tolist(),band_hz=profile['kernels'][j]['band_hz']) for j in range(2)]
    native_spectra={};low_matrix=None;gains_squared=None
    for part in ['train','check']:
        row=next(v for v in report['cases'] if v['label']=='source_'+part)
        with np.load(track(a.input/row['file'])) as f:z=f['phasors'][21600:122400]
        q=predict(law,matrix(z,hop=1,trim=0));n=len(z)
        low=np.column_stack([expected(taps,np.ones(n))[0] for taps in h])
        upper=np.zeros((9,2));spectra=[]
        for j,kernel in enumerate(profile['kernels'][2:]):
            band,spectrum=expected(kernel['taps'],np.sqrt(q[:,j]));g=kernel['gain']
            upper+=band[:,None]*g*g*np.array([1.,kernel['right_over_left']**2])
            spectra.append(spectrum)
        target=np.array(row['budgets']['dynamic']['residual'])
        if part=='train':
            low_matrix=low[[2,3]];gains_squared=np.column_stack([solve(low_matrix,(target-upper)[[2,3],c]) for c in range(2)])
            for j,kernel in enumerate(kernels):
                kernel.update(gain=float(np.sqrt(gains_squared[j,0])),right_over_left=float(np.sqrt(gains_squared[j,1]/gains_squared[j,0])))
        prediction=upper+low@gains_squared
        native_spectra[part+'_upper_spectra']=np.array(spectra);native_spectra[part+'_q']=q
        r['assessment'].append(dict(part=part,target_residual_power_LR=target.tolist(),predicted_residual_power_LR=prediction.tolist(),
              band_error_dB=(10*np.log10(prediction/target)).tolist(),fixed_upper_power_LR=upper.tolist(),
              lower_unit_power_matrix=low.tolist(),fitted_bands=[2,3],CHECK_used_for_fit=False))
    model=dict(schema='vsl.idle-joint-coherent-residual-budget/1',selected_modes=[1,2,4],main_amplitude_LR=main.tolist(),
         kernels=kernels,gains_squared_LR=gains_squared.tolist(),fit_matrix=low_matrix.tolist(),source_train_seconds=[6,9],
         source_projection_ROI_frames=[21600,122400],original_other10_and_phase_and_high4_preserved=True,
         recorded_trajectory=False,source_main_residual_cross_not_modeled=True,physical_source_separation=False,
         optional_amplitude_model='idle_phase_amplitude_v1_profile',amplitude_phase_independent_hypothesis=True,
         runtime_adopted=False,listening_accepted=False)
    save(a.out/'model.json',model);np.savez_compressed(a.out/'spectra.npz',**native_spectra)
    r.update(result='joint_coherent_and_low_residual_budget_compiled',model_sha256=sha(a.out/'model.json'),
             spectra_sha256=sha(a.out/'spectra.npz'),main_amplitude_LR=main.tolist(),
             old_low_gains=[k['gain'] for k in profile['kernels'][:2]],new_low_gains=[k['gain'] for k in kernels],
             runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],new_main=r['main_amplitude_LR'],old_gains=r['old_low_gains'],new_gains=r['new_low_gains'],
           errors=[(v['part'],v['band_error_dB'][2:4]) for v in r['assessment']]),flush=True)
