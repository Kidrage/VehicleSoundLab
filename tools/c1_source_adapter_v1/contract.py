"""Own legacy calibration and distinct new C1 audio/coordinates explicitly."""
import numpy as np
from clock_c1_v1.geometry import build, evaluate
from .bandwidth import describe


FIELDS = ('audio', 'target', 'metric_target', 'positions', 'original_positions', 'orders', 'scale',
    'weights', 'band_power', 'floor_active', 'sigma', 'amplitude', 'source_coordinates', 'target_source_coordinates')
CLOCK_FIELDS = ('x', 'y', 'origin', 'coefficients', 'interval_minimum_derivative', 'node_preservation_max_seconds')


def prepare(legacy, observations, clock, audio, source_taps, cutoff_hz):
    if any(name not in legacy for name in FIELDS):
        raise ValueError('Explicit legacy data, metric_target, calibration and source coordinates required')
    # Copies are deliberate: the caller retains ownership of every input.
    z = {name:np.asarray(legacy[name]).copy() for name in FIELDS}
    if any(np.iscomplexobj(v) or v.dtype.kind not in 'biuf' or not np.isfinite(v).all() for v in z.values()):
        raise ValueError('Every original data/calibration/coordinate array must be finite and real')
    n = len(z['audio']); old = z['source_coordinates']
    if (n < 8192 or z['audio'].shape != (n, 2) or z['target'].shape != (n-4096, 2)
            or old.shape != (n,) or np.iscomplexobj(old) or not np.isfinite(old).all()
            or np.any(np.diff(old)<=0) or not np.array_equal(z['target'], z['audio'][2048:-2048])
            or not np.array_equal(z['target_source_coordinates'], old[2048:-2048])):
        raise ValueError('Exact legacy stereo/context and strictly increasing original source times required')
    if any(name not in clock for name in CLOCK_FIELDS) or set(observations) != {'x', 'y'}:
        raise ValueError('Complete C1 model and explicit unchanged observations required')
    if not all(np.array_equal(clock[k], observations[k]) for k in ('x', 'y')):
        raise ValueError('C1 must preserve the original observed nodes')
    rebuilt = build(observations['x'], observations['y'])
    if any(not np.array_equal(clock[k], rebuilt[k]) for k in CLOCK_FIELDS):
        raise ValueError('Clock coefficients/derivatives must match the declared observed-node construction')
    q = np.arange(n, dtype=float)
    coordinates = evaluate(clock, q)
    audio = np.asarray(audio)
    if (audio.shape != (n, 2) or np.iscomplexobj(audio) or not np.isfinite(audio).all()):
        raise ValueError('Complete finite new stereo audio must share the supported source grid')
    bandwidth = describe(clock, z['orders'], source_taps, cutoff_hz)
    z.update(legacy_audio=z['audio'].copy(), legacy_target=z['target'].copy(),
        legacy_source_coordinates=old.copy(), legacy_target_source_coordinates=z['target_source_coordinates'].copy(),
        audio=audio.copy(), target=audio[2048:-2048].copy(),
        source_coordinates=coordinates.copy(), target_source_coordinates=coordinates[2048:-2048].copy(),
        phase_grid_indices=q, source_filter_taps=np.asarray(source_taps).copy(),
        source_nominal_cutoff_Hz=np.array(cutoff_hz), native_rate_Hz=np.array(48000))
    z.update({'clock_'+k:np.asarray(clock[k]).copy() for k in CLOCK_FIELDS})
    z.update({'observed_clock_'+k:np.asarray(observations[k]).copy() for k in ('x', 'y')})
    return z, dict(schema='vsl.c1-source-input/1', source_method='observed-node-C1-and-distinct-source-v1',
        objective_metric_origin='explicit unchanged legacy metric_target',
        source_time_geometry='new common LR C1, distinct from legacy coordinates',
        bandwidth=bandwidth, owned_input_arrays=True, no_runtime_source_or_fidelity_promotion=True)
