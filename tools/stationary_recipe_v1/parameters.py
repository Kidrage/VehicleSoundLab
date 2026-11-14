"""Stationary-context parameter compilation; no recorded timeline in profiles."""
import numpy as np
from scipy.optimize import nnls
from resonant_detail_v1.filters import fit
from residual_osc_v1.spectrum import matrices


def compile_detail(reference, dna, kernel):
    # The stationary observation has no qualified periodic envelope law.
    flat = [dict(coefficients=[0.] * 16, enabled=False) for _ in kernel['bands_hz']]
    filters = fit(reference, kernel, flat)
    target = np.array([row['power'] for row in matrices(reference)])
    current = np.array([row['power'] for row in matrices(dna)])
    response = np.array([row['theoretical_band_power'] for row in filters]).T
    weight = 1 / np.maximum(target[:, 0], 1e-20)
    debt = target[:, 0] - current[:, 0]
    power, _ = nnls(response * weight[:, None], np.maximum(debt, 0) * weight)
    return dict(filters=filters, gains=np.sqrt(power).tolist(),
                right_over_left=np.sqrt(target[:, 1] / target[:, 0]).tolist(),
                reference_power=target.tolist(), DNA_power=current.tolist(),
                negative_debt_bands=np.flatnonzero(debt < 0).tolist(),
                predicted_power_error_db=(10*np.log10((current[:, 0]+response@power)/target[:, 0])).tolist())


def encode(path, model, root, warmup):
    rows = [f"VSL_RESONANT_DETAIL 1 48000 {len(model['filters'])} {warmup} {root:.17g}"]
    for f, gain, ratio in zip(model['filters'], model['gains'], model['right_over_left']):
        rows += [f"{len(f['a'])-1} {len(f['sos'])} 0",
                 ' '.join(f'{v:.17g}' for v in [*f['band_hz'], f['sigma'], gain, ratio]),
                 ' '.join(f'{v:.17g}' for v in f['a'])]
        rows += [' '.join(f'{v:.17g}' for v in s) for s in f['sos']]
    path.write_text('\n'.join(rows)+'\n', encoding='ascii', newline='\n')
