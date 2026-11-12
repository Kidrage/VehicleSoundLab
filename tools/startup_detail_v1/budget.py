"""Independent additive stereo debt, without changing the underlying DNA."""
import numpy as np
from residual_osc_v1.spectrum import matrices
from stereo_field_v1.budget import matrix, scalar_minimum

BANDS = [(300,450),(450,600),(600,850),(850,1200),(1200,1500),(1500,1900),
         (1900,2400),(2400,3000),(3000,3800),(3800,4800),(4800,6000),(6000,8000)]


def additive(target, base, tolerance=1e-10):
    scale=float(np.trace(target).real)
    if scale <= 0 or not np.isfinite(target).all() or not np.isfinite(base).all():
        raise ValueError('Finite positive target required')
    delta=target-base
    eig=scalar_minimum(delta)/scale
    accepted=eig>=-tolerance
    if accepted:
        # Only roundoff is removed; a genuinely infeasible band is kept silent.
        values,vectors=np.linalg.eigh(delta)
        residual=(vectors*np.maximum(values,0))@vectors.conj().T
    else:
        residual=np.zeros((2,2),complex)
    power=np.maximum(residual.diagonal().real,0)
    norm=float(np.sqrt(np.prod(power)))
    rho=residual[1,0]/norm if norm>0 else 0j
    return dict(accepted=bool(accepted),minimum_eigenvalue_relative=eig,
                power=power.tolist(),coherence=[float(rho.real),float(rho.imag)],
                reconstruction_error_relative=float(np.linalg.norm(base+residual-target,'fro')/scale))


def fit(reference, base):
    targets=matrices(reference,BANDS);bases=matrices(base,BANDS)
    rows=[]
    for t,b in zip(targets,bases):
        rows.append(dict(hz=t['hz'],**additive(matrix(t),matrix(b)),target=t,base=b))
    return rows


def errors(target, candidate):
    rows=[]
    for t,c in zip(matrices(target,BANDS),matrices(candidate,BANDS)):
        p=np.asarray(t['power']);q=np.asarray(c['power'])
        def coherence(v):
            return complex(*v['cross'])/max(np.sqrt(np.prod(v['power'])),1e-30)
        rows.append(dict(hz=t['hz'],LR_dB=(10*np.log10((q+1e-30)/(p+1e-30))).tolist(),
                         coherence_error=float(abs(coherence(t)-coherence(c)))))
    return rows
