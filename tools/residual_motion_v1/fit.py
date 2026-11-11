"""Fit only positive amplitude-variance debt after accounting for the carriers."""
import numpy as np
from .features import covariance, amplitudes
from residual_osc_v1.spectrum import BANDS


def estimate(reference_power, base_powers, residual_powers):
    target, target_lag = covariance(amplitudes(reference_power))
    baseline = [covariance(amplitudes(p)) for p in base_powers]
    carrier = np.mean([c[0] for c in baseline], axis=0)
    carrier_lag = np.mean([c[1] for c in baseline], axis=0)
    debt = (target-carrier+target.T-carrier.T)/2
    values, vectors = np.linalg.eigh(debt)
    selected = np.argsort(values)[::-1][:4]
    selected = [i for i in selected if values[i] > 1e-7]
    modes = vectors[:, selected]*np.sqrt(np.maximum(values[selected], 0))
    rho = []
    for i in selected:
        vector = vectors[:, i]
        rho.append(float(np.clip(vector@(target_lag-carrier_lag)@vector/values[i], 0, .95)))
    rho = np.array(rho)
    total = np.mean([p.mean(axis=(0, 2)) for p in base_powers], axis=0)
    remaining = np.mean([p.mean(axis=(0, 2)) for p in residual_powers], axis=0)
    fraction = remaining/np.maximum(total, 1e-30)
    # First-order d(sqrt(total_power))/dg is the residual power fraction.
    # Weak residual bands cannot safely control the whole mixed envelope.
    basis = np.divide(modes, fraction[:, None], out=np.zeros_like(modes), where=fraction[:, None] >= .1)
    bound = np.sqrt((1+rho)/(1-rho))
    maximum = np.sum(abs(basis)*bound, axis=1)
    scale = min(1., .75/max(float(maximum.max()), 1e-30))
    basis *= scale
    return basis, rho, dict(target_covariance=target.tolist(), baseline_covariance=carrier.tolist(),
        raw_debt_eigenvalues=values.tolist(), retained_eigenvalues=values[selected].tolist(),
        negative_eigenvalue_mass=float(-values[values < 0].sum()), residual_power_fraction=fraction.tolist(),
        suppressed_weak_bands=(fraction < .1).tolist(), common_bound_scale=scale,
        maximum_affine_deviation=float(np.sum(abs(basis)*bound, axis=1).max()) if len(rho) else 0,
        note='Positive-PSD approximation of mixed-band amplitude variance debt; not an exact physical source envelope')


def export(path, basis, rho):
    with path.open('w', encoding='ascii', newline='\n') as stream:
        stream.write(f'VSL_RESIDUAL_MOTION 1 48000 480 {len(BANDS)} {len(rho)}\n')
        stream.write(' '.join(f'{r:.17g}' for r in rho)+'\n')
        for band, row in zip(BANDS, basis):
            stream.write(' '.join(f'{r:.17g}' for r in [*band, *row])+'\n')
