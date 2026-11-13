"""Independent complex-basis verification of masked fits and fixed predictions."""
import math
import numpy as np
from native_chirp_audit_v1.wave import near


def check(z,row,nominal,initial_rates):
    audio=z['audio']
    m=len(nominal)
    if not row['lines']:
        assert row['success'] is False and row['reason']=='empty_or_overflow' and (not m or m>64)
        assert z.files==['audio']
        return dict(lines=0,waveform_error=0.,normal_error=0.,optimality_error=0.,cost_error=0.)
    assert audio.shape==(12000,2) and row['training_frames']==9000 and row['check_frames']==3000
    assert row['whole_window_candidate_conditioned'] and row['success']==(row['status']>0) and row['evaluations']<=60
    near(z['nominal'],nominal,0)
    assert len(row['lines'])==m and z['coefficients'].shape==(2*m+1,2)
    time=np.array([(i-6000)/48000 for i in range(12000)])
    mask=np.array([i<9000 for i in range(12000)])
    native_weight=np.sqrt(np.hanning(12001)[:-1]/12000)
    weight=native_weight*mask
    assert np.array_equal(z['training_mask'],mask)
    near(z['weight'],weight,1e-16)
    p=z['parameters']
    co=z['coefficients']
    f=z['nominal']+p[:m]
    q=(p[m:2*m]+p[2*m:])/2
    curvature=(p[2*m:]-p[m:2*m])/.25
    phase=math.tau*(time[:,None]*f+time[:,None]**2*q/2+time[:,None]**3*curvature/6)
    carrier=np.exp(1j*phase)
    design=np.column_stack((carrier.real,carrier.imag,np.ones(12000)))
    output=(carrier@(co[:m]-1j*co[m:2*m])).real+co[-1]
    error=max(near(output,z['reconstructed'],2e-12),near(audio-output,z['residual'],2e-12))
    matrix=weight[:,None]*design
    singular=np.linalg.svd(matrix,compute_uv=False)
    rank=int(sum(singular>singular[0]*max(matrix.shape)*np.finfo(float).eps))
    assert rank==row['rank']
    normal=matrix.T@(weight[:,None]*(output-audio))
    normal_error=near(normal,np.zeros_like(normal),1e-11)
    # The two costs use disjoint raw samples, with no coefficient re-fit on check.
    train_cost=np.array([math.fsum(v*v) for v in (weight[:,None]*(output-audio)).T])
    check_cost=np.array([math.fsum(v*v) for v in (native_weight[:,None]*(~mask)[:,None]*(output-audio)).T])
    cost_error=max(near(train_cost,row['training_cost_LR'],1e-12),near(check_cost,row['check_cost_LR'],1e-12),
        near(train_cost[0]/2,row['cost'],1e-12))
    width=np.full(m,2.)
    if m>1:
        gaps=np.diff(nominal)
        width=np.minimum(width,.45*np.minimum(np.r_[np.inf,gaps],np.r_[gaps,np.inf]))
    near(z['lower'][:m],-width)
    near(z['upper'][:m],width)
    assert np.all(z['lower'][m:]==-500) and np.all(z['upper'][m:]==500)
    near(z['parameters'],np.clip(p,z['lower'],z['upper']),1e-12)
    near(z['initial'][:m],np.zeros(m),0)
    for values in [z['initial'][m:2*m],z['initial'][2*m:]]:near(values,np.clip(initial_rates,-500+1e-6,500-1e-6))
    near(row['frequency_offset_bounds_hz'],width)
    near(row['DC_LR'],co[-1])
    assert row['nonlinear_parameter_count']==3*m and row['eliminated_linear_parameter_count']==2*m+1
    residual=weight*(design@co[:,0]-audio[:,0])
    derivative=-carrier.imag*co[:m,0]+carrier.real*co[m:2*m,0]
    factors=[math.tau*time,.5*math.pi*time*time-math.pi*time**3/(3*.25),
        .5*math.pi*time*time+math.pi*time**3/(3*.25)]
    gradient=np.array([math.fsum(weight*factor*derivative[:,k]*residual) for factor in factors for k in range(m)])
    scale=np.where(gradient<0,z['upper']-p,np.where(gradient>0,p-z['lower'],1.))
    optimality_error=near(max(abs(gradient*scale)),row['optimality'],1e-10)
    amplitudes=np.hypot(co[:m],co[m:2*m])
    powers=.5*np.mean(amplitudes**2,axis=1)
    floor=max(powers)*10**(-42/10)
    for k,line in enumerate(row['lines']):
        assert line['index']==k and line['nominal_hz']==nominal[k]
        near([line['frequency_hz'],line['chirp_hz_per_second'],line['curvature_hz_per_second2']],[f[k],q[k],curvature[k]])
        near(line['rate_endpoints_hz_per_second'],[p[m+k],p[2*m+k]])
        near(line['amplitude_LR'],amplitudes[k])
        near(line['cosine_LR'],co[k])
        near(line['sine_LR'],co[m+k])
        near(line['phase_at_midpoint_LR'],np.arctan2(-co[m+k],co[k]))
        contact=bool(abs(p[k])>=width[k]-1e-7 or abs(p[m+k])>=500-1e-7 or abs(p[2*m+k])>=500-1e-7)
        gate=bool(row['success'] and rank==2*m+1 and not contact and powers[k]>=floor and powers[k]>0)
        assert line['bound_contact']==contact and line['relative_power_ok']==(powers[k]>=floor) and line['training_parameter_gate_ok']==gate
    return dict(lines=m,waveform_error=error,normal_error=normal_error,optimality_error=optimality_error,cost_error=cost_error)
