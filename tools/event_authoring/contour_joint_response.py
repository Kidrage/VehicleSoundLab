"""Opt-in simultaneous temporal/spectral fit of existing coarse event contours."""
from copy import deepcopy

import numpy as np
from scipy import optimize

from .contour_all_bands import observations
from .contour_joint import shape_errors
from .contour_knots import propose
from .contour_response import QuadraticResponse
from .contract import validate
from .measure import spectrum
from .model import synth
from .response_fit import EDGES
from .response_basis import calibrate_unit


def spectral_rows(f, power, targets):
    total=float(np.sum(targets))
    rows=[]
    for (lo,hi),wanted in zip(EDGES,targets):
        measured=float(power[(f>=lo)&(f<hi)].sum()*(f[1]-f[0]))
        db=float(10*np.log10(max(measured,1e-30)/max(wanted,1e-30)))
        significant=bool(wanted>=total*1e-4)
        passed=abs(db)<=3 if significant else measured<=max(wanted*2,total*2e-4)
        rows.append(dict(hz=[lo,hi],target_power=float(wanted),generated_power=measured,
            error_db=db,significant_target=significant,passed=bool(passed)))
    return rows


def fit(profile, x, background, arrays):
    duration = len(x)/48000
    time, target, rows = observations(x, background)
    indices = [k for k, row in enumerate(rows) if row['selected']]
    report = dict(method='band-contour-v5', bands=rows, selected_attempt=None,
                  qualified=False, groups_include_low_mid=True)
    if not indices:
        report['reason'] = 'No band has3dB event/background contrast'
        return deepcopy(profile), report, None
    baseline = shape_errors(profile, target, duration, indices)
    reference = target[indices]/np.maximum(target[indices].mean(axis=1), 1e-30)[:, None]
    weights = 1/np.maximum(baseline, .05)
    frequency, power, noise, *_ = arrays
    excess = np.maximum(power-noise, 0)
    spectral = np.array([excess[(frequency >= lo) & (frequency < hi)].sum() *
                         (frequency[1]-frequency[0]) for lo, hi in EDGES])
    total = float(spectral.sum())
    floor = total*1e-6
    spectral_significant = spectral >= total*1e-4
    spectral_wanted = np.where(spectral_significant, spectral, np.maximum(spectral*2, total*2e-4))
    spectral_weight = np.sqrt(reference.size/len(EDGES))
    attempts, candidates = [], []
    for layout in ('fixed', 'adaptive'):
        p = deepcopy(profile)
        p['contours'] = []
        for k, row in enumerate(rows):
            if not row['selected']:
                continue
            seconds = (propose(time, target[k], duration) if layout == 'adaptive' else
                (duration*np.array([0, .03125, .075, .15, .3125, .5625, .8125, 1.])).tolist())
            p['contours'].append(dict(low_hz=row['hz'][0], high_hz=row['hz'][1],
                                     seconds=seconds, gain=[1.]*len(seconds)))
        for step in range(7):
            if step:
                p = deepcopy(first_profile)
                p['noise_lowpass_hz'] = (0.,4000.,6000.,8000.,10000.,14000.)[step-1]
                p, calibration = calibrate_unit(p, arrays, duration)
            response = QuadraticResponse(p, duration)
            initial = np.concatenate([c['gain'] for c in p['contours']])

            def residual(g):
                power = response.power(response.temporal, g)[indices]
                shape = (power/np.maximum(power.mean(axis=1), 1e-30)[:, None]-reference)*weights[:, None]
                energy = response.power(response.spectral, g)
                energy = np.log(np.maximum(energy, 0)+floor)-np.log(spectral_wanted+floor)
                energy = np.where(spectral_significant, energy, np.maximum(energy, 0))*spectral_weight
                return np.r_[shape.ravel(), energy]

            def jacobian(g):
                power = response.power(response.temporal, g)[indices]
                derivative = response.derivative(response.temporal, g)[indices]
                mean = np.maximum(power.mean(axis=1), 1e-30)
                shape = (derivative/mean[:, None, None]-power[:, :, None] *
                    derivative.mean(axis=1)[:, None, :]/mean[:, None, None]**2)*weights[:, None, None]
                energy = response.power(response.spectral, g)
                spectrum_jac = response.derivative(response.spectral, g) / (np.maximum(energy, 0)+floor)[:, None]*spectral_weight
                active = spectral_significant | (energy > spectral_wanted)
                spectrum_jac *= active[:, None]
                return np.concatenate((shape.reshape(-1, response.count), spectrum_jac))

            result = optimize.least_squares(residual, initial, jac=jacobian, bounds=(0, 8),
                max_nfev=160, ftol=1e-9, xtol=1e-9, gtol=1e-9)
            offset = 0
            for contour, size in zip(p['contours'], response.sizes):
                contour['gain'] = result.x[offset:offset+size].tolist()
                offset += size
            validate(p)
            # Assess the actual synth, independently of the quadratic prediction.
            actual = synth(p, seconds=duration)
            f, actual_power = spectrum(actual[:, None])
            bands = spectral_rows(f,actual_power,spectral)
            seed_checks=[dict(seed=27431,bands=bands,qualified=all(row['passed'] for row in bands))]
            for seed in (48271,93931,17389):
                seed_f,seed_power=spectrum(synth(p,seed=seed,seconds=duration)[:,None])
                checked=spectral_rows(seed_f,seed_power,spectral)
                seed_checks.append(dict(seed=seed,bands=checked,qualified=all(row['passed'] for row in checked)))
            spectral_report = dict(method='simultaneous-contour-response-v1', bands=bands,
                qualified=all(row['qualified'] for row in seed_checks), amplitude_contract_fits=True,
                seed=27431, selection_seed_checks=seed_checks,target_positive_psd_excess_power=total)
            errors = shape_errors(p, target, duration, indices)
            temporal = all(a <= b+1e-10 for a, b in zip(errors, baseline))
            qualified = bool(spectral_report['qualified'] and temporal)
            score = float(np.mean((np.asarray(errors)*weights)**2))
            index = len(attempts)
            attempts.append(dict(layout=layout, step=step, shape_rmse=errors, response=spectral_report,
                temporal_nonregression=temporal, qualified=qualified, score=score,
                evaluations=result.nfev, optimizer_terminated=bool(result.success),
                controls=response.count, peak=float(np.max(abs(actual))),
                noise_lowpass_hz=p.get('noise_lowpass_hz',0.),
                preceding_calibration=calibration if step else None))
            if qualified:
                candidates.append((score, index, deepcopy(p), spectral_report))
            if not step:
                first_profile = deepcopy(p)
    report.update(attempts=attempts, baseline_shape_rmse=baseline,
        policy='Only independently>=3dB60..14000Hz groups receive<=8 existing amplitude knots. Two fixed/adaptive layouts: one simultaneous solve, then one recalibration/solve per original six source-noise cutoff choices; <=160 joint evaluations per solve, at most14 candidates. Mean-normalized temporal errors weighted by inverse max(entry RMSE,.05), six log spectral errors balanced by sqrt(temporal residual count/6). Weak spectral targets use only their original upper bound, never a requirement to synthesize tiny subtraction residue. Original six spectral gates and per-reliable-band temporal nonregression are mandatory. Every selectable candidate ends with a simultaneous solve and actual-synth gates. Phases, frequencies, local weak-band envelopes and runtime capacity stay fixed.',
        selection_seeds=[27431,48271,93931,17389],
        limitations='This fits coarse acoustic energy, not mechanical texture, source separation or physical RPM. Temporal fitting uses27431; all four declared selection seeds must pass the original six spectral gates. These are selection data, not held-out validation or timbre acceptance. Output is sparse parameters only; no recording playback or new room processing.')
    if not candidates:
        report['reason'] = 'No simultaneous contour layout passes the original spectral and temporal gates'
        return deepcopy(profile), report, attempts[-1]['response']
    _, choice, p, spectral_report = min(candidates, key=lambda row: (row[0], row[1]))
    report.update(qualified=True, selected_attempt=choice,
                  adaptive_selected=attempts[choice]['layout'] == 'adaptive')
    return validate(p), report, spectral_report
