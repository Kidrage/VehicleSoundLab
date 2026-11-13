"""Phase-free native-resolution stereo recording observations."""
import numpy as np


def spectrum(audio, bands, rate=48000):
    n = len(audio)
    window = .5-.5*np.cos(2*np.pi*np.arange(n)/n)
    transform = np.fft.rfft(audio*window[:, None], axis=0)
    factor = np.full(len(transform), 2.)
    factor[0] = 1.
    if n % 2 == 0:
        factor[-1] = 1.
    cells = abs(transform)**2*factor[:, None]/(n*np.sum(window*window))
    frequency = np.fft.rfftfreq(n, 1/rate)
    power = np.array([cells[(frequency >= lo)&(frequency < hi)].sum(axis=0) for lo, hi in bands])
    total = power.sum(axis=0)
    fractions = np.divide(power, total[None, :], out=np.zeros_like(power), where=total[None, :] > 0)
    weighted_energy = np.sum(audio*audio*window[:, None]**2, axis=0)/np.sum(window*window)
    parseval_error = float(abs(cells.sum(axis=0)-weighted_energy).max())
    return dict(power=power, fractions=fractions, total_band_power=total,
        parseval_error=parseval_error, cells=cells, frequency=frequency)


def observe(audio, bands, frames=24000):
    count = len(audio)//frames
    if count < 1:
        raise ValueError('No complete native-resolution analysis tile')
    tiles = [spectrum(audio[i*frames:(i+1)*frames], bands) for i in range(count)]
    powers = np.array([tile['power'] for tile in tiles])
    fractions = np.array([tile['fractions'] for tile in tiles])
    mean = powers.mean(axis=0)
    total = mean.sum(axis=0)
    overall = np.divide(mean, total[None, :], out=np.zeros_like(mean), where=total[None, :] > 0)
    return dict(frames=len(audio), tile_frames=frames, tiles=count, omitted_tail_frames=len(audio)-count*frames,
        mean_power=mean.tolist(), fraction_of_mean_band_power=overall.tolist(),
        per_tile_power=powers.tolist(), per_tile_fraction=fractions.tolist(),
        fraction_range=np.stack((fractions.min(axis=0), fractions.max(axis=0))).tolist(),
        parseval_maximum_absolute_error=max(tile['parseval_error'] for tile in tiles),
        average_cell_power=np.mean([tile['cells'] for tile in tiles], axis=0),
        frequency=tiles[0]['frequency'])


def controls(bands, frames=24000):
    rate = 48000; time = np.arange(frames)/rate
    frequencies = [100, 300, 1000, 2000, 3500, 6500, 10000]
    amplitudes = np.array([.3, .2, .15, .1, .07, .05, .03])
    left = sum(a*np.cos(2*np.pi*f*time+.17*i) for i, (f, a) in enumerate(zip(frequencies, amplitudes)))
    audio = np.column_stack((left, .7*left))
    result = spectrum(audio, bands)
    expected = .5*amplitudes[:, None]**2*np.array([[1., .49]])
    error = float(abs(result['power']-expected).max())
    silence = spectrum(np.zeros_like(audio), bands)
    scaled = spectrum(audio*3, bands)
    scale_error = float(abs(scaled['power']-9*result['power']).max())
    assert error <= 1e-12 and scale_error <= 1e-12 and result['parseval_error'] <= 1e-12
    assert np.count_nonzero(silence['power']) == np.count_nonzero(silence['fractions']) == 0
    return dict(passed=True, analytic_band_power_maximum_error=error,
        scaled_power_maximum_error=scale_error, parseval_error=result['parseval_error'], silence_exact=True)
