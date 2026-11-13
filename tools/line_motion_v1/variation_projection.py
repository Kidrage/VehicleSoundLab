"""Fixed rank-one descriptions of local frequency disagreement; no physical classifier."""
import numpy as np


def frequency_disagreement(left,right,time):
    return np.column_stack([r['frequency_Hz']+r['chirp_Hz_per_s']*(time-r['centre_seconds'])
        -l['frequency_Hz']-l['chirp_Hz_per_s']*(time-l['centre_seconds']) for l,r in zip(left,right)])


def project(disagreement,vector):
    d=np.asarray(disagreement,dtype=float);v=np.asarray(vector,dtype=float)
    assert d.ndim==2 and d.shape[1]==3 and v.shape==(3,) and np.all(v>0) and np.isfinite(d).all()
    coefficient=d@v/np.dot(v,v);prediction=coefficient[:,None]*v;residual=d-prediction
    total=float(np.sum(d*d));rest=float(np.sum(residual*residual))
    omitted=np.empty_like(d)
    for j in range(3):
        used=np.arange(3)!=j
        omitted[:,j]=v[j]*(d[:,used]@v[used])/np.dot(v[used],v[used])
    error=d-omitted
    return dict(vector=v.tolist(),raw_disagreement_squared_sum_Hz2=total,residual_squared_sum_Hz2=rest,
        residual_squared_fraction=None if total==0 else rest/total,
        per_line_rms_Hz=np.sqrt(np.mean(d*d,axis=0)).tolist(),
        omitted_line_prediction_rms_error_Hz=np.sqrt(np.mean(error*error,axis=0)).tolist(),
        omitted_line_prediction_max_error_Hz=abs(error).max(axis=0).tolist(),
        omitted_line_comparison='conditional_shared_joint_fit_NOT_independent_heldout',
        interpretation='geometric_description_of_model_disagreement_NOT_physical_source_energy_or_clock'),prediction,omitted


def observe(disagreement):
    reports={};arrays={}
    for name,vector in (('harmonic_hypothesis',[2,3,5]),('equal_Hz',[1,1,1])):
        reports[name],arrays[name],arrays[name+'_omitted']=project(disagreement,vector)
    return reports,arrays
