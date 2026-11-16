"""Original native observer plus explicit four upper physical subgroups."""
import numpy as np
from extraction_sound_v1.measure import measure
from native_clock_case_v1.diagnostics import comparison, convergence


def observe(values):
    measured = {name:measure(audio, 48000) for name, audio in values.items()}
    arrays = {name+'_audio':audio for name, audio in values.items()}
    for name, fields in measured.items():
        arrays.update({name+'_'+k:v for k,v in fields.items()})
        audio = values[name]; starts = fields['starts']
        window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
        x = np.fft.rfft(audio[starts[:, None]+np.arange(4096)]*window[None, :, None], axis=1)
        f = fields['frequency']; edge = np.r_[1., np.full(2047, 2.), 1.]/(4096*np.dot(window, window))
        ms_all = np.stack(((x[:, :, 0]+x[:, :, 1])/2, (x[:, :, 0]-x[:, :, 1])/2), axis=2)
        arrays.update({name+'_bin_power':abs(x)**2*edge[None, :, None],
            name+'_bin_cross':x[:, :, 0]*x[:, :, 1].conj()*edge,
            name+'_bin_mid_side':abs(ms_all)**2*edge[None, :, None]})
        powers, crosses, ms = [], [], []
        for lo, hi in ((14000, 16000), (16000, 20000), (20000, 22000), (22000, 24001)):
            mask = (f >= lo)&(f < hi); a = x[:, mask]; w = edge[mask]
            powers.append(np.sum(abs(a)**2*w[None, :, None], axis=1))
            crosses.append(np.sum(a[:, :, 0]*a[:, :, 1].conj()*w, axis=1))
            b = np.stack(((a[:, :, 0]+a[:, :, 1])/2, (a[:, :, 0]-a[:, :, 1])/2), axis=2)
            ms.append(np.sum(abs(b)**2*w[None, :, None], axis=1))
        arrays.update({name+'_upper_power':np.asarray(powers).transpose(1, 0, 2),
            name+'_upper_cross':np.asarray(crosses).T, name+'_upper_mid_side':np.asarray(ms).transpose(1, 0, 2)})
    return measured, arrays


def compare_all(values, measured, pairs):
    return {a+'_vs_'+b:comparison(values[a], values[b], measured[a], measured[b]) for a,b in pairs}
