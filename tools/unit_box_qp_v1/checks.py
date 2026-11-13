"""Fixed analytic unit-transform controls; independently check original KKT."""
import numpy as np
import scipy.sparse as sp
from .solver import solve_system


def controls(settings):
    rows=[]
    cases=[('interior',1.,[1.,.2,.01],[.2,-.3,.4]),
        ('strict_active',1.,[1.,.2,.01],[2.,-3.,.4]),
        ('zero',1.,[1.,.2,.01],[0.,0.,0.]),
        ('singular',1.,[1.,.2,0.],[.2,-.3,0.]),
        ('small_trust',2**-16,[1.,.2,.01],[2.,-3.,.4])]
    for label,radius,diagonal,target in cases:
        diagonal=np.array(diagonal);target=np.array(target)*radius;gram=np.diag(diagonal)
        weighted=np.diag(np.sqrt(diagonal));gradient=-gram@target;rhs=weighted@target
        matrix=sp.eye(3,format='csc');lower=np.full(3,-radius);upper=-lower
        step,q=solve_system(gram,gradient,weighted,rhs,matrix,lower,upper,radius,settings)
        expected=np.clip(target,lower,upper);identified=diagonal>0
        error=float(abs((step[identified]-expected[identified])/radius).max())
        assert q['success'] and error<=1e-6,(label,error,q['status'])
        scale=q['objective_scale'];normal=(gram+gram.T)/(2*scale);y=np.array(q['dual_solution'])
        stationarity=float(abs(normal@step+gradient/scale+matrix.T@y).max())
        assert stationarity==q['normalized_dual_stationarity'] and stationarity<=1e-8
        assert max(np.max(lower-step),np.max(step-upper))<=1e-9
        rows.append(dict(id=label,identified_unit_error=error,certificate=q))
    # min .5||x||^2+[-3,-2]'x with x1+x2<=2 has exact solution(1.5,.5).
    matrix=sp.csc_matrix([[1.,0.],[0.,1.],[1.,1.]])
    lower=np.array([-3.,-3.,-np.inf]);upper=np.array([3.,3.,2.]);g=np.array([-3.,-2.])
    step,q=solve_system(np.eye(2),g,np.eye(2),-g,matrix,lower,upper,3.,settings)
    error=float(abs(step-np.array([1.5,.5])).max());assert q['success'] and error<=1e-6
    rows.append(dict(id='coupled',identified_unit_error=error,certificate=q))
    return dict(passed=True,analytic_cases=rows,fixture_or_solver_threshold_sweep=False,
        limits='Certificates in original units; singular coordinate not asserted unique')
