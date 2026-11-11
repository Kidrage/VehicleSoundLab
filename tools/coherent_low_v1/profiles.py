"""Fit a constrained LF supplement and a magnitude-identical phase control."""
from copy import deepcopy
import numpy as np
from sound_dna.profile import estimate, export


def rotate_profile(model, offsets):
    result = deepcopy(model)
    matrices = []
    for h, angle in enumerate(offsets):
        co, si = np.cos(angle), np.sin(angle)
        rotation = np.array([[co, -si, 0, 0], [si, co, 0, 0],
                             [0, 0, co, -si], [0, 0, si, co]])
        result['mean'][h] = rotation @ model['mean'][h]
        result['basis'][h] = model['basis'][h] @ rotation.T
        result['root'][h] = rotation @ model['root'][h]
        matrices.append(rotation)
    return result, np.array(matrices)


def fit(audio, directory):
    directory.mkdir()
    model, statistics = estimate(audio, harmonics=7, components=12)
    # Engineering selection, not a measured structural transfer. Avoid adding
    # a weak/unlocked sub-bass and the dominant tracking line already in DNA.
    weights = np.array([0, 1, 1, 1, 0, 1, .25])
    for name in ('mean', 'basis', 'root'):
        model[name] *= weights.reshape((7,) + (1,) * (model[name].ndim - 1))
    random = np.random.default_rng(17031)
    offsets = random.uniform(-np.pi, np.pi, 7)
    control, matrices = rotate_profile(model, offsets)
    probe = np.random.default_rng(781).normal(size=(128, model['basis'].shape[1]))
    residual = np.random.default_rng(782).normal(size=(128, 7, 4))
    a = model['mean'][None] + np.einsum('nk,hkc->nhc', probe, model['basis']) + np.einsum('hcj,nhj->nhc', model['root'], residual)
    b = control['mean'][None] + np.einsum('nk,hkc->nhc', probe, control['basis']) + np.einsum('hcj,nhj->nhc', control['root'], residual)
    magnitudes_a = abs(a[..., 0::2] + 1j * a[..., 1::2])
    magnitudes_b = abs(b[..., 0::2] + 1j * b[..., 1::2])
    error = float(np.max(abs(magnitudes_a - magnitudes_b)))
    assert error < 1e-12
    export(directory / 'measured_phase.model', model, 46.875)
    export(directory / 'scrambled_phase.model', control, 46.875)
    np.savez(directory / 'statistics.npz', **model)
    return dict(statistics=statistics, relative_harmonic_weights=weights.tolist(),
                phase_control_offsets_radians=offsets.tolist(), phase_control_magnitude_max_error=error,
                rotation_orthogonality_error=float(np.max(abs(matrices.transpose(0, 2, 1) @ matrices - np.eye(4)))),
                design='Additive 93.75..328.125Hz-relative supplement; h1/h5 muted, h7 tapered. Existing DNA content remains; this is voicing, not source separation.',
                generation='Unmodified modules/sound_dna C11 voice; fixed mean phases with new stochastic magnitudes')
