"""Independent per-channel FFT, scalar band sums and every temporal Gram."""
import numpy as np
from locked_source_tail_v1.audit_measure import masks, LABELS


def verify(audio, saved, prefix):
    audio = audio[2048:-2048]
    starts = np.arange(0, len(audio)-4096+1, 256)
    k = np.arange(4096); window = .5-.5*np.cos(2*np.pi*k/4096)
    edge = np.r_[1., np.full(2047, 2.), 1.]/(4096*np.sum(window**2))
    power, cross, ms = [], [], []
    for start in starts:
        a = np.column_stack([np.fft.rfft(audio[start:start+4096, c]*window) for c in (0, 1)])
        pp, cc, mm = [], [], []
        for mask in masks():
            pp.append([np.sum((a[mask, c].real**2+a[mask, c].imag**2)*edge[mask]) for c in (0, 1)])
            cc.append(np.sum(a[mask, 0]*a[mask, 1].conj()*edge[mask]))
            mid = (a[mask, 0]+a[mask, 1])/2; side = (a[mask, 0]-a[mask, 1])/2
            mm.append([np.sum(abs(value)**2*edge[mask]) for value in (mid, side)])
        power.append(pp); cross.append(cc); ms.append(mm)
    power, cross, ms = map(np.asarray, (power, cross, ms))
    mean = power.mean(axis=0); defined = mean > 0
    normalized = np.zeros(power.shape)
    for b in range(10):
        for c in (0, 1):
            if defined[b, c]:
                normalized[:, b, c] = power[:, b, c]/mean[b, c]-1
    flat = normalized.reshape(len(power), 20)
    covariance = np.array([[np.sum(flat[:, i]*flat[:, j])/len(flat) for j in range(20)] for i in range(20)])
    denom = np.sqrt(mean[:, 0]*mean[:, 1])
    coh = np.divide(cross.mean(axis=0), denom, out=np.zeros(10, complex), where=denom>0)
    values = dict(starts=starts, power=power, cross=cross, mid_side=ms, mean_power=mean,
        mean_mid_side=ms.mean(axis=0), CV=np.sqrt(np.mean(normalized**2, axis=0)),
        covariance=covariance, complex_coherence=coh, power_defined=defined)
    checks = {}
    for key, expected in values.items():
        got = saved[prefix+'__stereo_'+key]
        assert expected.shape == got.shape
        if key in ('starts', 'power_defined'):
            assert np.array_equal(got, expected)
            continue
        if key in ('cross', 'complex_coherence', 'covariance'):
            scale = max(float(np.max(abs(expected))), np.finfo(float).tiny)
            error = float(np.max(abs(got-expected))/scale)
        else:
            denom = np.maximum(abs(got), abs(expected))
            error = float(np.max(np.divide(abs(got-expected), denom, out=np.zeros_like(denom), where=denom>0)))
        assert error < 2e-12, (key, error)
        checks[key] = error
    return values, checks


def compare(old, new, report):
    checks = 0
    for k, row in enumerate(report['bands']):
        assert row['band'] == LABELS[k]
        values = dict(old_Welch_FS2_LR=old['mean_power'][k], C1_Welch_FS2_LR=new['mean_power'][k],
            power_change_dB_LR=10*np.log10(new['mean_power'][k]/old['mean_power'][k]),
            coherence_complex_difference=abs(new['complex_coherence'][k]-old['complex_coherence'][k]),
            old_Side_Mid_dB=10*np.log10(old['mean_mid_side'][k, 1]/old['mean_mid_side'][k, 0]),
            C1_Side_Mid_dB=10*np.log10(new['mean_mid_side'][k, 1]/new['mean_mid_side'][k, 0]),
            CV_change_LR=new['CV'][k]-old['CV'][k])
        for key, expected in values.items():
            assert np.max(abs(np.asarray(row[key])-expected)) < 2e-12*max(1., float(np.max(abs(expected))))
            checks += np.asarray(expected).size
    assert abs(report['normalized_covariance_max_change']-np.max(abs(new['covariance']-old['covariance']))) < 2e-12
    return dict(verified_report_values=int(checks)+1, both_LR_complex_cross_direct_MS_and_time=True)
