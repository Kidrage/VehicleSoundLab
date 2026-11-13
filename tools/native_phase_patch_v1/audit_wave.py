"""Independent physical-coordinate reconstruction of saved cubic patches."""
import math
import numpy as np
from native_chirp_audit_v1.wave import near


def check(z,row,plan):
    x=z['audio']
    p=z['parameters']
    nominal=z['nominal']
    co=z['coefficients']
    n,m=len(x),len(nominal)
    assert x.shape==(12000,2) and len(p)==3*m and co.shape==(2*m+1,2)
    assert row['success']==(row['status']>0) and row['evaluations']<=60
    duration=n/48000
    t=np.array([(i-n/2)/48000 for i in range(n)])
    f=nominal+p[:m]
    q=(p[m:2*m]+p[2*m:])/2
    curvature=(p[2*m:]-p[m:2*m])/duration
    angle=math.tau*(t[:,None]*f+.5*t[:,None]**2*q+t[:,None]**3*curvature/6)
    complex_basis=np.exp(1j*angle)
    waveform=(complex_basis@(co[:m]-1j*co[m:2*m])).real+co[-1]
    error=max(near(waveform,z['reconstructed'],2e-12),near(x-waveform,z['residual'],2e-12))
    cosine,sine=complex_basis.real,complex_basis.imag
    design=np.column_stack((cosine,sine,np.ones(n)))
    window=.5-.5*np.cos(math.tau*np.arange(n)/n)
    w=np.sqrt(window/n)
    weighted=w[:,None]*design
    singular=np.linalg.svd(weighted,compute_uv=False)
    assert sum(singular>singular[0]*max(design.shape)*np.finfo(float).eps)==row['rank']
    normals=weighted.T@(w[:,None]*(design@co-x))
    normal_error=near(normals,np.zeros_like(normals),1e-11)
    residual=w*(design@co[:,0]-x[:,0])
    near(.5*math.fsum(residual**2),row['cost'],1e-12)
    factors=[math.tau*t,.5*math.pi*t*t-math.pi*t**3/(3*duration),.5*math.pi*t*t+math.pi*t**3/(3*duration)]
    derivative=-sine*co[:m,0]+cosine*co[m:2*m,0]
    gradient=np.array([math.fsum(w*factor*derivative[:,j]*residual) for factor in factors for j in range(m)])
    scale=np.where(gradient<0,z['upper']-p,np.where(gradient>0,p-z['lower'],1.))
    optimality_error=near(max(abs(gradient*scale)),row['optimality'],1e-10)
    near(row['weighted_relative_residual_LR'],np.linalg.norm(w[:,None]*(x-waveform),axis=0)/np.linalg.norm(w[:,None]*x,axis=0))
    width=np.full(m,2.)
    if m>1:
        gaps=np.diff(nominal)
        width=np.minimum(width,.45*np.minimum(np.r_[np.inf,gaps],np.r_[gaps,np.inf]))
    near(z['lower'][:m],-width)
    near(z['upper'][:m],width)
    assert np.all(z['lower'][m:]==-500) and np.all(z['upper'][m:]==500)
    near(p,np.minimum(np.maximum(p,z['lower']),z['upper']),1e-12)
    near(row['frequency_offset_bounds_hz'],width)
    near(row['DC_LR'],co[-1])
    assert row['nonlinear_parameter_count']==3*m and row['eliminated_linear_parameter_count']==2*m+1
    amp=np.hypot(co[:m],co[m:2*m])
    power=.5*np.mean(amp**2,axis=1)
    floor=max(power)*10**(-42/10)
    hz=np.fft.rfftfreq(n,1/48000)
    # Ratios use the saved residual after its independent waveform verification.
    zr=np.fft.rfft(z['residual']*window[:,None],axis=0)
    support_error=0.
    for k,line in enumerate(row['lines']):
        near([line['frequency_hz'],line['chirp_hz_per_second'],line['curvature_hz_per_second2']],[f[k],q[k],curvature[k]])
        near(line['rate_endpoints_hz_per_second'],[p[m+k],p[2*m+k]])
        near(line['amplitude_LR'],amp[k])
        near(line['cosine_LR'],co[k])
        near(line['sine_LR'],co[m+k])
        near(line['phase_at_midpoint_LR'],np.arctan2(-co[m+k],co[k]))
        times=[-duration/2,duration/2]
        if curvature[k] and -duration/2<=-q[k]/curvature[k]<=duration/2:times.append(-q[k]/curvature[k])
        extent=max(abs(q[k]*at+.5*curvature[k]*at*at) for at in times)+8
        near(extent,line['support_extent_hz'])
        chosen=(hz>=f[k]-extent)&(hz<=f[k]+extent)
        stem=cosine[:,k,None]*co[k]+sine[:,k,None]*co[m+k]
        zl=np.fft.rfft(stem*window[:,None],axis=0)
        before=np.sum(abs((zr+zl)[chosen])**2,axis=0)
        after=np.sum(abs(zr[chosen])**2,axis=0)
        support=1-np.divide(after,before,out=np.ones(2),where=before>0)
        support_error=max(support_error,near(support,line['local_explained_fraction_LR'],1e-9))
        contact=bool(abs(p[k])>=width[k]-1e-7 or abs(p[m+k])>=500-1e-7 or abs(p[2*m+k])>=500-1e-7)
        eligible=bool(row['success'] and row['rank']==2*m+1 and not contact and power[k]>=floor and power[k]>0 and min(support)>=.8)
        assert line['bound_contact']==contact and line['relative_power_ok']==(power[k]>=floor) and line['eligible']==eligible
    return dict(waveform_error=error,support_error=support_error,normal_error=normal_error,optimality_error=optimality_error)
