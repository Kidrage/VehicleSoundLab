"""All-bin weighted/ordinary spectra and signed transform-domain comparisons."""
import numpy as np
from locked_source_error_v1.assessment import locked_rows


def measure(values, weights, amplitude):
    arrays, info, rows = {}, {}, {}
    frequency = np.arange(2049)*16.
    masks = [frequency < 3000, (frequency >= 3000) & (frequency < 6000),
        (frequency >= 6000) & (frequency < 8000), (frequency >= 8000) & (frequency < 10000),
        (frequency >= 10000) & (frequency < 14000), frequency >= 14000,
        (frequency >= 14000) & (frequency < 16000), (frequency >= 16000) & (frequency < 18432),
        frequency == 18432, frequency > 18432]
    names = ['0_3k', '3_6k', '6_8k', '8_10k', '10_14k', '14k_plus',
             '14_16k', '16_18432', 'centre18432', 'above18432']
    for name, audio in values.items():
        X, power, _, _ = locked_rows(audio[2048:-2048], weights, amplitude)
        rows[name] = X
        mass = np.sum(abs(X)**2, axis=0)
        arrays[name+'_weighted_mass'] = mass
        arrays[name+'_Welch_FS2'] = power
        info[name] = {label: dict(weighted_mass_LR=mass[mask].sum(axis=0).tolist(),
                                  Welch_FS2_LR=power[mask].sum(axis=0).tolist())
                      for label, mask in zip(names, masks)}
    reference_name = 'exact_registered' if 'exact_registered' in values else 'reference2048'
    R = rows[reference_name]
    comparisons = {}
    for name, X in rows.items():
        D = X-R  # Declared transform-domain residual; no claim of bitwise STFT linearity.
        time_delta = values[name]-values[reference_name]
        time_rows, time_power, _, _ = locked_rows(time_delta[2048:-2048], weights, amplitude)
        time_mass = np.sum(abs(time_rows)**2, axis=0)
        arrays[name+'_time_difference_weighted_mass'] = time_mass
        arrays[name+'_time_difference_Welch_FS2'] = time_power
        groups = {}
        for label, mask in zip(names, masks):
            B = np.concatenate((R[:, mask], D[:, mask]), axis=2).reshape(-1, 4)
            G = B.T@B.conj()
            a = np.array([G[c, c].real for c in (0, 1)])
            d = np.array([G[c+2, c+2].real for c in (0, 1)])
            cross = 2*np.array([G[c, c+2].real for c in (0, 1)])
            total = np.sum(abs(X[:, mask])**2, axis=(0, 1))
            scale = a+d+abs(cross)
            closure = np.divide(abs(total-a-d-cross), scale, out=np.zeros_like(scale), where=scale>0)
            assert np.max(closure) < 2e-12
            groups[label] = dict(reference_mass_LR=a.tolist(), difference_mass_LR=d.tolist(),
                signed_cross_mass_LR=cross.tolist(), candidate_mass_LR=total.tolist(),
                transform_difference_NRMSE=float(np.sqrt(d.sum()/a.sum())) if a.sum() else None,
                time_difference_NRMSE=float(np.sqrt(time_mass[mask].sum()/a.sum())) if a.sum() else None,
                signed_power_closure_relative=float(np.max(closure)))
            arrays[name+'_vs_reference_'+label+'_Gram'] = G
        comparisons[name] = dict(groups=groups, time_max_FS=float(np.max(abs(time_delta))),
            time_NRMSE=float(np.linalg.norm(time_delta)/np.linalg.norm(values[reference_name])))
    return arrays, dict(signals=info, comparisons=comparisons, diagnostic_reference=reference_name,
        virtual_rate=65536, maximum_carrier_centre_is_not_strict_bandwidth=True,
        weighted_mass_is_not_acoustic_power=True, residual_is_difference_of_declared_spectra=True,
        spectral_difference_not_claimed_bitwise_equal_to_FFT_of_time_difference=True)
