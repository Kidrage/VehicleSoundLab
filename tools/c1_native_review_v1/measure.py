"""Disjoint native bands, signed component budgets, and complex error geometry."""
import numpy as np


EDGES = (0, 3000, 6000, 8000, 10000, 14000, 16000, 20000, 22000, 24001)
LABELS = ('0-3k', '3-6k', '6-8k', '8-10k', '10-14k', '14-16k', '16-20k', '20-22k', '22-24k')


def frames(audio):
    n = len(audio)
    if np.shape(audio) != (n, 2) or n < 4096 or np.iscomplexobj(audio) or not np.isfinite(audio).all():
        raise ValueError('Finite native48k stereo with genuine complete windows required')
    starts = np.arange(0, n-4096+1, 256)
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    return audio[starts[:, None]+np.arange(4096)]*window[None, :, None], starts, window


def analyze(raw, filtered, source_grid, candidate):
    if any(np.shape(v) != np.shape(raw) for v in (filtered, source_grid, candidate)):
        raise ValueError('Same complete source interval required')
    values = dict(raw=raw, filtered=filtered, source_grid=source_grid, candidate=candidate)
    spectra = {name:np.fft.rfft(frames(audio)[0], axis=1) for name,audio in values.items()}
    _, starts, window = frames(raw)
    weight = np.r_[1., np.full(2047, 2.), 1.]/(4096*np.dot(window, window))
    frequency = np.arange(2049)*48000/4096
    components = np.stack((filtered-raw, source_grid-filtered, candidate-source_grid), axis=1)
    c = np.fft.rfft(components[starts[:, None]+np.arange(4096)]*window[None, :, None, None], axis=1)
    c = c.reshape(len(starts), 2049, 6)
    gram = np.einsum('wki,wkj,k->kij', c, c.conj(), weight, optimize=True)/len(starts)
    ref, fit = spectra['raw'], spectra['candidate']
    error = fit-ref
    radial = (abs(fit)-abs(ref))**2
    product = abs(fit)*abs(ref)
    direction = np.zeros_like(ref)
    valid_ref, valid_fit = abs(ref)>0, abs(fit)>0
    left, right = np.zeros_like(ref), np.zeros_like(fit)
    np.divide(ref, abs(ref), out=left, where=valid_ref)
    np.divide(fit, abs(fit), out=right, where=valid_fit)
    direction = right-left
    angular = product*abs(direction)**2
    power = lambda x:np.mean(abs(x)**2, axis=0)*weight[:, None]
    arrays = dict(frequency=frequency, starts=starts, window=window, bin_component_Gram=gram,
        bin_error_power=power(error),
        bin_radial_error_power=np.mean(radial, axis=0)*weight[:, None],
        bin_angular_error_power=np.mean(angular, axis=0)*weight[:, None],
        waveform_component_closure=(candidate-raw)-components.sum(axis=1))
    arrays.update({name+'_bin_power':power(value) for name,value in spectra.items()})
    arrays.update({name+'_audio':value for name,value in values.items()})
    rows = []
    for name, lo, hi in zip(LABELS, EDGES[:-1], EDGES[1:]):
        mask = (frequency>=lo)&(frequency<hi)
        rp = arrays['raw_bin_power'][mask].sum(axis=0)
        ep = arrays['bin_error_power'][mask].sum(axis=0)
        g = gram[mask].sum(axis=0)
        autos = np.diag(g).real.reshape(3, 2)
        cross = np.zeros((3, 3, 2))
        for i in range(3):
            for j in range(i+1, 3):
                cross[i, j] = 2*np.array([g[2*i+k, 2*j+k].real for k in (0, 1)])
        radial = arrays['bin_radial_error_power'][mask].sum(axis=0)
        angular = arrays['bin_angular_error_power'][mask].sum(axis=0)
        rows.append(dict(band=name, low_Hz=lo, high_exclusive_Hz=hi, reference_FS2_LR=rp.tolist(),
            candidate_FS2_LR=arrays['candidate_bin_power'][mask].sum(axis=0).tolist(),
            error_FS2_LR=ep.tolist(), radial_error_FS2_LR=radial.tolist(), angular_error_FS2_LR=angular.tolist(),
            component_auto_FS2_LR=autos.tolist(), component_signed_cross_FS2_LR=cross.tolist(),
            component_recovered_error_FS2_LR=(autos.sum(axis=0)+cross.sum(axis=(0, 1))).tolist(),
            combined_complex_NRMSE=float(np.sqrt(ep.sum()/rp.sum())) if rp.sum()>0 else (0. if not ep.sum() else None),
            fraction_of_total_observed_error=float(ep.sum()/arrays['bin_error_power'].sum()) if arrays['bin_error_power'].sum()>0 else 0.))
    return arrays, rows
