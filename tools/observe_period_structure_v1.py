"""Diagnose the frozen E coordinate without fitting another clock or voice."""
import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read, sha
from exterior_clock_v1.warp import warp, CYCLE
from period_structure_v1.spectrum import observe as spectral_observation
from period_structure_v1.phase import observe as phase_observation
from period_structure_v1.fixtures import cases


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def observations(audio, samples_per_cycle, root, plan, directory):
    directory.mkdir()
    split = len(audio)//2
    parts = {'full': audio, 'first_half': audio[:split], 'last_half': audio[split:]}
    result, arrays = {}, {}
    for name, part in parts.items():
        measured, (orders, power, starts, powers) = spectral_observation(part, samples_per_cycle, root, plan)
        result[name] = measured
        np.savez_compressed(directory/(name+'.npz'), orders=orders, power=power, starts=starts, per_window_power=powers)
        arrays[name] = (orders, power)
    save(directory/'spectrum.json', result)
    return result, arrays


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.period-structure-observation/1', result='running', sources={}, fixtures=[],
    model_exported=False, runtime_changed=False, real_C_render_executed=False, vehicle_timbre_accepted=False)
try:
    plan_path = repo/'research/period_structure_v1_plan.json'
    plan = load(plan_path)
    report['plan_sha256'] = sha(plan_path)
    source_files = [Path(__file__), plan_path, repo/'references/segments_v1.json',
        repo/'tools/drive_evidence_v1/sources.py', repo/'tools/exterior_clock_v1/warp.py',
        repo/'modules/sound_dna/profile.h']+list((repo/'tools/period_structure_v1').glob('*.py'))
    for source in source_files:
        relative = source.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)

    # Qualify the meter before using it on the real observation. These tests
    # establish frequency/phase measurements and a non-identifiability example,
    # not a general engine-period detector.
    fixtures, ambiguity_error = cases()
    for case in fixtures:
        item, _ = spectral_observation(case['audio'], CYCLE, 33., plan['spectrum'])
        expected = case['expected']
        row = dict(id=case['id'], observation=item, passed=True)
        if expected is not None:
            errors = []
            for channel in item['channels']:
                found = np.array([peak['order'] for peak in channel['peaks']])
                if not len(found):
                    raise ValueError('Analytic tones were absent from the measured spectrum')
                errors.append(float(np.min(abs(found[:, None]-expected[None, :]), axis=0).max()))
            row['maximum_expected_peak_order_error_LR'] = errors
            row['passed'] &= max(errors) <= plan['fixture_gate']['maximum_peak_order_error']
        if case['id'] == 'integer_delayed_stereo':
            phase = phase_observation(case['audio'], CYCLE, plan['phase'])
            drift = max(pair['worst_p95_relative_drift_cycles'] for pair in phase['pairs'])
            row['maximum_pair_phase_drift_cycles'] = drift
            row['passed'] &= drift <= plan['fixture_gate']['maximum_pair_drift_cycles']
            row['passed'] &= all(channel['lattice']['fractional_peaks'] == 0 for channel in item['channels'])
        if case['id'] == 'noise_only':
            row['passed'] = None
            row['interpretation'] = 'Noise occupies fractional grids too; this observation cannot establish a source period'
        report['fixtures'].append(row)
    report['AM_long_period_sample_difference'] = ambiguity_error
    report['fixture_scope'] = 'Fixed analytic frequency observations, stable phase pairs and exact AM ambiguity only; no engine-period classification gate'
    assert all(row['passed'] for row in report['fixtures'] if row['id'] != 'noise_only')
    assert ambiguity_error <= plan['fixture_gate']['maximum_ambiguous_waveform_difference']
    save(args.out/'fixtures.json', {key: report[key] for key in ('fixtures', 'AM_long_period_sample_difference', 'fixture_scope')})

    # Reuse frozen coarse coordinates. No track(), polish() or refine() call.
    prior_path, coarse_path = [args.workspace/plan[key] for key in ('prior_report', 'coarse_report')]
    prior, coarse = load(prior_path), load(coarse_path)
    assert prior['result'] == 'source_phase_rejected' and prior['track_status'] == coarse['status'] == 'measured_consensus'
    assert prior['source_case']['seconds'] == plan['source_seconds'] == [5.2, 7.8]
    report['prior_report_sha256'], report['saved_coarse_sha256'] = sha(prior_path), sha(coarse_path)
    shutil.copy2(prior_path, args.out/'prior_report.json')
    shutil.copy2(coarse_path, args.out/'saved_coarse.json')
    assert sha(repo/'references/segments_v1.json') == sha(args.workspace/'references/segments_v1.json')
    audio, provenance = read(args.workspace, plan['segment'], 'exterior_spectral_observation')
    assert provenance['source'] == plan['source'] and provenance['master_sha256'] == prior['input']['master_sha256']
    report['input'] = provenance
    rows = coarse['rows']
    times = np.array([row['seconds'] for row in rows])
    roots = np.array([row['root_hz'] for row in rows])
    normalized, positions, warp_evidence = warp(audio, provenance['seconds'][0], times, roots, *plan['source_seconds'])
    report['initial_warp'] = warp_evidence
    np.savez_compressed(args.out/'initial_coordinates_and_stereo.npz', source_seconds=positions, stereo=normalized)
    base = float(np.median(1/(CYCLE*np.diff(positions))))
    report['display_root_hz'] = base
    first, last = [round((time-provenance['seconds'][0])*48000) for time in plan['source_seconds']]
    original = audio[first:last]
    raw_report, raw_arrays = observations(original, 48000/base, base, plan['spectrum'], args.out/'raw')
    normalized_report, normalized_arrays = observations(normalized, CYCLE, base, plan['spectrum'], args.out/'coarse_coordinate')
    report['raw_spectrum'], report['coarse_coordinate_spectrum'] = raw_report, normalized_report
    report['phase_pairs'] = phase_observation(normalized, CYCLE, plan['phase'])
    save(args.out/'phase_pairs.json', report['phase_pairs'])

    # A lower fundamental also needs a wider representation. Report the exact
    # existing capacity, without silently changing the coordinate or lowpass.
    maximum = int(re.search(r'#define SD_MAX_HARMONICS (\d+)', (repo/'modules/sound_dna/profile.h').read_text()).group(1))
    report['conditional_bandwidth_budget'] = [dict(divisor=divisor, hypothetical_root_hz=base/divisor,
        current_max_harmonics=maximum, current_harmonic_ceiling_hz=maximum*base/divisor,
        current_warp_lowpass_hz=min(14000., .38*CYCLE*float(min(roots))/divisor),
        harmonics_required_through_14khz=int(np.ceil(14000/(base/divisor))),
        cycle_samples_required_for_existing_antialias_margin=int(np.ceil(14000/(.38*float(min(roots))/divisor))))
        for divisor in (1, 2, 3, 4, 5, 6, 7, 8)]

    figure, axes = plt.subplots(3, 1, figsize=(12, 9), constrained_layout=True)
    for name, arrays, style in [('original source', raw_arrays, '-'), ('saved coarse coordinate', normalized_arrays, '--')]:
        for half, color in [('first_half', 'tab:blue'), ('last_half', 'tab:orange')]:
            order, power = arrays[half]
            selected = (order*base>=35)&(order*base<1000)
            axes[0].plot(order[selected]*base, 10*np.log10(np.maximum(power[selected, 0],1e-30)),
                label=name+' / '+half, color=color, linestyle=style, linewidth=.8, alpha=.85)
    axes[0].set(xlabel='Equivalent Hz (coarse median used for normalized display only)', ylabel='L coherent-normalized bin power (dB)', xlim=(35, 1000))
    axes[0].legend(fontsize=7)
    for half, color in [('first_half', 'tab:blue'), ('last_half', 'tab:orange')]:
        peaks = normalized_report[half]['channels'][0]['peaks']
        order = np.array([row['order'] for row in peaks])
        levels = np.array([row['relative_db'] for row in peaks])
        axes[1].scatter(order%1, levels, color=color, label=half, s=18)
    for residue in np.arange(.2, 1, .2):
        axes[1].axvline(residue, color='gray', linestyle=':', alpha=.5)
    axes[1].set(xlabel='Peak order modulo 1 in the existing ~33 Hz coordinate', ylabel='L peak relative power (dB)', xlim=(0, 1), ylim=(-31, 1))
    axes[1].legend(fontsize=8)
    pairs = [row for row in report['phase_pairs']['pairs'] if row['channel']=='L']
    axes[2].bar(np.arange(len(pairs)), [row['worst_p95_relative_drift_cycles'] or 0 for row in pairs])
    axes[2].set(xticks=np.arange(len(pairs)), xticklabels=['/'.join(map(str,row['orders'])) for row in pairs],
        xlabel='Supported L carrier pairs; missing segments remain absent in JSON', ylabel='p95 relative phase drift (coarse cycles)')
    for axis in axes:
        axis.grid(alpha=.2)
    figure.suptitle('E 5.2-7.8 s: diagnostic only, no new period or engine RPM asserted\nSame declared windows and saved coordinate; original phase rejection retained')
    figure.savefig(args.out/'period_structure.png', dpi=140)
    plt.close(figure)

    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='') as stream:
        index = list(csv.DictReader(stream))
    assert len(index) == 540 and all(sha(repo/row['文件']) == row['SHA-256'] for row in index)
    c_hashes = {row['文件']: row['SHA-256'] for row in index}
    voice_hashes = load(args.workspace/'references/analysis/multicarrier_clock_v1/final1/voice_files_sha256.json')
    assert all(sha(repo/name) == digest for name, digest in voice_hashes.items())
    save(args.out/'C_files_sha256.json', c_hashes)
    save(args.out/'voice_files_sha256.json', voice_hashes)
    assert sha(prior_path) == report['prior_report_sha256'] and sha(coarse_path) == report['saved_coarse_sha256']
    report.update(result='observed_no_new_clock_or_model', C_H=540, Ctests_rerun=False,
        moving35='held_unchanged', idle_acceleration_complete=False,
        interpretation='Inspect spectral occupancy and pair drift together. No fractional occupancy score establishes a true engine-cycle divisor.',
        limits=['Single existing E interval and coarse coordinate; no fitted lower-period clock',
            'Equal halves are descriptive stability checks, not passed independent DNA holdouts',
            'Warm idle, ECU RPM, load and background/engine separation remain unverified',
            'Bandwidth budgets are conditional capacity calculations, not permission to export or truncate a new model'])
    print(json.dumps(dict(result=report['result'], root_hz=base, fixture_count=len(fixtures),
        ambiguity_max_error=ambiguity_error, phase_L=[dict(orders=row['orders'], p95=row['worst_p95_relative_drift_cycles'])
            for row in report['phase_pairs']['pairs'] if row['channel']=='L'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    save(args.out/'report.json', report)
