"""Measure A stationary rising/falling colour without changing runtime voices."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--clocks', type=Path, required=True)
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read, sha
from sound_dna.windowed import estimate
from sound_dna.profile import export
from state_dna_v1.compare import describe, match, difference

repository = Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True, exist_ok=False)
audio, provenance = read(args.workspace, 'A_exterior_blips', 'exterior_dynamic_observation')
exploration = json.loads((args.clocks/'report.json').read_text(encoding='utf-8'))
observation = args.workspace/'references/analysis/drive_evidence_v1/observed/A_exterior_blips/audio.npz'
assert sha(observation) == exploration['observation_sha256']
report = dict(schema='vsl.state-dna-colour/1', source=provenance,
    clocks_sha256=sha(args.clocks/'report.json'), cases={}, comparisons=[], human_accepted=False,
    probe_sha256=sha(args.probe), runtime_changed=False,
    limits=['Observed rising/falling sound, not measured throttle/load/fuel state',
        'One short rising passage; Hann windows overlap and are not independent repeats',
        'Four-cycle windows and source FIR smooth short transients;8..14k comparisons may be filter-limited',
        'No claim that stationary rev spectra transfer to loaded driving or another microphone context'])
cases = [('fall1', 238.35, 238.95), ('rise2', 240.60, 240.85), ('fall2', 240.94, 241.66)]
bins = [(35, 40), (40, 45), (45, 50)]
for name, start, stop in cases:
    out = args.out/name
    out.mkdir()
    paths = exploration['cases'][name]
    rows5, rows10 = paths['5']['rows'], paths['10']['rows']
    times = np.array([r['seconds'] for r in rows5])
    roots = np.array([r['root_hz'] for r in rows5])
    selected = (times >= start) & (times <= stop)
    other = np.interp(times[selected], [r['seconds'] for r in rows10], [r['root_hz'] for r in rows10])
    y, where, evidence, values = describe(audio, provenance['seconds'][0], times, roots, start, stop)
    evidence['reference5_vs10_relative_error'] = (abs(roots[selected]-other)/roots[selected]).tolist()
    evidence['matched_bins'] = match(values, np.array(evidence['window_root_hz']), bins)
    evidence['direction'] = 'rising' if name.startswith('rise') else 'falling'
    evidence['training_claim'] = 'Diagnostic short-passage model; insufficient independent repeats for production state atlas'
    np.savez_compressed(out/'coordinates.npz', source_seconds=where, complex_rows=values)
    sf.write(out/'normalized_float.wav', y, 48000, subtype='FLOAT')
    model, stats = estimate(y, 288, min(12, len(values)-1))
    export(out/'voice.model', model, 46.875)
    evidence['statistics'] = stats
    evidence['model_sha256'] = sha(out/'voice.model')
    raw = out/'c_sustained_float.wav'
    command = [str(args.probe), str(out/'voice.model'), str(raw), '8', '1', '1', '1']
    run = subprocess.run(command, check=True, capture_output=True, timeout=90)
    evidence['render'] = dict(command=command, stdout=run.stdout.decode('utf-8', errors='replace'), sha256=sha(raw))
    report['cases'][name] = evidence
    print(name, 'cycles', round(evidence['normalized_cycles'], 2), 'windows', len(values),
          'clock disagreement max', round(max(evidence['reference5_vs10_relative_error']), 4), flush=True)

for before, after in [('fall1', 'rise2'), ('fall2', 'rise2'), ('fall1', 'fall2')]:
    record = dict(before=before, after=after,
        whole_window=difference(report['cases'][before]['harmonic_mean_power_LR'],
                                report['cases'][after]['harmonic_mean_power_LR']), bins=[])
    for a, b in zip(report['cases'][before]['matched_bins'], report['cases'][after]['matched_bins']):
        record['bins'].append(dict(root_bin_hz=a['root_bin_hz'], windows=[a['windows'], b['windows']],
            difference=difference(a['mean_power_LR'], b['mean_power_LR']) if a['windows'] and b['windows'] else None))
    report['comparisons'].append(record)

fig, axes = plt.subplots(2, 1, figsize=(11, 7), layout='constrained')
for name, evidence in report['cases'].items():
    power = np.asarray(evidence['harmonic_mean_power_LR']).mean(axis=1)
    hz = np.arange(1, len(power)+1)*46.875
    axes[0].semilogx(hz, 10*np.log10(power+1e-30), label=name, alpha=.75, lw=1)
    axes[1].semilogx(hz, 10*np.log10((power+1e-30)/(power.sum()+1e-30)), label=name, alpha=.75, lw=1)
axes[0].set(title='A stationary rear: same acoustic pitch, original relative levels', ylabel='Harmonic power dBFS')
axes[1].set(title='Scalar gain removed for shape diagnostic only', ylabel='Relative harmonic power dB', xlabel='Hz at acoustic root46.875')
for axis in axes:
    axis.set_xlim(46, 14000)
    axis.grid(alpha=.2)
    axis.legend()
fig.savefig(args.out/'spectra.png', dpi=140)
plt.close(fig)
report['source_sha256'] = {p.relative_to(repository).as_posix():sha(p) for p in
    [Path(__file__), repository/'tools/explore_state_dna_v1.py',
     *repository.joinpath('tools/state_dna_v1').glob('*.py'),
     *repository.joinpath('tools/exterior_clock_v1').glob('*.py'),
     *repository.joinpath('tools/sound_dna').glob('*.py')]}
(args.out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
