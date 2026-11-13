"""Independent native FFT quadrature and preservation of old observations."""
import numpy as np
from aperture_model_v1.forward import Aperture, real_rows
from .geometry import complete


def controls(previous):
    plan, evidence = complete(previous)
    frames = round(plan['cycles']*plan['samples_per_cycle'])
    time = np.arange(frames)/plan['samples_per_cycle']
    old, new = Aperture(frames, previous), Aperture(frames, plan)
    assert np.array_equal(old.starts, new.starts) and old.size == new.size
    assert np.array_equal(old.window, new.window)
    indices = np.searchsorted(new.bins, old.bins)
    assert np.array_equal(new.bins[indices], old.bins)
    grid_evidence = []
    for order in (3., 3.1):
        amplitude = .23
        signal = amplitude*np.cos(2*np.pi*order*time+.31)
        before = old.apply(signal).reshape(len(old.starts), -1)
        after = new.apply(signal).reshape(len(new.starts), -1)
        assert np.array_equal(before, after[:, indices])
        old_energy = float(np.sum(abs(before[0])**2))
        new_energy = float(np.sum(abs(after[0])**2))
        expected_old = amplitude**2*(1 if order == 3. else .5)
        expected_new = 1.5*amplitude**2
        assert abs(old_energy-expected_old) < 1e-12 and abs(new_energy-expected_new) < 1e-12
        grid_evidence.append(dict(order=order, previous_energy=old_energy, native_energy=new_energy,
            expected_previous_energy=expected_old, expected_native_energy=expected_new))
    rows = []
    for kind in ('rapid_common', 'occluded_partial', 'local_phase'):
        epsilon = .055*np.exp(-((time-18)/1.3)**2)-.035*np.exp(-((time-21)/.9)**2)
        signal = np.zeros_like(time)
        for index, order in enumerate((2., 2.2, 3., 5., 7.)):
            amplitude = .03*(1+.08*np.sin(2*np.pi*.023*time+.2*index))
            if kind == 'occluded_partial' and index == 1:
                amplitude *= 1-.95*np.exp(-((time-20)/.8)**4)
            phase = 2*np.pi*order*(time+epsilon)+.17*index
            if kind == 'local_phase' and index == 2:
                phase += .6*np.sin(2*np.pi*.17*time)
            signal += amplitude*np.cos(phase)
        after = new.apply(signal).reshape(len(new.starts), -1)
        before = old.apply(signal).reshape(len(old.starts), -1)
        assert np.array_equal(before, after[:, indices])
        maximum = 0.
        window = np.sin(np.pi*np.arange(new.size)/new.size)**2
        for row in (0, len(new.starts)//2, len(new.starts)-1):
            start = new.starts[row]
            for col in range(len(new.orders)):
                direct = 2*np.sum(signal[start:start+new.size]*window*
                    np.exp(-2j*np.pi*new.orders[col]*time[start:start+new.size]))/window.sum()
                maximum = max(maximum, float(abs(direct-after[row, col])))
        assert maximum < plan['rules']['maximum_forward_check_error']
        rows.append(dict(id=kind, scalar_quadrature_maximum_error=maximum,
            previous_subset_exact=True, interstitial_observation_norm=float(np.linalg.norm(
                np.delete(after, indices, axis=1)))))
    return dict(passed=True, geometry=evidence, on_off_grid_Hann_energy=grid_evidence,
        independent_waveform_projections=rows, old_bins=len(old.orders), native_bins=len(new.orders),
        old_real_rows=2*len(old.starts)*len(old.orders), native_real_rows=2*len(new.starts)*len(new.orders),
        note='Projection controls only; not rapid/occlusion phase-estimator qualification')
