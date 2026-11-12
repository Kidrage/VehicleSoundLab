"""One declared source evaluation after independent clock qualification only."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--validated', type=Path, required=True)
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from exterior_clock_v1.warp import warp
from phase_clock_v1.projection import independent_agreement
from startup_catch_v1.clock import diagnostics
from multicarrier_clock_v1.coarse import track
from multicarrier_clock_v1.phase import refine
from stationary_dna_v1.measure import moments, difference
from stationary_dna_v1.fit import fit, physical_playback, normalized_playback

args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.multicarrier-source-fit/1', result='running', sources={},
              model_exported=False, runtime_modified=False, vehicle_timbre_accepted=False)
try:
    validated = json.loads((args.validated/'report.json').read_text(encoding='utf-8'))
    assert validated['result'] == 'passed', 'Independent qualification incomplete: no source evaluation permitted'
    for name, digest in validated['sources'].items():
        assert sha(repo/name) == sha(args.validated/'exact_sources'/name) == digest
    clock_plan = json.loads((repo/'research/multicarrier_clock_v1_plan.json').read_text(encoding='utf-8'))
    assert validated['plan_sha256'] == sha(repo/'research/multicarrier_clock_v1_plan.json')
    original_plan = json.loads((repo/'research/E_stationary_dna_v1_plan.json').read_text(encoding='utf-8'))
    assert len(original_plan['cases']) == 1
    case = original_plan['cases'][0]
    assert case['seconds'] == [5.2, 7.8] and case['initial_root_hz'] == 32.8
    report.update(validation_report_sha256=sha(args.validated/'report.json'), source_case=case)
    observed_dir = args.workspace/'references/analysis/E_low_state_v1/observe2'
    observed_report = json.loads((observed_dir/'report.json').read_text(encoding='utf-8'))
    assert observed_report['result'] == 'observed_not_fitted' and observed_report['input']['source'] == 'E'
    measured_path = observed_dir/case['observation']/'observations_80ms.npz'
    segment = observed_report['segments'][case['observation']]
    assert sha(measured_path) == segment['observations']['80']['observations_sha256']
    report['observation_report_sha256'] = sha(observed_dir/'report.json')
    catalog = json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    entry = catalog['sources']['E']
    for kind in ('raw', 'master'):
        assert sha(args.workspace/entry[kind]) == entry[kind+'_sha256'] == observed_report['input'][kind+'_sha256']
    report['input'] = entry
    sources = [Path(__file__), repo/'research/multicarrier_clock_v1_plan.json',
               repo/'research/E_stationary_dna_v1_plan.json', repo/'references/segments_v1.json']
    for package in ('multicarrier_clock_v1', 'stationary_dna_v1', 'sound_dna',
                    'phase_clock_v1', 'exterior_clock_v1', 'startup_catch_v1'):
        sources += list((repo/'tools'/package).glob('*.py'))
    for source in sources:
        relative = source.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)
    with np.load(measured_path, allow_pickle=False) as archive:
        observed = {key: archive[key] for key in archive.files}
    lo, hi = segment['case']['seconds']
    with sf.SoundFile(args.workspace/entry['master']) as stream:
        assert (stream.samplerate, stream.channels, stream.subtype) == (48000, 2, 'FLOAT')
        stream.seek(round(lo*48000))
        audio = stream.read(round((hi-lo)*48000), dtype='float64', always_2d=True)
    path = track(observed, *case['seconds'], case['initial_root_hz'], clock_plan['coarse'])
    (args.out/'coarse.json').write_text(json.dumps(path, indent=2)+'\n', encoding='utf-8')
    report['track_status'] = path['status']
    if not path['rows']:
        report.update(result='source_coarse_rejected', candidate=None)
    else:
        times = np.array([row['seconds'] for row in path['rows']])
        roots = np.array([row['root_hz'] for row in path['rows']])
        try:
            normalized, where, initial = warp(audio, lo, times, roots, *case['seconds'])
            normalized, where, phase = refine(audio, lo, normalized, where,
                                              initial['source_cutoff_hz'], clock_plan['phase'])
            sf.write(args.out/'normalized_reference.wav', normalized, 48000, subtype='FLOAT')
            np.savez_compressed(args.out/'coordinates.npz', source_seconds=where)
            base = float(np.median(1/(1024*np.diff(where))))
            split = len(normalized)//2048*1024
            train, heldout = normalized[:split], normalized[split:]
            counts = [len(part)//4096 for part in (train, heldout)]
            independent = []
            for part in (train, heldout):
                checks = diagnostics(part, 0)
                independent.append(independent_agreement({key: item for key, item in checks.items()
                    if int(key) not in clock_plan['phase']['fit_orders']}))
            delta = difference(moments(train, base, clock_plan['harmonics'], clock_plan['bands_hz']),
                               moments(heldout, base, clock_plan['harmonics'], clock_plan['bands_hz']))
            power_error = float(abs(np.asarray(delta['power_difference_db_LR'])).max())
            correlation_error = float(max(delta['complex_correlation_difference']))
            passed = bool(phase['independent_agreement']['passed'] and all(item['passed'] for item in independent)
                          and min(counts)>=6 and power_error<=3 and correlation_error<=.2)
            report.update(result='source_holdout_measured', phase=phase, acoustic_root_hz=base,
                source_seconds=[float(where[0]), float(where[-1])], split_normalized_sample=split,
                nonoverlapping_four_cycle_windows=counts, independent_halves=independent,
                heldout_difference=delta, maximum_heldout_band_power_error_db=power_error,
                maximum_heldout_complex_correlation_error=correlation_error,
                stationary_scope_passed=passed, candidate=None)
            if passed:
                parameters = dict(harmonics=clock_plan['harmonics'], components=12)
                candidate_dir = args.out/'candidate'
                candidate = fit(train, base, parameters, candidate_dir, args.probe.resolve())
                sf.write(candidate_dir/'train_reference.wav', physical_playback(train, base), 48000, subtype='FLOAT')
                sf.write(candidate_dir/'heldout_reference.wav', physical_playback(heldout, base), 48000, subtype='FLOAT')
                generated, rate = sf.read(candidate_dir/'detail.wav', always_2d=True)
                assert rate == 48000
                generated = normalized_playback(generated, base)[round(base/46.875*48000):]
                candidate['heldout_vs_C_harmonic_observations'] = difference(
                    moments(heldout, base, clock_plan['harmonics'], clock_plan['bands_hz']),
                    moments(generated, base, clock_plan['harmonics'], clock_plan['bands_hz']))
                report.update(model_exported=True, candidate=candidate)
        except ValueError as exc:
            report.update(result='source_phase_rejected', reason=str(exc), candidate=None)
    report['limits'] = ['Conditional acoustic coordinate only; engine-cycle identity, physical RPM, warm idle and load are unverified',
                        'Original generic qualification unchanged; no source crop/reference/window alternatives or accepted-model replacement',
                        'Statistical model coverage and C generation do not establish naturalness or complete idle/acceleration timbre']
    print(json.dumps({key: report.get(key) for key in ('result', 'track_status', 'acoustic_root_hz',
        'stationary_scope_passed', 'maximum_heldout_band_power_error_db', 'maximum_heldout_complex_correlation_error',
        'model_exported', 'reason')}), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
