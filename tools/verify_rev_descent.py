"""Independent signal controls and read-only history audit for rev_descent_v1."""
import json
from dataclasses import replace
from pathlib import Path
from runtime_review import ROOT, sha
from reference_segments import read_segment
from review_audit import frozen_baselines
from ridge_tracks import RidgeSettings, spectrogram, follow
import numpy as np

OUT = ROOT/'references/analysis/rev_descent_v1'
COUNTS = {'v0.1.0':23, 'v0.2.0':64, 'v0.3.0':81, 'v0.4.0':99,
    'v0.5.0':112, 'v0.6.0':161, 'v0.7.0':157, 'v0.8.0':182,
    'v0.9.0':190, 'v0.10.0':205, 'v0.11.0':189, 'v0.12.0':156, 'v0.13.0':167}


def phase_reversal_control():
    rate = 48000
    t = np.arange(round(1.6*rate))/rate
    truth = 5*63*2**(-t)
    phase = 2*np.pi*np.cumsum(truth)/rate
    left = .1*np.cos(phase)+.025*np.cos(2*np.pi*100*t)
    x = np.column_stack([left, -left])
    settings = RidgeSettings()
    hz, times, power = spectrogram(x, rate, settings)
    tracks = []
    for p in [power.mean(axis=1), power[:, 0, :], power[:, 1, :]]:
        run = follow(hz, times, p, .2, 1.2, 5*63*2**(-.2), settings)
        assert run['status'] == 'connected_peak_path' and run['support_fraction'] == 1
        frequency = np.array([r['hz'] for r in run['rows']])
        tt = np.array([r['seconds'] for r in run['rows']])
        error = abs(1200*np.log2(frequency/np.interp(tt, t, truth)))
        assert np.percentile(error, 95) < 15
        tracks.append(frequency)
    delta = max(float(np.max(abs(f-tracks[0]))) for f in tracks)
    assert delta < 1e-10 and np.max(abs(x.mean(axis=1))) == 0
    return dict(status='pass', waveform_sum_is_zero=True,
        maximum_mean_power_vs_individual_path_difference_hz=delta,
        explanation='Opposite waveform channels cancel in a mono sum; independent PSD/power selection still tracks the known chirp.')


def sensitivity(result):
    audio, rate, provenance = read_segment('A_exterior_blips', 'exterior_dynamic_observation')
    assert provenance == result['reference']
    settings = RidgeSettings()
    hz, times, power = spectrogram(audio, rate, settings)
    times += provenance['source_seconds'][0]
    base = np.array([r['hz'] for r in result['runs']['first_upper_128ms_mean_power']['rows']])
    reports = []
    for bound in [1.8, 2.6, 4.0]:
        for cost in [0., .15, .30]:
            cfg = replace(settings, max_octaves_per_second=bound, continuity_cost=cost)
            run = follow(hz, times, power.mean(axis=1), 238.18, 239., 315, cfg)
            assert run['status'] == 'connected_peak_path' and run['support_fraction'] == 1
            estimate = np.array([r['hz'] for r in run['rows']])
            delta = float(np.max(abs(base-estimate)))
            assert delta < 2
            reports.append(dict(max_octaves_per_second=bound, continuity_cost=cost,
                maximum_frequency_difference_from_primary_hz=delta))
    return dict(status='pass', runs=reports,
        scope='Selected first upper ridge only. Stability to these choices is not unrestricted detector validation or a statistical error bound.')


def runtime_audit():
    path = ROOT/'renders/v0.13.0/workspace_audit.json'
    audit = json.loads(path.read_text())
    assert audit['result'] == 'pass' and audit['version'] == '0.13.0'
    for group in ['source_code', 'deliverables']:
        for name, digest in audit[group].items():
            assert sha(ROOT/name) == digest, name
    for name, digest in audit['rendered_artifacts'].items():
        assert sha(ROOT/'renders/v0.13.0'/name) == digest, name
    verification = json.loads((ROOT/'renders/v0.13.0/verification.json').read_text())
    for name, digest in verification['binaries'].items():
        assert sha(ROOT/'build-v013/Release'/name) == digest, name
    return dict(version='0.13.0', historical_workspace_audit_sha256=sha(path),
        unchanged_source_files=len(audit['source_code']),
        unchanged_deliverables=len(audit['deliverables']),
        unchanged_rendered_files=len(audit['rendered_artifacts']),
        unchanged_binaries=verification['binaries'],
        ctests='No C change; previous fifteen passing CTests preserved, not rerun.',
        device='No runtime/UI/device change; previous muted device evidence preserved, not rerun.')


def main():
    destination = OUT/'verification.json'
    if destination.exists():
        raise SystemExit('Preserve completed verification; create a new analysis version.')
    result = json.loads((OUT/'results.json').read_text())
    for name, digest in result['outputs'].items():
        assert sha(OUT/name) == digest, name
    for name, digest in result['tools'].items():
        assert sha(ROOT/name) == digest, name
    assert result['summary']['connected_runs'] == 24
    assert len(result['summary']['failed_runs']) == 12
    for run in result['runs'].values():
        rows = run['rows']
        if run['status'] == 'no_connected_path':
            assert rows == [] and run['metrics'] is None
            continue
        times = np.array([r['seconds'] for r in rows])
        freq = np.array([r['hz'] for r in rows])
        assert np.allclose(np.diff(times), .01, atol=1e-10)
        assert np.all(abs(np.diff(np.log2(freq))/np.diff(times)) <= run['settings']['max_octaves_per_second']+1e-9)
        assert min(r['prominence_db'] for r in rows) >= run['settings']['prominence_db']
    report = dict(status='pass', analysis='rev_descent_v1', dsp_version='0.13.0',
        anti_phase_control=phase_reversal_control(),
        selected_ridge_constraint_sensitivity=sensitivity(result),
        runtime=runtime_audit(), preserved_baselines=frozen_baselines(COUNTS),
        known_signal_controls='Nine successful L/R/power tracks with p95 < 3 cents; six negative/dropout tracks rejected; equivalent-waveform hidden-base counterexample preserved.',
        limits='Signal controls and hashes do not prove real-recording RPM, operating state, calibrated physics or subjective sound realism.',
        goal_status='active')
    paths = list(OUT.iterdir())+[Path(__file__), ROOT/'tools/analyze_rev_descent.py',
        ROOT/'tools/ridge_tracks.py', ROOT/'research/驻车补油落转观测V1.md',
        ROOT/'research/goal_progress_rev_descent_v1.json']
    report['files'] = {str(p.relative_to(ROOT)).replace('\\', '/'):sha(p) for p in sorted(paths) if p.is_file()}
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
