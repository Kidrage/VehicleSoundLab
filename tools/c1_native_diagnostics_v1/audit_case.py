"""All-query native case verification, separate from launch and reporting."""
import numpy as np
from clock_c1_v1.audit_geometry import verify as geometry
from clock_native_bridge_v1.audit_render import verify as render
from clock_native_bridge_v1.audit_observation import comparisons
from locked_source_tail_v1.audit_kernel import analytic
from observer_frequency_v1.reduced_oracle import synthesize
from .declared_statistics import verify as observe


def read(path):
    with np.load(path, allow_pickle=False) as f:
        return {k:f[k] for k in f.files}


def verify(root, row, mode, gates, check):
    source = read(root/'source.npz')
    gr = geometry(source)
    scalar = synthesize(source['fitted'], source['fit_positions'], source['orders'], len(source['query']))
    check('every_fitted_scalar', source['fitted_grid_audio'], scalar, float(np.max(abs(scalar))), 2e-11)
    count, start = int(source['count']), float(source['native_start'])
    if mode == 'known':
        times = start+np.arange(count)/48000
        raw = analytic(times-160., source['source_frequency'], source['source_coefficients'], np.array([1.]))
        filtered = analytic(times-160., source['source_frequency'], source['source_coefficients'], source['source_taps'])
    else:
        first, stop = int(source['native_first']), int(source['native_stop'])
        assert stop-first == count and start == float(source['source_start'])+first/48000
        raw = source['source_native'][first:stop]
        d = len(source['source_taps'])//2
        assert first >= d and stop+d <= len(source['source_native'])
        context = source['source_native'][first-d:stop+d]
        filtered = np.zeros((count, 2))
        for k, tap in enumerate(source['source_taps']):
            filtered += tap*context[2*d-k:2*d-k+count]
    scale = float(np.max(abs(raw)))
    check('raw_reference', source['raw'], raw, scale, 2e-11)
    check('native_source_FIR', source['source_FIR'], filtered, scale, 2e-11)
    checks = []
    for name in ('source', 'candidate'):
        field = 'source_grid_audio' if name == 'source' else 'fitted_grid_audio'
        packet = dict(source, source=source[field])
        for up in (16, 32):
            result = render(packet, read(root/(name+'_'+str(up)+'.npz')), up, check)
            checks.append(dict(name=name, up=up, verification=result))
    saved = read(root/'sound.npz')
    sound = {}
    for name in ('raw', 'source_FIR', 'source_16', 'source_32', 'candidate_16', 'candidate_32'):
        audio = source[name] if name in ('raw', 'source_FIR') else read(root/(name+'.npz'))['native']
        assert np.array_equal(saved[name+'_audio'], audio)
        sound[name] = observe(name, audio, saved, check, gates)
    for label, result in row['comparisons'].items():
        left, right = label.split('_vs_')
        comparisons(left, right, saved, result, check, gates)
    if mode == 'known':
        assert row['known_wave_qualified']
        if row['label'] in ('nonlinear_zero', 'nonlinear_silent_right'):
            for name in sound:
                audio = saved[name+'_audio']
                assert not np.count_nonzero(audio if row['label'] == 'nonlinear_zero' else audio[:, 1])
    return dict(label=row['label'], geometry=gr, every_query_render=checks, native_observations=sound,
        known_wave_qualified=row['known_wave_qualified'],
        source_native16_32_converged=row['source_native16_32_converged'],
        candidate_native16_32_converged=row['candidate_native16_32_converged'])
