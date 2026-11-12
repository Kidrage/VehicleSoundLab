"""Absolute-Hz observations; deliberately independent of cycle normalization."""
import numpy as np
from residual_osc_v1.spectrum import matrices, error
from startup_detail_v1.budget import additive
from stereo_field_v1.budget import matrix

BANDS = [(20,300),(300,1200),(1200,3000),(3000,6000),(6000,8000),
         (8000,10000),(10000,12000),(12000,16000),(16000,20000)]


def observe(audio):
    rows = matrices(audio, BANDS)
    total = np.sum([v['power'] for v in rows], axis=0)
    for row in rows:
        row['fraction_of_20_20000_power'] = (np.asarray(row['power'])/total).tolist()
    return rows


def budget(target, base, bands):
    return [dict(hz=t['hz'], target=t, base=b, **additive(matrix(t), matrix(b)))
            for t,b in zip(matrices(target,bands), matrices(base,bands))]


def compare(target, candidate, bands):
    return error(matrices(target,bands), matrices(candidate,bands))


def known_controls():
    # A center-bin high tone must survive absolute-Hz measurement. A lower
    # tone must not masquerade as missing HF through FFT indexing/leakage.
    t=np.arange(48000)/48000
    high=.1*np.cos(2*np.pi*12000*t)
    low=.1*np.cos(2*np.pi*1500*t)
    x=np.column_stack((high+low, .7*high+.7*low))
    rows=matrices(x,[(1400,1600),(11000,13000)])
    expected=np.array([.005,.005*.49])
    tone_error=max(float(np.max(abs(np.array(v['power'])/expected-1))) for v in rows)
    assert tone_error<1e-10,tone_error
    pure_low=matrices(np.column_stack((low,low)),[(8000,16000)])[0]
    leakage=float(max(pure_low['power'])/.005)
    assert leakage<1e-20,leakage
    # Analytic stereo positive and impossible additive budgets.
    target=np.array([[3, .3+.2j],[.3-.2j,2]],complex)
    base=np.eye(2)*.5
    positive=additive(target,base)
    assert positive['accepted'] and positive['reconstruction_error_relative']<1e-14
    negative=additive(np.eye(2),np.eye(2)*2)
    assert not negative['accepted'] and negative['power']==[0.,0.]
    return dict(relative_tone_power_error=tone_error,low_tone_HF_leakage_ratio=leakage,
                analytic_stereo_budget=True,negative_budget_kept_silent=True)
