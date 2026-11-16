"""Independent linear spectra; frozen-series ratios are audited separately."""
import math
import numpy as np
from scipy import signal


def verify(saved, rows, check):
    audio = {name:saved[name+'_audio'] for name in ('raw', 'filtered', 'source_grid', 'candidate')}
    starts = np.arange(0, len(audio['raw'])-4096+1, 256)
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    ids = starts[:, None]+np.arange(4096)
    kwargs = dict(fs=48000, window=window, nperseg=4096, noverlap=0, detrend=False, axis=1, scaling='density')
    scale = float(np.max(saved['raw_bin_power'].sum(axis=0)))
    transforms = {}
    for name,value in audio.items():
        f, p = signal.welch(value[ids], **kwargs)
        assert np.array_equal(f, saved['frequency'])
        expected = p.mean(axis=0)*(48000/4096)
        check(name+'_all_bin_power', saved[name+'_bin_power'], expected, scale)
        # Unnormalized SciPy FFT, independent of the producer NumPy FFT.
        from scipy.fft import rfft
        transforms[name] = rfft(value[ids]*window[None, :, None], axis=1)
    comp = np.stack((audio['filtered']-audio['raw'], audio['source_grid']-audio['filtered'],
        audio['candidate']-audio['source_grid']), axis=1).reshape(len(audio['raw']), 6)
    expected_gram = np.zeros((2049, 6, 6), complex)
    for i in range(6):
        for j in range(6):
            _, value = signal.csd(comp[ids, j], comp[ids, i], **kwargs)
            expected_gram[:, i, j] = value.mean(axis=0)*(48000/4096)
    check('all_bin_signed_component_Gram', saved['bin_component_Gram'], expected_gram, scale)
    ref, fit = transforms['raw'], transforms['candidate']
    ra, fa = np.hypot(ref.real, ref.imag), np.hypot(fit.real, fit.imag)
    product = ra*fa
    numerator = (fit.real*ra-ref.real*fa)**2+(fit.imag*ra-ref.imag*fa)**2
    angular = np.zeros_like(product)
    np.divide(numerator, product, out=angular, where=product>0)
    weight = np.r_[1., np.full(2047, 2.), 1.]/(4096*np.dot(window, window))
    radial = np.mean((fa-ra)**2, axis=0)*weight[:, None]
    angular = np.mean(angular, axis=0)*weight[:, None]
    error = np.mean(abs(fit-ref)**2, axis=0)*weight[:, None]
    check('all_bin_complex_error', saved['bin_error_power'], error, scale)
    check('all_bin_radial_error', saved['bin_radial_error_power'], radial, scale)
    check('all_bin_angular_error', saved['bin_angular_error_power'], angular, scale)
    check('complex_geometry_closure', radial+angular, error, scale)
    check('stored_complex_geometry_closure', saved['bin_radial_error_power']+
        saved['bin_angular_error_power'], saved['bin_error_power'], scale)
    components = comp.reshape(len(comp), 3, 2)
    check('sample_component_closure', saved['waveform_component_closure'],
        (audio['candidate']-audio['raw'])-components.sum(axis=1),
        max(float(np.max(abs(audio['raw']))), 1e-300))
    assert np.array_equal(starts, saved['starts'])
    expected_edges = (0, 3000, 6000, 8000, 10000, 14000, 16000, 20000, 22000, 24001)
    assert len(rows) == len(expected_edges)-1
    # Ratios in nearly empty bands cannot be certified by agreement of linear
    # spectra on the total-source scale. Audit those table ratios from the
    # SAME frozen observed bins with scalar fsum, never cross-FFT ratios.
    def reduce(value):
        value = np.asarray(value)
        return np.asarray([math.fsum(value[:, k]) for k in range(value.shape[1])])
    total_error = math.fsum(saved['bin_error_power'].ravel())
    for index, row in enumerate(rows):
        assert (row['low_Hz'], row['high_exclusive_Hz']) == expected_edges[index:index+2]
        mask=(f>=row['low_Hz'])&(f<row['high_exclusive_Hz'])
        rp = reduce(saved['raw_bin_power'][mask])
        ep = reduce(saved['bin_error_power'][mask])
        g = np.empty((6, 6), complex)
        for i in range(6):
            for j in range(6):
                values = saved['bin_component_Gram'][mask, i, j]
                g[i, j] = complex(math.fsum(values.real), math.fsum(values.imag))
        autos = np.diag(g).real.reshape(3, 2)
        cross = np.zeros((3, 3, 2))
        for i in range(3):
            for j in range(i+1, 3):
                cross[i, j] = [2*g[2*i+k, 2*j+k].real for k in (0, 1)]
        for key,value in (('reference_FS2_LR',rp), ('candidate_FS2_LR',reduce(saved['candidate_bin_power'][mask])),
            ('error_FS2_LR',ep), ('radial_error_FS2_LR',reduce(saved['bin_radial_error_power'][mask])),
            ('angular_error_FS2_LR',reduce(saved['bin_angular_error_power'][mask])), ('component_auto_FS2_LR',autos),
            ('component_signed_cross_FS2_LR',cross), ('component_recovered_error_FS2_LR',autos.sum(axis=0)+cross.sum(axis=(0,1)))):
            check(row['band']+'_'+key, row[key], value, scale)
        check(row['band']+'_signed_closure', autos.sum(axis=0)+cross.sum(axis=(0,1)), ep, scale)
        if math.fsum(rp)>0:
            check(row['band']+'_NRMSE', row['combined_complex_NRMSE'],
                math.sqrt(math.fsum(ep)/math.fsum(rp)), max(float(row['combined_complex_NRMSE']), 1.))
        else:
            assert row['combined_complex_NRMSE'] == (0. if not math.fsum(ep) else None)
        check(row['band']+'_error_fraction', row['fraction_of_total_observed_error'],
            math.fsum(ep)/total_error if total_error>0 else 0., 1.)
    return dict(windows=len(starts), all_bins=2049, signed_component_pairs=36,
        independent_linear_spectra_and_Gram=True, frozen_series_scalar_fsum_table_verification=True,
        crossFFT_normalized_ratios_or_certified_roundoff_bound=False,
        radial_angular_are_geometric_not_physical_or_audibility_attribution=True)
