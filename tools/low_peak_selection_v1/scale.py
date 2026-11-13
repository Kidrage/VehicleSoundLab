"""Reuse the phase-free matcher, with explicit cross-band agreement evidence."""
import copy
import numpy as np
from accel_material_v1.features import whiten,scale_match
from idle_material_v1.features import spectrum


def feature(audio,plan):
    observed=spectrum(audio,plan['bands_hz'])
    return whiten(observed['cells'],observed['frequency'],plan['spectral_scale']),observed


def compare(reference,current,plan):
    settings=plan['spectral_scale']
    global_match=scale_match(reference,current,settings)
    local=[scale_match(reference,current,dict(settings,comparison_hz=band))
        for band in plan['independent_comparison_bands_hz']]
    shifts=[row['shift_bins'] for row in local]
    spread=max(shifts)-min(shifts)
    supported=global_match['supported'] and all(row['supported'] for row in local) and spread<=plan['maximum_band_shift_spread_bins']
    return dict(global_match=global_match,band_matches=local,band_shift_spread_bins=spread,supported=bool(supported))


def controls(plan):
    n=plan['native_frames'];time=np.arange(n)/48000
    orders=np.arange(3,451);frequencies=orders*10.613
    amplitude=.07*orders**-.65;phase=orders*.173
    def wave(ratio=1.,colour=0.,split=False):
        ratios=np.where(frequencies<1100,2**(-128/1536),2**(128/1536)) if split else np.full(len(orders),ratio)
        amp=amplitude*(frequencies/1500)**colour
        y=sum(amp[k]*np.cos(2*np.pi*frequencies[k]*ratios[k]*time+phase[k]) for k in range(len(orders)))
        return np.column_stack((y,.67*y))
    reference,_=feature(wave(),plan);rows=[]
    for shift in [-512,0,512,1024]:
        current,_=feature(wave(2**(shift/1536)),plan)
        match=compare(reference,current,plan)
        assert abs(match['global_match']['shift_bins']-shift)<=8,(shift,match)
        assert match['supported'],(shift,match)
        rows.append(dict(expected_shift=shift,measured_shift=match['global_match']['shift_bins'],
            band_shift_spread=match['band_shift_spread_bins']))
    changed,_=feature(wave(colour=.4),plan);colour=compare(reference,changed,plan)
    assert colour['supported'] and abs(colour['global_match']['shift_bins'])<=8
    quiet,_=feature(.21*wave(),plan);error=float(abs(quiet-reference).max());assert error<1e-8
    silence,_=feature(np.zeros((n,2)),plan);silent=compare(reference,silence,plan);assert not silent['supported']
    split,_=feature(wave(split=True),plan);divergent=compare(reference,split,plan)
    assert not divergent['supported'],divergent
    # Store full control observations, including candidate scores, outside a synthesis profile.
    return dict(dense_known_scales=rows,colour=colour,gain_feature_error=error,
        silence_rejected=True,split_spectrum_rejected=divergent)
