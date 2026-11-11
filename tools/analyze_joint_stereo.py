"""Reproducible stereo oscillator research on approved A/B and known controls.

All real fits reconstruct their OWN excerpt. Disjoint check excerpts test the
unchanged estimator on other recording content, not a learned driving model.
"""
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import signal
from osc_research.tracker import Settings, synthesize, independent
from osc_research.metrics import measure, compare
from sinusoidal_experiment import synthesize as legacy

OUT = ROOT/'references/analysis/joint_stereo_v1'
SR = 48000
CASES = [('A_idle_check', 'A', 208, 211, 'additional exterior-context check'),
         ('A_road_check', 'A', 316, 319.5, 'corrected rear exterior context'),
         ('A_revs_explore', 'A', 238, 242, 'exploratory stationary rear revs'),
         ('A_revs_check', 'A', 244, 248, 'disjoint stationary rear revs check'),
         ('B_pull_explore', 'B', 218, 222, 'exploratory binaural cabin'),
         ('B_pull_check', 'B', 226, 230, 'disjoint binaural cabin check')]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def controls():
    t = np.arange(2*SR)/SR
    static = np.zeros((len(t), 2))
    for index, (f, a, p, ratio, shift) in enumerate([
            (117.37, .2, .31, 1, np.pi),  # completely cancelled by mono folding
            (337.71, .1, -.73, .8, .6),
            (1241.26, .05, 1.51, .45, -1.7),
            (5301.83, .025, -.26, 1.2, 2.1),
            (10037.29, .012, .83, 0, 0)]):  # one-sided component
        phase = 2*np.pi*f*t + p
        static[:, 0] += a*np.cos(phase)
        static[:, 1] += a*ratio*np.cos(phase+shift)
    dynamic = np.zeros_like(static)
    for f, slope, a, am, shift, ratio in [
            (230, 17, .17, 2.1, .9, .8),
            (1500, 260, .06, 3.3, -1.4, 1.1),
            (6500, -550, .025, 4.1, 2.2, .65)]:
        phase = 2*np.pi*(f*t+.5*slope*t*t)
        amplitude = a*(.7+.3*np.cos(2*np.pi*am*t))
        dynamic[:, 0] += amplitude*np.cos(phase)
        dynamic[:, 1] += amplitude*ratio*np.cos(phase+shift)
    reports = {}
    for name, x in [('sparse_stereo', static), ('known_stereo_am_fm', dynamic)]:
        target = measure(x, SR)
        methods = {}
        for label, setting in [('joint_4096', Settings()), ('joint_2048', Settings(window=2048))]:
            y, stats = synthesize(x, SR, 64, setting)
            metrics = measure(y, SR, x)
            methods[label] = dict(settings=asdict(setting), metrics=metrics,
                                  band_errors=compare(target, metrics), tracking=stats)
            if name == 'sparse_stereo':
                assert metrics['relative_waveform_residual_db'] < -45, (label, metrics)
                assert abs(metrics['side_to_mid_db']-target['side_to_mid_db']) < .1
                assert abs(metrics['bands'][0]['side_to_mid_db']-target['bands'][0]['side_to_mid_db']) < .2
            else:
                assert metrics['relative_waveform_residual_db'] < -12, (label, metrics)
                assert abs(metrics['side_to_mid_db']-target['side_to_mid_db']) < .5
        reports[name] = dict(reference=target, methods=methods)
    return reports


def save_auditions(name, outputs):
    valid = slice(round(.2*SR), -round(.2*SR))
    target_rms = 10**(-23/20)
    gains = {key: target_rms/max(float(np.sqrt(np.mean(x[valid]**2))), 1e-20)
             for key, x in outputs.items()}
    common = min(1, .85/max(float(np.max(abs(x)))*gains[key] for key, x in outputs.items()))
    paths = {}
    for key, x in outputs.items():
        y = x*gains[key]*common
        fade = np.linspace(0, 1, 240)
        y[:240] *= fade[:, None]
        y[-240:] *= fade[::-1, None]
        file = OUT/f'{name}_{key}_rms_matched.wav'
        sf.write(file, y, SR, subtype='PCM_24')
        paths[key] = dict(file=str(file.relative_to(ROOT)), sha256=digest(file),
                          rms_gain=gains[key], shared_headroom_gain=common)
    return paths


def plot_case(name, outputs):
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    for key, x in outputs.items():
        f, p = signal.welch(x[9600:-9600], SR, nperseg=4096, axis=0, detrend=False)
        _, ms = signal.welch(np.column_stack(((x[:, 0]+x[:, 1])*.5,
                                              (x[:, 0]-x[:, 1])*.5))[9600:-9600],
                            SR, nperseg=4096, axis=0, detrend=False)
        ax[0].semilogx(f, 10*np.log10(p.mean(axis=1)+1e-30), label=key, alpha=.8)
        # Band S/M values are less sensitive to empty single-bin divisions.
        m = measure(x, SR)
        ax[1].semilogx([np.sqrt(b['hz'][0]*b['hz'][1]) for b in m['bands']],
                      [b['side_to_mid_db'] for b in m['bands']], 'o-', label=key)
    ax[0].set(ylabel='Stereo mean PSD dB/Hz', title=f'{name}: same-excerpt diagnostic / original gains')
    ax[1].set(xlabel='Hz', ylabel='Band side/mid dB', ylim=(-85, 20))
    for a in ax:
        a.set_xlim(80, 14000)
        a.grid(alpha=.2)
    ax[0].legend(ncol=2, fontsize=8)
    fig.savefig(OUT/f'{name}.png', dpi=150)
    plt.close(fig)


def real_case(name, source, start, end, role):
    master = ROOT/f'references/clean/{source}_decoded_float.wav'
    with sf.SoundFile(master) as f:
        assert f.samplerate == SR and f.channels == 2 and f.subtype == 'FLOAT'
        f.seek(round(start*SR))
        x = f.read(round((end-start)*SR), always_2d=True)
    outputs = {'reference': x}
    methods = {}
    jobs = [
        ('legacy_independent64', lambda: (np.column_stack([legacy(x[:, c], SR, 64) for c in range(2)]),
                                          dict(channel_oscillator_budget=128))),
        ('independent64', lambda: independent(x, SR, 64, Settings())),
        ('joint64', lambda: synthesize(x, SR, 64, Settings())),
        ('joint64_short', lambda: synthesize(x, SR, 64, Settings(window=2048)))
    ]
    target = measure(x, SR)
    for key, job in jobs:
        before = time.perf_counter()
        y, stats = job()
        assert np.isfinite(y).all()
        outputs[key] = y
        metrics = measure(y, SR, x)
        methods[key] = dict(metrics=metrics, band_errors=compare(target, metrics),
                            tracking=stats, elapsed_seconds=time.perf_counter()-before)
    paths = save_auditions(name, outputs)
    plot_case(name, outputs)
    return dict(source=source, source_seconds=[start, end], role=role,
        master=str(master.relative_to(ROOT)), reference=target, methods=methods,
        auditions=paths, plot=f'{name}.png')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--controls-only', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(schema='vsl.joint-stereo-diagnostic/1', controls=controls())
    (OUT/'controls.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for name, case in report['controls'].items():
        print(name, {key: round(m['metrics']['relative_waveform_residual_db'], 2)
                     for key, m in case['methods'].items()}, flush=True)
    if args.controls_only:
        return
    ledger = json.loads((ROOT/'references/approval_manifest.json').read_text(encoding='utf-8'))
    assert all(next(a for a in ledger if a['id'] == source)['approved'] for source in ['A', 'B'])
    report.update(settings_primary=asdict(Settings()),
        settings_ablation=asdict(Settings(window=2048)),
        oscillator_budget='Each method permits 128 channel oscillator outputs. Joint64 shares 64 frequencies with independent L/R amplitude and phase; independent64 permits 64 frequencies per channel. These are trajectories, not engine orders.',
        processing='Raw decoded float stereo slices, no denoise/HP/normalization before metrics. 0.2s edges excluded. Audition derivatives use explicitly recorded stereo RMS gains and one common peak headroom gain per case, 5ms fades, PCM24. Not LUFS.',
        method='Zero-padded centred Hann transform; sum of L/R powers for peak selection; off-bin complex interpolation; Hungarian frequency matching; cubic phase interpolation; no stochastic component, samples or residual waveform playback.',
        limits=[
            'Every reconstruction is fitted to the same excerpt that it reconstructs. No learned RPM/load/state generator or held-out timbre synthesis is evaluated.',
            'Disjoint check excerpts receive the fixed estimator/settings; they only check recording-domain estimator behaviour.',
            'Waveform residual includes AM/FM estimation, tracking, transients, interference, out-of-band content and noise. It is not noise fraction or realism.',
            'Long/short windows trade frequency separation for transient resolution. Sharing a frequency does not force identical channel phases.',
            'Shared sinusoidal support cannot create the diffuse field, binaural room response or physical speaker validation.',
            'A and B are separate perspectives and cars. Do not fit exterior width to B cabin.',
            'No runtime DSP, frozen baseline or source master is changed by this tool.'],
        sources={s: dict(master=f'references/clean/{s}_decoded_float.wav',
                         sha256=digest(ROOT/f'references/clean/{s}_decoded_float.wav')) for s in ['A', 'B']},
        tools={str(p.relative_to(ROOT)): digest(p) for p in [Path(__file__),
            ROOT/'tools/osc_research/tracker.py', ROOT/'tools/osc_research/metrics.py',
            ROOT/'tools/sinusoidal_experiment.py']}, cases={})
    for case in CASES:
        name = case[0]
        report['cases'][name] = real_case(*case)
        print(name, {key: round(m['metrics']['relative_waveform_residual_db'], 2)
                     for key, m in report['cases'][name]['methods'].items()}, flush=True)
        (OUT/'results.partial.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    report['plots'] = {p.name: digest(p) for p in OUT.glob('*.png')}
    (OUT/'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
