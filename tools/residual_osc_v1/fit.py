"""Fit positive diagonal debt and a bounded complex residual coherence."""
import numpy as np
from .spectrum import matrices, BANDS


def fit(reference, base):
    target, represented = matrices(reference), matrices(base)
    rows = []
    for a, b in zip(target, represented):
        raw = np.asarray(a['power'])-np.asarray(b['power'])
        power = np.maximum(raw,0)
        cross = complex(*a['cross'])-complex(*b['cross'])
        rho = cross/np.sqrt(np.prod(power)) if min(power)>1e-25 else 0j
        original = rho
        if abs(rho)>1:rho /= abs(rho)
        rows.append(dict(hz=a['hz'],power=power.tolist(),coherence=[rho.real,rho.imag],
            raw_diagonal_difference=raw.tolist(), raw_cross_difference=[cross.real,cross.imag],
            unclipped_coherence=[original.real,original.imag], coherence_clipped=abs(original)>1,
            negative_diagonal_clipped=(raw<0).tolist()))
    return rows, dict(reference=target,base=represented,
        processing='Mean Welch power debt; nonnegative L/R diagonals; cross difference clipped to positive-semidefinite magnitude. No full-DNA gain or denoising.',
        meaning='Additive analysis residual, not identified airflow/intake/mechanical sources')


def export(path, rows, partials=32):
    assert len(rows)<=16 and 8<=partials<=32
    lines=[f'VSL_SOUND_RESIDUAL 1 48000 {len(rows)} {partials}']
    for row in rows:
        data=[*row['hz'], *row['power'], *row['coherence']]
        assert np.isfinite(data).all()
        lines.append(' '.join(f'{v:.17g}' for v in data))
    path.write_text('\n'.join(lines)+'\n',encoding='ascii')
