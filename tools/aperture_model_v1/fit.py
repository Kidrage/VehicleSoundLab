"""Joint waveform parameters and common phase through exact finite windows."""
import numpy as np
from scipy.optimize import least_squares
from .basis import spline
from .forward import Aperture,real_rows


class Model:
    def __init__(self,time,plan):
        self.time=time
        self.orders=np.asarray(plan['source_orders'])
        self.phase_basis=spline(time,plan['cycles'],plan['phase_knot_cycles'])
        self.envelope_basis=spline(time,plan['cycles'],plan['amplitude_knot_cycles'])
        self.aperture=Aperture(len(time),plan)
        self.parts=len(self.orders)
        self.phase_count=self.phase_basis.shape[1]
        self.envelope_count=self.envelope_basis.shape[1]
        self.parameter_count=2*self.parts+self.phase_count+self.parts*self.envelope_count

    def samples(self,parameters,jacobian=False):
        count=self.parts
        a=parameters[:count]
        b=parameters[count:2*count]
        p=parameters[2*count:2*count+self.phase_count]
        beta=parameters[2*count+self.phase_count:].reshape(count,self.envelope_count)
        phase=self.phase_basis@p
        envelope=1+self.envelope_basis@beta.T
        angle=2*np.pi*(self.time[:,None]+phase[:,None])*self.orders[None,:]
        cosine=np.cos(angle)
        sine=np.sin(angle)
        partial=envelope*(cosine*a+sine*b)
        result=partial.sum(axis=1)
        if not jacobian:
            return result,phase,envelope
        slope=(envelope*2*np.pi*self.orders*(-sine*a+cosine*b)).sum(axis=1)
        derivative=np.column_stack((envelope*cosine,envelope*sine,slope[:,None]*self.phase_basis,
            (partial[:,:,None]/envelope[:,:,None]*self.envelope_basis[:,None,:]).reshape(len(self.time),-1)))
        return result,derivative

    def prediction(self,parameters,jacobian=False):
        if not jacobian:
            return real_rows(self.aperture.apply(self.samples(parameters)[0]))
        samples,derivative=self.samples(parameters,True)
        projected=self.aperture.apply(np.column_stack((samples,derivative)))
        return real_rows(projected[:,0]),real_rows(projected[:,1:])


def estimate(audio,time,plan):
    model=Model(time,plan)
    target=real_rows(model.aperture.apply(audio[:,0]))
    zero=np.zeros(model.parameter_count)
    _,linear=model.prediction(zero,True)
    zero[:2*model.parts]=np.linalg.lstsq(linear[:,:2*model.parts],target,rcond=None)[0]
    lower=np.full(model.parameter_count,-plan['amplitude_control_bound'])
    upper=-lower
    lower[:2*model.parts]=-1
    upper[:2*model.parts]=1
    lower[2*model.parts:2*model.parts+model.phase_count]=-plan['phase_control_bound_cycles']
    upper[2*model.parts:2*model.parts+model.phase_count]=plan['phase_control_bound_cycles']
    cache={}
    def calculate(parameters):
        if 'parameters' not in cache or not np.array_equal(parameters,cache['parameters']):
            prediction,jacobian=model.prediction(parameters,True)
            cache.update(parameters=parameters.copy(),residual=prediction-target,jacobian=jacobian)
        return cache
    # scipy's robust-loss scaling can modify both arrays in place. Preserve
    # the raw cache for subsequent calls and final residual diagnostics.
    fitted=least_squares(lambda x:calculate(x)['residual'].copy(),zero,jac=lambda x:calculate(x)['jacobian'].copy(),
        bounds=(lower,upper),loss='soft_l1',f_scale=plan['soft_l1_scale'],x_scale='jac',
        max_nfev=plan['maximum_evaluations'],ftol=1e-10,xtol=1e-10,gtol=1e-10)
    _,phase,envelope=model.samples(fitted.x)
    jacobian=calculate(fitted.x)['jacobian']
    norms=np.linalg.norm(jacobian,axis=0)
    singular=np.linalg.svd(jacobian/np.maximum(norms,1e-30),compute_uv=False)
    return phase,dict(success=bool(fitted.success),status=int(fitted.status),message=fitted.message,
        evaluations=int(fitted.nfev),parameters=model.parameter_count,
        normalized_projection_residual=float(np.linalg.norm(calculate(fitted.x)['residual'])/max(np.linalg.norm(target),1e-30)),
        minimum_envelope=float(envelope.min()),maximum_envelope=float(envelope.max()),
        minimum_phase_derivative=float(min(1+np.diff(phase)*plan['samples_per_cycle'])),
        scaled_jacobian_condition=float(singular[0]/max(singular[-1],1e-30)),
        identifiability='Local scaled Jacobian diagnostic only; no calibrated real-source uncertainty'),fitted.x
