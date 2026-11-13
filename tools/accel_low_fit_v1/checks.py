"""Known full-path low+upper mixture and explicit local-support counterexamples."""
import numpy as np
from accel_ridges_v1.observe import inventory
from .observe import initial_graphs, fit_tile, temporal

def union_inventory(audio, ridge_plan):
    low = inventory(audio, dict(ridge_plan, inventory_hz=[30, 200]))
    high = inventory(audio, ridge_plan)
    return dict(bin=low['bin'] + high['bin'], hz=low['hz'] + high['hz'])

def controls(fit_plan, ridge_plan, link_plan, checkpoint=None):
    n = 12000
    local = (np.arange(n) - n / 2) / 48000
    centers = (np.arange(12) + .5) * .25
    base = np.array([43.3, 65.1, 88.7, 115.7, 137.9, 179.3, 239.7, 299.8, 519.3, 899.1])
    moving = np.array([True, False, True, False, True, True, False, True, True, True])
    amplitude = np.array([.04, .03, .05, .02, .055, .08, .03, .3, .07, .03])
    phase = np.arange(10) * .4
    q = base * moving * .05
    audio, inventories = [], []
    truth = []
    for center in centers:
        t = center + local
        angles = 2 * np.pi * (base * t[:, None] + .5 * q * t[:, None] ** 2) + phase
        x = np.column_stack((np.cos(angles) @ amplitude, np.cos(angles + .17) @ (amplitude * .71)))
        audio.append(x)
        inv = union_inventory(x, ridge_plan)
        inventories.append(inv)
        frequencies = base + q * center
        truth.append(dict(frequency_hz=frequencies.tolist(), q_hzs=q.tolist(), amplitude_LR=(amplitude[:, None] * [1, .71]).tolist()))
        if checkpoint:
            checkpoint('inventory_' + str(len(audio) - 1), dict(inventory=inv, truth=truth[-1]), dict(audio=x))
        assert len(inv['hz']) == 10, (center, inv)
    initialization = initial_graphs(inventories, 1 + .05 * centers, ridge_plan)
    rows, arrays = [], []
    for i, x in enumerate(audio):
        result, saved = fit_tile(x, inventories[i], initialization[i], fit_plan)
        rows.append(result)
        arrays.append(dict(audio=x, **saved))
        if checkpoint:
            checkpoint('fit_' + str(i), dict(fit=result, truth=truth[i]), arrays[-1])
        assert result['success'] and all(v['eligible'] for v in result['lines']), (i, result)
        assert max(abs(v['frequency_hz'] - f) for v, f in zip(result['lines'], truth[i]['frequency_hz'])) < .06
        assert max(abs(v['chirp_hz_per_second'] - z) for v, z in zip(result['lines'], q)) < .15
        assert np.linalg.norm(saved['residual']) / np.linalg.norm(x) < 1e-5
    linked = temporal(rows, link_plan)
    assert len(linked['tracks']) == 10 and all(len(v['windows']) == 12 for v in linked['tracks'])
    result = dict(rows=rows, inventories=inventories, initialization=initialization, truth=truth, temporal=linked,
                  known_crossing200_present=True, source_truth_not_initialization=True,
                  signal_parameters=dict(base_hz=base.tolist(), q_hzs=q.tolist(), amplitude_L=amplitude.tolist(),
                    phase_radians=phase.tolist(), centers_seconds=centers.tolist(), right_gain=.71, right_phase_radians=.17))
    # Record noise/silence without interpreting a positive local fit as a source.
    rng = np.random.default_rng(761233)
    left = rng.normal(0, .1, n)
    right = rng.normal(0, .1, n)
    cases = dict(same_mono_noise=np.column_stack((left, .67 * left)),
                 independent_noise=np.column_stack((left, right)), silence=np.zeros((n, 2)))
    counterexamples = {}
    for name, x in cases.items():
        inv = union_inventory(x, ridge_plan)
        init = initial_graphs([inv], [1.], ridge_plan)[0]
        fitted, saved = fit_tile(x, inv, init, fit_plan)
        counterexamples[name] = dict(inventory=inv, initialization=init, fit=fitted)
        arrays.append(dict(name=name, audio=x, **saved))
        if checkpoint:
            checkpoint(name, counterexamples[name], dict(audio=x, **saved))
    center = centers[0]
    t = center + local
    target = 5
    removed = amplitude[target] * np.cos(2 * np.pi * (base[target] * t + .5 * q[target] * t ** 2) + phase[target])
    removed_r = amplitude[target] * .71 * np.cos(2 * np.pi * (base[target] * t + .5 * q[target] * t ** 2) + phase[target] + .17)
    neighbor = .06 * np.cos(2 * np.pi * 199.7 * t + .4)
    missing = audio[0] - np.column_stack((removed, removed_r)) + np.column_stack((neighbor, .71 * neighbor))
    inv = union_inventory(missing, ridge_plan)
    mapping = dict(zip(inv['bin'], inv['hz']))
    mapping.setdefault(45, 180.)  # Native bin45 is180Hz at4Hz/bin; explicit absent-slot control.
    inv = dict(bin=sorted(mapping), hz=[mapping[k] for k in sorted(mapping)])
    init = initial_graphs([inv], [1.], ridge_plan)[0]
    fitted, saved = fit_tile(missing, inv, init, fit_plan)
    counterexamples['missing_low_with_neighbor'] = dict(inventory=inv, initialization=init, fit=fitted,
        forced_absent_native_bin=45, forced_absent_frequency_hz=180, removed_global_component=target, neighbor_hz=199.7)
    arrays.append(dict(name='missing_low_with_neighbor', audio=missing, **saved))
    if checkpoint:
        checkpoint('missing_low_with_neighbor', counterexamples['missing_low_with_neighbor'], dict(audio=missing, **saved))
    assert not next(v for v in fitted['lines'] if v['nominal_hz'] == 180)['eligible']
    result['counterexamples'] = counterexamples
    return result, arrays
