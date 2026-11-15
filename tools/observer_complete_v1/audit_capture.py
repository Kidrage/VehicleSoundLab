"""Per-mean weak-band, full signed-Gram and partition audit helpers."""
import numpy as np
from circular_phase_lift_v1.audit_oracle import statistics


def compare(measured,z,report):
    def check(name,x,y,scale=1.,gate=2e-9):
        err=float(np.max(abs(x-y)/scale));assert err<gate,(name,err)
        report['maximum_errors'][name]=max(err,report['maximum_errors'].get(name,0.))
    check('coefficients',measured['coefficients'],z['coefficients'],gate=2e-10)
    for prefix,pk,ck in (('line','power','cross'),('broad','broadband_power','broadband_cross')):
        truth=statistics(measured[pk],measured[ck]);mean=truth['mean']
        channel=np.maximum(mean,1e-24);cross=np.maximum(np.sqrt(mean[::2]*mean[1::2]),1e-24)
        joint=np.maximum(mean[::2]+mean[1::2],1e-24)
        covariance=np.maximum(mean[:,None]*mean[None,:],1e-24)
        check('raw_'+pk,measured[pk],z[pk],channel[None])
        check('raw_'+ck,measured[ck],z[ck],cross[None])
        for field,scale in dict(mean=channel,CV=1.,complex_coherence=1.,covariance=covariance,
                lag_covariance=covariance[None],mid_power=joint,side_power=joint).items():
            check(prefix+'_'+field,truth[field],z[prefix+'_'+field],scale)
        for field in ('power_defined','coherence_defined'):assert np.array_equal(truth[field],z[prefix+'_'+field])
        if prefix+'_Gram' not in z:continue
        m=measured[prefix+'_Gram'];ref=np.maximum(np.diagonal(m,axis1=-2,axis2=-1).real.sum(axis=-1).max(axis=0),1e-24)
        check(prefix+'_Gram',m,z[prefix+'_Gram'],ref[None,:,None,None],2e-10)
        report['band_Gram_matrices']+=len(m)*m.shape[1]
        avg=m.mean(axis=0);B=m.shape[1]
        diagonal=np.diagonal(avg,axis1=-2,axis2=-1).real.reshape(B,6,2)
        low=diagonal[:,0]
        rest=np.array([[sum(avg[b,2*g+c,2*h+c].real for g in range(1,6) for h in range(1,6)) for c in (0,1)] for b in range(B)])
        signed=np.array([[2*sum(avg[b,c,2*h+c].real for h in range(1,6)) for c in (0,1)] for b in range(B)])
        total=low+rest+signed
        lr=np.array([sum(avg[b,2*g,2*h+1] for g in range(6) for h in range(6)) for b in range(B)])
        for field,value in dict(group_self_power=diagonal,low_power=low,rest_power=rest,
                signed_low_rest_cross=signed,total_power=total,signed_all_group_cross=total-diagonal.sum(axis=1),complex_LR=lr).items():
            denominator=ref[:,None,None] if field=='group_self_power' else ref if field=='complex_LR' else ref[:,None]
            check(prefix+'_group_'+field,value,z[prefix+'_group_'+field],denominator)
        slices=np.array_split(np.arange(len(measured[pk])),3)
        assert np.array_equal(z['chunk_rows'],[len(s) for s in slices])
        for j,indices in enumerate(slices):
            part=statistics(measured[pk][indices],measured[ck][indices])
            for field in ('mean','CV','complex_coherence'):
                denominator=np.maximum(part['mean'],1e-24) if field=='mean' else 1.
                check('chunks_'+prefix+'_'+field,part[field],z['chunks_'+prefix+'_'+field][j],denominator)
    if 'all_frequency_Gram' in z:
        norm=max(float(abs(measured['time_energy_Gram']).max()),1e-24)
        for key in ('all_frequency_Gram','time_energy_Gram'):check(key,measured[key],z[key],norm)
        check('Parseval',measured['all_frequency_Gram'].real,measured['time_energy_Gram'],norm)
