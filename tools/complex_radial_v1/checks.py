"""Independent derivatives, complex rotations and small analytic constrained QPs."""
from types import SimpleNamespace
import numpy as np
from absolute_amplitude_v1.amplitude import cost as scalar_cost
from .loss import cost,gradient,hessian_apply,quadratic
from .quadratic import solve


def rotate(values,angle):
    m=len(values)//2;c=np.cos(angle);s=np.sin(angle)
    return np.concatenate((c*values[:m]-s*values[m:],s*values[:m]+c*values[m:]),axis=0)


def controls(settings):
    scale=.0002;r=scale*np.array([0.,.3,3.,-4.,0.,-.7,.5,2.])
    angle=.37;turned=rotate(r,angle);rng=np.random.default_rng(128042)
    matrix=rng.normal(0,.001,(len(r),5));g=gradient(r,scale)
    identity=np.eye(len(r));h=hessian_apply(r,identity,scale)
    root=hessian_apply(r,identity,scale,.5)
    invariant=dict(cost=abs(cost(r,scale)-cost(turned,scale)),
        gradient=float(abs(rotate(g,angle)-gradient(turned,scale)).max()),
        hessian=float(abs(rotate(hessian_apply(r,matrix,scale),angle)-hessian_apply(turned,rotate(matrix,angle),scale)).max()),
        square_root=float(abs(root@root-h).max()),zero_hessian=float(abs(hessian_apply(np.zeros(4),np.eye(4),scale)-np.eye(4)).max()))
    directions=rng.normal(size=(3,len(r)));derivatives=[]
    for direction in directions:
        direction/=np.linalg.norm(direction);step=scale*1e-4
        measured=(cost(r+step*direction,scale)-cost(r-step*direction,scale))/(2*step)
        grad_error=abs(measured-float(g@direction))/max(np.linalg.norm(g),1e-30)
        finite=(gradient(r+step*direction,scale)-gradient(r-step*direction,scale))/(2*step)
        hess_error=float(np.linalg.norm(finite-h@direction)/max(np.linalg.norm(h@direction),1e-30))
        derivatives.append(dict(gradient_relative_error=grad_error,hessian_relative_error=hess_error))
    old_difference=abs(scalar_cost(r,scale)-scalar_cost(turned,scale))
    assert max(invariant.values())<=1e-12 and max(max(x.values()) for x in derivatives)<=1e-6
    assert old_difference>0
    # Diagonal block case has an explicit clipped QP solution, with no phase/source truth.
    residual=np.array([1.,0.,0.,-2.]);design=np.eye(4);box=.5
    gram,linear,weighted,rhs=quadratic(residual,design,1.)
    truth=np.clip(-linear/np.diag(gram),-box,box)
    region=SimpleNamespace(base=np.zeros(4),lower=np.full(4,-box),upper=np.full(4,box),
        model=SimpleNamespace(parts=0),first=np.array([],dtype=int),planes=[])
    results=[]
    for label,local_r,local_m in [('original',residual,design),('rotated',rotate(residual,angle),rotate(design,angle))]:
        gram,linear,weighted,rhs=quadratic(local_r,local_m,1.)
        solution,qp=solve(gram,linear,weighted,rhs,region,settings)
        error=float(abs(solution-truth).max());assert qp['success'] and error<=1e-7
        results.append(dict(label=label,parameters=solution.tolist(),analytic_error=error,qp=qp))
    return dict(passed=True,rotation_errors=invariant,derivatives=derivatives,
        original_scalar_cost_rotation_difference=old_difference,small_QPs=results,
        limitations=['Metric/linear-subproblem controls only; not common-phase estimator qualification'])
