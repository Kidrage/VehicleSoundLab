"""Quantify native control hold and a causal one-period C gain ramp."""
import csv
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from runtime_review import ROOT, sha, rms
from review_pairs import common_pair
import numpy as np
import soundfile as sf
from scipy.signal import lfilter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT/'renders/gain_bridge_v1'
PROBE = ROOT/'build-experiment-gain-bridge/Release/gain_bridge_probe.exe'
CASES = {'high': ('8000 RPM · 既有细节各 65%', 'high_combined'),
    'neutral': ('空挡补油与落转', 'neutral_base'), 'lift': ('收油、断油与恢复', 'lift_base'),
    'drive': ('30 秒运动自动挡 · 既有细节各 65%', 'drive_combined')}
METHODS = {'hold':'原有 200 Hz 保持', 'ramp':'逐样本因果线性过渡'}


def audio(path):
    x, sr = sf.read(path, always_2d=True)
    assert sr == 48000 and sf.info(path).subtype == 'FLOAT' and np.isfinite(x).all()
    return x


def main():
    if OUT.exists() and ('--repair-incomplete' not in sys.argv or (OUT/'results.json').exists() or (ROOT/'baselines/gain_bridge_v1').exists()):
        raise SystemExit('Preserve gain_bridge_v1; output folder already exists.')
    OUT.mkdir(exist_ok=True)
    native = json.loads((ROOT/'renders/v0.16.0/verification.json').read_text())
    inputs, commands = {}, {}
    for label, take in CASES.values():
        for ext in ['vsltake','wav','csv']:
            path = ROOT/f'renders/v0.16.0/{take}.{ext}'
            assert sha(path) == native['files'][path.name]
            inputs[path.relative_to(ROOT).as_posix()] = sha(path)

    def render(case, method, channels=2):
        name = case+'_'+method+('_714' if channels == 12 else '')
        args = [str(PROBE), str(ROOT/f'renders/v0.16.0/{CASES[case][1]}.vsltake'), str(OUT/name), str(int(method=='ramp')), str(channels)]
        run = subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True, timeout=180)
        assert '| pass' in run.stdout
        print('rendered '+name, flush=True)
        return name, dict(command=args, stdout=run.stdout)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(render, case, method) for case in CASES for method in METHODS]
        jobs.append(pool.submit(render, 'high','ramp',12))
        for job in as_completed(jobs):
            name, row = job.result();commands[name] = row
    args = [str(PROBE), 'carrier', str(OUT/'control')]
    run = subprocess.run(args, check=True, capture_output=True, text=True, timeout=30)
    assert '| pass' in run.stdout;commands['carrier'] = dict(command=args, stdout=run.stdout)
    carrier = audio(OUT/'control_carrier.wav');n = len(carrier)
    transform = np.fft.rfft(carrier,axis=0)*2/n
    hz = np.fft.rfftfreq(n,1/48000)
    carrier_rows = []
    for offset in [7, 193, 207, 393, 407]:
        frequency = 2048+offset;bin_index = round(frequency*n/48000)
        measured = float(abs(transform[bin_index,1])/abs(transform[bin_index,0]))
        expected = abs(np.sin(np.pi*offset*240/48000)/(240*np.sin(np.pi*offset/48000)))
        assert abs(measured-expected) < 2e-6, (offset, measured, expected)
        carrier_rows.append(dict(offset_hz=offset, carrier_sideband_hz=frequency,
            measured_ramp_over_hold_db=float(20*np.log10(measured)),
            expected_boxcar_ratio_db=float(20*np.log10(expected))))

    results, pages = {}, {}
    for case, (label, take) in CASES.items():
        assert sha(OUT/f'{case}_hold.wav') == sha(ROOT/f'renders/v0.16.0/{take}.wav')
        assert sha(OUT/f'{case}_hold.csv') == sha(ROOT/f'renders/v0.16.0/{take}.csv')
        traces = {method:list(csv.DictReader((OUT/f'{case}_{method}.csv').open(newline=''))) for method in METHODS}
        changed = [key for key in traces['hold'][0] if any(a[key]!=b[key] for a,b in zip(traces['hold'],traces['ramp']))]
        assert len(traces['hold']) == len(traces['ramp'])
        assert set(changed) <= {'mechanical_stored_energy','character_pressure_l','character_pressure_r','character_structure'}, changed
        meta = {method:json.loads((OUT/f'{case}_{method}_bridge.json').read_text()) for method in METHODS}
        assert meta['hold']['gains'] == meta['ramp']['gains']
        assert meta['ramp']['enabled'] and not meta['hold']['enabled']
        gains = {}
        for row in meta['hold']['gains']:
            name = row['name'];path = OUT/f'{case}_hold_gain_{name}.wav'
            assert sha(path) == sha(OUT/f'{case}_ramp_gain_{name}.wav')
            pairs = audio(path)
            independent = lfilter(np.ones(240)/240, [1.], pairs[:,0])
            error = float(abs(independent-pairs[:,1]).max());assert error < 1.5e-7
            assert row['maximum_ramp_step'] <= row['maximum_held_step']/240+1e-14
            gains[name] = dict(**row, independent_boxcar_max_error=error,
                measured_float32_max_held_step=float(abs(np.diff(pairs[:,0],prepend=0)).max()),
                measured_float32_max_ramp_step=float(abs(np.diff(pairs[:,1],prepend=0)).max()))
        # Independent previously exported native source fixtures.
        prior_prefix = (ROOT/f'renders/source_audition_v1/{take}') if case != 'lift' else ROOT/'renders/exhaust_phase_v1/lift_base'
        unchanged = []
        for obj in json.loads((OUT/f'{case}_hold_scene.json').read_text())['objects']:
            name = obj['name'];prior = Path(str(prior_prefix)+'_source_'+name+'.wav')
            assert sha(prior) == sha(OUT/f'{case}_hold_source_{name}.wav')
            inputs[prior.relative_to(ROOT).as_posix()] = sha(prior)
            if sha(OUT/f'{case}_hold_source_{name}.wav') == sha(OUT/f'{case}_ramp_source_{name}.wav'):
                unchanged.append(name)
        assert {'events','road','wind'} <= set(unchanged)
        arrays = [audio(OUT/f'{case}_{method}.wav') for method in METHODS]
        assert all(abs(x).max() < .95 for x in arrays)
        audition = common_pair(OUT, arrays, list(METHODS), case)
        difference = arrays[1]-arrays[0]
        results[case] = dict(take=take, changed_trace_fields=changed, control_checks=gains,
            unchanged_sources=unchanged, rms_dbfs={m:rms(x) for m,x in zip(METHODS,arrays)},
            difference_rms_dbfs=rms(difference),difference_peak=float(abs(difference).max()),audition=audition,
            difference_note='Complete deterministic render difference, not isolated click/noise energy or a perceptual score.')
        pages[case] = dict(label=label,takes={method:'../renders/gain_bridge_v1/'+audition[method]['file'] for method in METHODS},
            gain_db=audition['hold']['gain_db'])
    bed = json.loads((OUT/'high_ramp_714_scene.json').read_text())
    for obj in bed['objects']:
        name = obj['name'];assert sha(OUT/f'high_ramp_714_source_{name}.wav') == sha(OUT/f'high_ramp_source_{name}.wav')
    assert sha(OUT/'high_ramp_714.csv') == sha(OUT/'high_ramp.csv')
    assert bed['channels'] == ['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for row in json.loads((OUT/'high_ramp_714_bridge.json').read_text())['gains']:
        name = row['name'];assert sha(OUT/f'high_ramp_714_gain_{name}.wav') == sha(OUT/f'high_ramp_gain_{name}.wav')
    # Visualise a deterministic control interval, not a physical reference event.
    pairs = audio(OUT/'lift_hold_gain_exhaust.wav');step = abs(np.diff(pairs[:,0],prepend=0));at = int(np.argmax(step))
    window = slice(max(0,at-720),min(len(pairs),at+1440));time=(np.arange(len(pairs))[window]-at)/48
    fig,axes = plt.subplots(1,2,figsize=(10,3.8),constrained_layout=True)
    axes[0].plot(time,pairs[window,0],label='native control hold');axes[0].plot(time,pairs[window,1],label='causal gain ramp')
    axes[0].set(xlabel='ms relative to largest gain step',ylabel='exhaust gain',title='Frozen lift take / exact C control taps');axes[0].legend(fontsize=8)
    mask=(hz>=2200)&(hz<=2300)
    for c, label in enumerate(['hold','ramp']):axes[1].plot(hz[mask],20*np.log10(np.maximum(abs(transform[mask,c]),1e-12)),label=label)
    axes[1].set(xlabel='Hz',ylabel='diagnostic amplitude / dBFS',ylim=(-125,-30),title='2048 Hz carrier / 7 Hz gain modulation / first images');axes[1].legend()
    for ax in axes:ax.grid(alpha=.2)
    fig.savefig(OUT/'gain_bridge.png',dpi=160);plt.close(fig)
    shutil.copy2(ROOT/'build-experiment-gain-bridge/Testing/Temporary/LastTest.log',OUT/'ctest_original.log')
    sources = [*sorted((ROOT/'experiments/gain_bridge_v1').glob('*')), ROOT/'tools/render_gain_bridge.py',
        ROOT/'build-experiment-gain-bridge/bridge_engine.c',ROOT/'build-experiment-gain-bridge/bridge_take.c']
    binaries = [PROBE,ROOT/'build-experiment-gain-bridge/Release/gain_bridge_checks.exe',
        ROOT/'build-experiment-gain-bridge/Release/gain_bridge.lib',ROOT/'build-v016/Release/vsl_core.lib']
    result = dict(schema='vsl.gain-bridge-study/1',runtime='0.16.0 unchanged',period_samples=240,
        gain_only_boxcar_group_delay_samples=119.5,gain_only_boxcar_group_delay_ms=119.5/48,
        cases=results,page_data=pages,methods=METHODS,diagnostic_carrier=carrier_rows,commands=commands,inputs=inputs,
        layout12_source_gain_and_trace_identity=True,
        sources={p.relative_to(ROOT).as_posix():sha(p) for p in sources if p.is_file()},
        binaries={p.relative_to(ROOT).as_posix():sha(p) for p in binaries},
        retained_initial_overlap={p.relative_to(OUT).as_posix():sha(p) for p in sorted((OUT/'initial_carrier_overlap').iterdir()) if p.is_file()},
        files={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        scope='Seven continuous voice gains only; state maps/targets, driving, clocks and RNG schedules retained. Other control steps remain. Diagnostic image attenuation is not a measured engine-noise fraction or a realism improvement.')
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(result='pass',normal_auditions=8,carrier_checks=carrier_rows,
        maximum_independent_gain_error=max(c['independent_boxcar_max_error'] for row in results.values() for c in row['control_checks'].values())),indent=2))


if __name__ == '__main__':
    main()
