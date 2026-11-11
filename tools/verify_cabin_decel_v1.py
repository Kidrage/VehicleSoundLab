"""Check slow-sweep fixtures and identify the boundary of local deceleration fits."""
import argparse
import csv
import json
from pathlib import Path
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
from drive_evidence_v1.sources import sha
from shift_evidence_v1.spectrum import observe
from state_colour_v2.clock import follow
from state_dna_v1.compare import describe
from phase_clock_v1.projection import polish as short_polish
from exterior_clock_v1.warp import polish as long_polish

args.out.mkdir(parents=True, exist_ok=False)
root = args.workspace/'references/analysis/cabin_decel_v1'
reports = {name: json.loads((root/name/'report.json').read_text(encoding='utf-8'))
           for name in ('exploration1', 'exploration2_four')}
for name, report in reports.items():
    for source, digest in report['source_sha256'].items():
        assert sha(root/name/'exact_sources'/source) == digest, source
assert reports['exploration1']['plan_sha256'] == reports['exploration2_four']['plan_sha256']

def bands(power):
    hz = np.arange(1, 289)*46.875
    return np.array([power[(hz >= lo) & (hz < hi)].sum(axis=0)
                     for lo, hi in ((400, 1200), (1200, 3000), (3000, 8000))])

def shape(expected, actual):
    delta = 10*np.log10(np.maximum(bands(actual), 1e-30)/np.maximum(bands(expected), 1e-30))
    return delta[1:] - delta[0]

methods = {'two': short_polish, 'four': long_polish}
rate = 48000
times = np.arange(round(1.2*rate))/rate
orders = np.arange(1, 289)
amplitude = .065*np.exp(-orders/90)/np.sqrt(orders)
phase = orders*.17
channel_phase = .02*orders+.1*np.sin(orders)
expected = np.column_stack((amplitude**2, .8**2*amplitude**2))
fixtures = []
missing = []
for real_case in reports['exploration1']['cases']:
    p = real_case['references']['5']['tracking']['rows']
    pt = np.array([r['seconds'] for r in p])
    pr = np.array([r['root_hz'] for r in p])
    # The known true schedule copies a measured slow curve. Measurement error
    # in that real curve is irrelevant to the identity of this synthetic truth.
    roots = np.interp(times, pt-pt[0]+.2, pr)
    cycles = np.r_[0, np.cumsum((roots[1:]+roots[:-1])/(2*rate))]
    gain = .7+.15*np.sin(2*np.pi*.8*times)
    for transfer in (False, True):
        audio = np.zeros((len(times), 2))
        no_reference = np.zeros_like(audio)
        for h, a, ph, side in zip(orders, amplitude, phase, channel_phase):
            # Phase-only, pitch-dependent transfer. This is an explicit known
            # coefficient model, not a measured cabin or a causal acoustic FRF.
            extra = .9*np.arctan2((h*roots)**2-160**2, 2*.12*160*h*roots) if transfer else 0
            angle = 2*np.pi*h*cycles+ph+extra
            term = gain[:, None]*a*np.column_stack((np.cos(angle), .8*np.cos(angle+side)))
            audio += term
            if h != 5:
                no_reference += term
        observation = observe(audio, 0, 80)
        track = follow(observation['hz'], observation['seconds'], observation['power_low'],
                       .2, .995, float(np.interp(.2, times, roots)), 5)
        for method, refine in methods.items():
            item = dict(case=real_case['case']['id'], method=method, phase_only_transfer=transfer,
                        tracking_status=track['status'])
            if not track['rows']:
                item['status'] = 'missing_coarse_path'
                fixtures.append(item)
                continue
            at = np.array([r['seconds'] for r in track['rows']])
            hz = np.array([r['root_hz'] for r in track['rows']])
            try:
                _, _, evidence, z = describe(audio, 0, at, hz, float(at[0]), float(at[-1]),
                                             phase_refiner=refine)
            except ValueError as exc:
                item.update(status='phase_rejected', reason=str(exc))
                fixtures.append(item)
                continue
            power = np.mean(abs(z)**2, axis=0)
            error = shape(expected, power)
            wt = np.array(evidence['window_source_seconds'])
            estimated = np.array(evidence['window_root_hz'])
            true = np.interp(wt, times, roots)
            item.update(status='measured', shape_error_db_LR=error.tolist(),
                        max_shape_error_db=float(abs(error).max()),
                        root_relative_p95=float(np.percentile(abs(estimated-true)/true, 95)),
                        source_span=evidence['correction']['source_seconds'])
            fixtures.append(item)
        if not transfer:
            observation = observe(no_reference, 0, 80)
            track = follow(observation['hz'], observation['seconds'], observation['power_low'],
                           .2, .995, float(np.interp(.2, times, roots)), 5)
            missing.append(dict(case=real_case['case']['id'], rejected=not bool(track['rows']), status=track['status']))

fig, axes = plt.subplots(3, 2, figsize=(11, 9), constrained_layout=True)
common_interval_checks = []
for i, case in enumerate(reports['exploration1']['cases']):
    for name, style in (('exploration1', '--'), ('exploration2_four', '-')):
        observed = reports[name]['cases'][i]
        for ref, item in observed['references'].items():
            if item['status'] != 'measured':
                continue
            evidence = item['evidence']
            axes[i, 0].plot(evidence['window_source_seconds'], evidence['window_root_hz'],
                            linestyle=style, label=f'{name} / ref{ref}', lw=.8)
        primary = observed['references']['5']['evidence']
        zp = np.load(root/name/case['case']['id']/'reference5_coordinates.npz')['complex_rows']
        tp = np.array(primary['window_source_seconds'])
        for ref in ('3', '7'):
            other = observed['references'][ref]
            if other['status'] != 'measured':
                continue
            to = np.array(other['evidence']['window_source_seconds'])
            zo = np.load(root/name/case['case']['id']/f'reference{ref}_coordinates.npz')['complex_rows']
            lo, hi = max(tp[0], to[0]), min(tp[-1], to[-1])
            grid = np.arange(lo, hi, .005)
            # Interpolate power, never complex phase, at the same physical
            # source centers. Four-cycle window supports still differ slightly.
            def power(z, t):
                flat = (abs(z)**2).reshape(len(z), -1)
                return np.array([np.interp(grid, t, col).mean() for col in flat.T]).reshape(288, 2)
            error = shape(power(zp, tp), power(zo, to))
            common_interval_checks.append(dict(case=case['case']['id'], method=name, reference=int(ref),
                common_seconds=[float(lo), float(hi)], shape_relative_400_1200_db_LR=error.tolist(),
                maximum_shape_db=float(abs(error).max())))
            axes[i, 1].plot([1.2, 3.0], error.mean(axis=1), linestyle=style, marker='o',
                            label=f'{name} / ref{ref}')
    axes[i, 0].set(title=case['case']['id'], xlabel='Original source seconds', ylabel='Acoustic root Hz')
    axes[i, 0].legend(fontsize=6)
    axes[i, 1].set(xlabel='Band starts kHz; common source centers', ylabel='Other vs ref5 shape dB')
    axes[i, 1].axhline(0, color='grey', lw=.7)
    axes[i, 1].legend(fontsize=6)
fig.savefig(args.out/'clock_and_colour.png', dpi=140)
plt.close(fig)

with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='') as stream:
    index = list(csv.DictReader(stream))
assert len(index) == 421
for row in index:
    assert sha(repo/row['文件']) == row['SHA-256'], row['文件']
result = dict(schema='vsl.cabin-deceleration-verification/1',
    local_candidate_qualification='not_passed', runtime_changes=False, human_accepted=False,
    fixtures=fixtures, missing_reference=missing, common_interval_checks=common_interval_checks,
    c_index_rows=len(index), c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
    input_sha256={name: sha(root/name/'report.json') for name in reports},
    limits=['Known phase-only transfer does not measure the real microphone transfer',
            'Observed carrier inconsistency alone does not identify a software bug or an engine state',
            'Common centers do not make slightly different physical window lengths identical',
            'No model exported, no state profile promoted, no runtime source modified'])
paths = [Path(__file__), repo/'tools/state_dna_v1/compare.py', repo/'tools/state_colour_v2/clock.py',
         repo/'tools/shift_evidence_v1/spectrum.py', repo/'tools/phase_clock_v1/projection.py',
         repo/'tools/exterior_clock_v1/warp.py', repo/'tools/sound_dna/windowed.py']
result['source_sha256'] = {p.relative_to(repo).as_posix(): sha(p) for p in paths}
for p in paths:
    target = args.out/'exact_sources'/p.relative_to(repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, target)
(args.out/'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',
                                        encoding='utf-8', newline='\n')
print(json.dumps(dict(fixture_errors=[(r['case'], r['method'], r['phase_only_transfer'],
                                      r.get('max_shape_error_db'), r.get('root_relative_p95')) for r in fixtures],
                      missing_reference_rejected=[r['rejected'] for r in missing],
                      common_interval_maxima=[r['maximum_shape_db'] for r in common_interval_checks]), ensure_ascii=False))
