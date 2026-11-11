"""Separate log-band common gain and colour; neither is a physical source."""
import numpy as np


DB = 20 / np.log(10)


def band_power(audio, plan):
    size, hop, rate = (plan[k] for k in ('size', 'hop', 'sample_rate'))
    starts = np.arange(0, len(audio) - size + 1, hop)
    window = .5 - .5 * np.cos(2 * np.pi * np.arange(size) / size)
    hz = np.fft.rfftfreq(size, 1 / rate)
    masks = np.array([(hz >= lo) & (hz < hi) for lo, hi in plan['bands']])
    scale = np.ones(len(hz)) / (size * np.sum(window * window))
    scale[1:-1] *= 2
    # Bound temporary memory independently of recording length.
    result = []
    for at in range(0, len(starts), 128):
        frame = audio[starts[at:at+128, None] + np.arange(size)]
        z = np.fft.rfft(frame * window[None, :, None], axis=1)
        result.append(np.einsum('wfc,bf->wbc', abs(z)**2 * scale[None, :, None], masks))
    return starts, np.concatenate(result)


def decompose(power, order, period, slow_band, floor):
    """Equal band weights make common/shape orthogonal in log amplitude."""
    amplitude_log = .5 * np.log(np.maximum(power, floor))
    t = np.linspace(-1, 1, len(power))
    design = np.column_stack([t**k for k in range(order + 1)])
    flat = amplitude_log.reshape(len(power), -1)
    motion = (flat - design @ np.linalg.lstsq(design, flat, rcond=None)[0]).reshape(power.shape)
    common = motion.mean(axis=1)
    shape = motion - common[:, None, :]
    count = power.shape[1]
    total_variance = np.mean(motion**2, axis=(0, 1))
    common_variance = np.mean(common**2, axis=0)
    shape_variance = np.mean(shape**2, axis=(0, 1))
    denominator = np.maximum(total_variance, 1e-24)
    decomposition_error = np.max(abs(total_variance-common_variance-shape_variance) / denominator)

    def spectrum(x):
        result = abs(np.fft.rfft(x, axis=0))**2 / len(x)**2
        result[1:-1 if len(x)%2 == 0 else None] *= 2
        return result

    full_spectrum, common_spectrum, shape_spectrum = map(spectrum, (motion, common, shape))
    hz = np.fft.rfftfreq(len(power), period)
    mask = (hz > slow_band[0]) & (hz < slow_band[1])
    total_slow = full_spectrum[mask].sum(axis=0).mean(axis=0)
    common_slow = common_spectrum[mask].sum(axis=0)
    shape_slow = shape_spectrum[mask].sum(axis=0).mean(axis=0)
    parseval_error = np.max(abs(full_spectrum.sum(axis=0)-np.mean(motion**2,axis=0)) /
                            np.maximum(np.mean(motion**2,axis=0),1e-24))
    slow_error = np.max(abs(total_slow-common_slow-shape_slow) / np.maximum(total_slow,1e-24))
    # Slope is measured before detrending. It describes the observation only.
    seconds = np.arange(len(power))*period
    slope_design = np.column_stack((np.ones(len(power)), seconds-seconds.mean()))
    slopes = np.linalg.lstsq(slope_design, amplitude_log.reshape(len(power),-1),rcond=None)[0][1]
    row = dict(
        frames=len(power),first_positive_modulation_hz=float(hz[1]),
        actual_slow_bins_hz=hz[mask].tolist(),
        common_variance_fraction_LR=(common_variance/denominator).tolist(),
        slow_common_variance_fraction_LR=(common_slow/np.maximum(total_slow,1e-24)).tolist(),
        all_rms_db_LR=(DB*np.sqrt(total_variance)).tolist(),
        common_rms_db_LR=(DB*np.sqrt(common_variance)).tolist(),
        shape_rms_db_LR=(DB*np.sqrt(shape_variance)).tolist(),
        slow_common_rms_db_LR=(DB*np.sqrt(common_slow)).tolist(),
        slow_shape_rms_db_LR=(DB*np.sqrt(shape_slow)).tolist(),
        slow_shape_rms_per_band_db_LR=(DB*np.sqrt(shape_spectrum[mask].sum(axis=0))).tolist(),
        common_slope_db_per_second_LR=(DB*slopes.reshape(count,2).mean(axis=0)).tolist(),
        decomposition_relative_error=float(decomposition_error),
        slow_decomposition_relative_error=float(slow_error),
        parseval_relative_error=float(parseval_error),
        floored_band_frames=int(np.sum(power<floor)))
    return row, dict(motion=motion, common=common, shape=shape,
                     full_spectrum=full_spectrum, common_spectrum=common_spectrum,
                     shape_spectrum=shape_spectrum, modulation_hz=hz)


def analyze(starts, power, audio_frames, plan):
    rows = []
    rate = plan['sample_rate']
    for length in plan['block_seconds']:
        block = round(length*rate)
        for offset in plan['offset_fractions']:
            first = round(offset*block)
            for at in range(first, audio_frames-block+1, block):
                selected = (starts>=at)&(starts+plan['size']<=at+block)
                for order in plan['detrend_orders']:
                    row,_ = decompose(power[selected],order,plan['hop']/rate,
                                      plan['slow_band_hz'],plan['minimum_power'])
                    rows.append(dict(block_seconds=length,offset_fraction=offset,
                        start_frame=at,stop_frame=at+block,detrend_order=order,**row))
    return rows


def summarize(rows):
    result = []
    keys = ('common_variance_fraction_LR','slow_common_variance_fraction_LR',
            'all_rms_db_LR','common_rms_db_LR','shape_rms_db_LR',
            'slow_common_rms_db_LR','slow_shape_rms_db_LR',
            'slow_shape_rms_per_band_db_LR','common_slope_db_per_second_LR')
    configs = sorted({(r['block_seconds'],r['offset_fraction'],r['detrend_order']) for r in rows})
    for length,offset,order in configs:
        group = [r for r in rows if (r['block_seconds'],r['offset_fraction'],r['detrend_order']) == (length,offset,order)]
        result.append(dict(block_seconds=length,offset_fraction=offset,detrend_order=order,
            blocks=len(group),modulation_resolution_hz=group[0]['first_positive_modulation_hz'],
            medians={key:np.median([r[key] for r in group],axis=0).tolist() for key in keys},
            ranges={key:[np.min([r[key] for r in group],axis=0).tolist(),
                         np.max([r[key] for r in group],axis=0).tolist()] for key in keys}))
    return result


def scalar_power_check(audio, starts, power, plan):
    size,rate = plan['size'],plan['sample_rate']
    at = np.arange(size);window=.5-.5*np.cos(2*np.pi*at/size)
    hz=np.fft.rfftfreq(size,1/rate);errors=[]
    for frame in sorted({0,len(starts)//2,len(starts)-1}):
        for band in (0,3,6):
            lo,hi=plan['bands'][band];bins=np.flatnonzero((hz>=lo)&(hz<hi))
            phase=2*np.pi*bins[:,None]*at/size
            z=(np.cos(phase)-1j*np.sin(phase))@(audio[starts[frame]:starts[frame]+size]*window[:,None])
            actual=(abs(z)**2).sum(axis=0)*2/(size*np.sum(window**2))
            errors.append(float(np.max(abs(actual-power[frame,band])/np.maximum(power[frame,band],1e-24))))
    return max(errors)
