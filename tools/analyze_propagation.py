"""Measure the compiled C path impulses, not a Python replacement renderer."""
import json
import subprocess
from runtime_review import ROOT, sha
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT/'renders/v0.14.0'
PROBE = ROOT/'build-v014/Release/vsl_spatial_probe.exe'


def run_probe(name, rate, fraction=None):
    prefix = OUT/'propagation'/name
    command = [str(PROBE), str(prefix), str(rate)]
    if fraction is not None:
        command.append(str(fraction))
    subprocess.run(command, check=True, capture_output=True, timeout=10)
    meta = json.loads(prefix.with_suffix('.json').read_text())
    x = np.loadtxt(prefix.with_suffix('.csv'), delimiter=',', skiprows=1)[:, 1:]
    assert np.isfinite(x).all() and meta['clamped_paths'] == 0
    assert meta['dsp'] == '0.14.0' and meta['algorithmic_latency_samples'] == 13
    sums = x.sum(axis=0)
    assert np.max(abs(sums-np.array(meta['gain']))) < 1e-10
    moment = (np.arange(len(x))[:, None]*x).sum(axis=0)/sums
    assert abs(moment[0]-meta['delay_samples'][0]) < 1e-8
    assert abs(moment[2]-meta['delay_samples'][2]) < 1e-8
    fft = np.fft.rfft(x, n=131072, axis=0)
    hz = np.fft.rfftfreq(131072, 1/rate)
    selected = (hz >= 28) & (hz <= min(20000, rate*5/12))
    ideal = meta['gain'][2]*np.exp(-2j*np.pi*hz*meta['delay_samples'][2]/rate)
    relative = fft[:, 2]/ideal
    db = 20*np.log10(np.maximum(abs(relative), 1e-20))
    phase = np.angle(relative, deg=True)
    report = dict(command=command, metadata=meta,
        impulse_dc_gain=sums.tolist(), signed_impulse_moment_samples=moment.tolist(),
        centre_filter_band_hz=[28, min(20000, rate*5/12)],
        centre_filter_max_abs_magnitude_error_db=float(np.max(abs(db[selected]))),
        centre_filter_max_abs_phase_error_deg=float(np.max(abs(phase[selected]))),
        files={p.name:sha(p) for p in [prefix.with_suffix('.csv'), prefix.with_suffix('.json')]})
    # Finite fractional interpolation need not be transparent near Nyquist.
    assert report['centre_filter_max_abs_magnitude_error_db'] < .3, report
    assert report['centre_filter_max_abs_phase_error_deg'] < 1, report
    if fraction is None:
        source = np.array(meta['source']); listener = np.array(meta['listener'])
        ears = [listener+np.array([0, meta['ear_spacing_m']/2, 0]),
                listener-np.array([0, meta['ear_spacing_m']/2, 0]), listener]
        expected = np.array([np.linalg.norm(source-ear)/meta['speed_mps']*rate+13 for ear in ears])
        assert np.max(abs(expected-np.array(meta['delay_samples']))) < 1e-9
        report['interaural_geometric_delay_us'] = (meta['delay_samples'][1]-meta['delay_samples'][0])/rate*1e6
    return report, (hz[selected], db[selected], phase[selected])


def main():
    destination = OUT/'propagation_probe.json'
    if destination.exists():
        raise SystemExit('Preserve final probe results; use a new version.')
    (OUT/'propagation').mkdir(parents=True, exist_ok=True)
    rates = {}
    for rate in [16000, 48000, 192000]:
        rates[str(rate)], _ = run_probe(f'geometry_{rate}', rate)
    fractional = {}
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, constrained_layout=True)
    for i, fraction in enumerate(np.linspace(0, 1, 17)):
        item, (hz, db, phase) = run_probe(f'fraction_{i:02d}', 48000, float(fraction))
        fractional[str(fraction)] = item
        axes[0].plot(hz, db, lw=.7, alpha=.6)
        axes[1].plot(hz, phase, lw=.7, alpha=.6)
    axes[0].set(ylabel='Magnitude error (dB)', title='Compiled C centre-path probe: 17 fractional phases at 48 kHz\n25-tap Blackman sinc, 256-phase table; relative to ideal fractional delay')
    axes[1].set(xlabel='Frequency (Hz)', ylabel='Phase error (degrees)')
    for axis in axes:
        axis.grid(alpha=.2);axis.set_xlim(28, 20000)
    fig.savefig(OUT/'fractional_path_response.png', dpi=150);plt.close(fig)
    result = dict(status='pass', compiled_probe_sha256=sha(PROBE), rate_controls=rates,
        fractional_controls=fractional, common_algorithmic_latency_samples=13,
        scope='Actual compiled C impulses before scene highpass/width/room. Signed moments are for near ear and centre; far-ear head shadow adds frequency-dependent phase. No measured HRTF/vehicle transfer or listening validation.',
        boundaries='Bounds only over 28 Hz..min(20 kHz, 5/12 sample rate) and tested phases/positions. No near-Nyquist transparency or arbitrary moving-delay aliasing proof.',
        tools={str(p.relative_to(ROOT)).replace('\\', '/'):sha(p) for p in [ROOT/'tools/analyze_propagation.py', ROOT/'src/cli/spatial_probe.c']})
    destination.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='pass', geometry_itd_us=rates['48000']['interaural_geometric_delay_us'],
        worst_magnitude_db=max(x['centre_filter_max_abs_magnitude_error_db'] for x in fractional.values()),
        worst_phase_degrees=max(x['centre_filter_max_abs_phase_error_deg'] for x in fractional.values())), indent=2))


if __name__ == '__main__':
    main()
