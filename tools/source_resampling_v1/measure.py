"""Separate locked observer mass, Welch power, LR and signed changes."""
import numpy as np
from native_error_budget_v1.assessment import locked_rows
from extraction_sound_v1.measure import measure
from extraction_sound_v1.compare import compare


def summarize(variants, weights, amplitude):
    original = variants['legacy'][2048:-2048]
    base = measure(original, 65536)
    frequency = np.arange(2049)*16
    masks = [(frequency >= 14000) & (frequency < 16000),
        (frequency >= 16000) & (frequency < 18432), frequency == 18432, frequency > 18432]
    results, arrays = {}, {}
    for name, audio in variants.items():
        target = audio[2048:-2048]
        rows, power, _, _ = locked_rows(target, weights, amplitude)
        measured = measure(target, 65536)
        mass = (abs(rows)**2).sum(axis=0)
        arrays[name+'_weighted_mass'] = mass
        arrays[name+'_Welch_FS2'] = power
        for key, value in measured.items():
            arrays[name+'_measured_'+key] = value
        delta = target-original
        results[name] = dict(target_wave_NRMSE_vs_legacy=float(np.linalg.norm(delta)/np.linalg.norm(original)),
            target_wave_max_FS_vs_legacy=float(np.max(abs(delta))),
            highest_split_weighted_mass_LR=[mass[mask].sum(axis=0).tolist() for mask in masks],
            highest_split_Welch_FS2_LR=[power[mask].sum(axis=0).tolist() for mask in masks],
            signed_stereo_and_temporal_changes_vs_legacy=compare(measured, base)['broad'])
    return results, arrays
