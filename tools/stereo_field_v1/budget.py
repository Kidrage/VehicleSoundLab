"""Hermitian2x2 additive feasibility; alpha is a diagnostic bound, not a recipe."""
import numpy as np


def matrix(row):
    cross=complex(*row['cross'])
    # Our stored cross is conjugate(L)*R; E[x x^H] has its conjugate at0,1.
    return np.array([[row['power'][0],cross.conjugate()],[cross,row['power'][1]]],dtype=complex)


def minimum(value):
    return float(np.linalg.eigvalsh(value)[0])


def analyze(target,base,tolerance,steps):
    scale=float(np.trace(target).real)
    if not scale>0:raise ValueError('Need positive target trace')
    t=target/scale;b=base/scale
    if minimum(t)<-tolerance or minimum(b)<-tolerance:raise ValueError('Input matrix is not PSD')
    def possible(alpha):return minimum(t-alpha*b)>=-tolerance
    raw=t-b;old_ok=possible(1)
    if old_ok:alpha=1.;bracket=[1.,1.]
    else:
        low=0.;high=1.
        for _ in range(steps):
            mid=(low+high)/2
            if possible(mid):low=mid
            else:high=mid
        alpha=low;bracket=[low,high]
    # Reproduce the old residual strategy: nonnegative diagonal debt and
    # magnitude-limited cross. It is always PSD, but can miss target cross.
    diagonal=np.maximum(np.diag(raw).real,0)
    desired=raw[1,0];bound=float(np.sqrt(np.prod(diagonal)))
    cross=desired if abs(desired)<=bound else desired*bound/abs(desired)
    clipped=np.array([[diagonal[0],cross.conjugate()],[cross,diagonal[1]]])
    discrepancy=b+clipped-t
    return dict(target_trace=scale,unmodified_debt_PSD=bool(old_ok),raw_minimum_eigenvalue_relative=minimum(raw),
        raw_diagonal_debt_relative=np.diag(raw).real.tolist(),raw_cross_debt_relative=[float(desired.real),float(desired.imag)],
        diagonal_nonnegative=bool(np.min(np.diag(raw).real)>=-tolerance),
        maximum_independent_additive_DNA_power_alpha=alpha,alpha_bisection_bracket=bracket,
        alpha_boundary_minimum_eigenvalue_relative=minimum(t-alpha*b),
        old_clipping_matrix_error_relative=float(np.linalg.norm(discrepancy,'fro')),
        old_clipping_cross_error_relative=float(abs(discrepancy[1,0])))


def controls(plan):
    examples=[('already_feasible',np.diag([1.,1.]),np.diag([.2,.3]),1.),
        ('diagonal_excess',np.diag([2.,1.]),np.diag([1.,2.]),.5),
        ('cross_excess',np.eye(2),np.array([[1.,.8],[.8,1.]]),1/1.8),
        ('opposite_coherence',np.array([[1.,.5],[.5,1.]]),np.array([[.4,-.2],[-.2,.4]]),5/6),
        ('rank_one_target',np.array([[1.,1.],[1.,1.]]),np.diag([1.,0.]),0.),
        ('silent_base',np.eye(2),np.zeros((2,2)),1.)]
    records=[]
    for name,t,b,expected in examples:
        row=analyze(t,b,plan['PSD_relative_tolerance'],plan['bisection_steps'])
        error=abs(row['maximum_independent_additive_DNA_power_alpha']-expected)
        assert error<plan['known_alpha_error_maximum'],(name,error)
        # A common unitary phase rotation must not affect the feasibility bound.
        unitary=np.diag([1.,np.exp(.71j)])
        rotated=analyze(unitary@t@unitary.conj().T,unitary@b@unitary.conj().T,
            plan['PSD_relative_tolerance'],plan['bisection_steps'])
        rotation_error=abs(rotated['maximum_independent_additive_DNA_power_alpha']-row['maximum_independent_additive_DNA_power_alpha'])
        assert rotation_error<plan['independent_matrix_error_maximum']
        records.append(dict(name=name,expected_alpha=expected,alpha_error=error,unitary_alpha_error=rotation_error,result=row))
    return records


def scalar_minimum(value):
    a=float(value[0,0].real);b=float(value[1,1].real);cross=complex(value[1,0])
    return .5*(a+b-np.sqrt((a-b)**2+4*abs(cross)**2))
