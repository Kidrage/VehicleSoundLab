"""Plot the fixed dense comparison; objective curves stay in their own metrics."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/python_deps')]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha
from observed_topology_v1.fixtures import make


def load(path): return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.complex-radial-review/1', result='running', sources={},
    real_audio_read=False, model_exported=False, runtime_changed=False)
try:
    root = args.workspace/'references/analysis/complex_radial_v1'
    parent = args.workspace/'references/analysis/correlated_observation_v1/fit1'
    audit = load(root/'audit1/report.json')
    assert audit['result'] == 'radial_geometry_all_QP_certificates_and_entire_fit_trace_reconstructed'
    report['reports_sha256'] = {name: sha(root/name/'report.json') for name in ('controls1', 'fit1', 'audit1')}
    sources = {Path(__file__)}
    for name, digest in audit['sources'].items():
        assert sha(repo/name) == sha(root/'audit1/exact_sources'/name) == digest
        sources.add(repo/name)
    for source in sources:
        relative = source.relative_to(repo); target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)
    topology = load(repo/'research/observed_topology_v1_plan.json'); base = load(repo/topology['base_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    time, _, truth, _ = make(case, base); interior = (time >= 5)&(time < 35)
    scalar = load(parent/'report.json'); radial = load(root/'fit1/report.json')
    figure = plt.figure(figsize=(11, 6.8), layout='constrained')
    grid = figure.add_gridspec(2, 2, height_ratios=(1.5, 1))
    axis = figure.add_subplot(grid[0, :])
    for label, folder in (('Scalar Re/Im soft-L1', parent), ('Complex radial soft-L1', root/'fit1')):
        phase = np.load(folder/'fit.npz')['phase_correction']
        error = phase-truth; error -= np.median(error[interior])
        axis.plot(time[interior], error[interior], label=label, linewidth=1)
    gate = load(root/'fit1/effective_plan.json')['rules']['maximum_point_phase_p95_cycles']
    for sign in (-1, 1):
        axis.axhline(sign*gate, color='black', linestyle='--', linewidth=.8)
    axis.set(xlabel='Coarse-cycle coordinate', ylabel='Phase error (cycles)',
        title='Original dense36 known control: both fits fail the unchanged phase-p95 gate')
    axis.legend(loc='upper left')
    for column, (label, value) in enumerate((('Scalar Re/Im objective', scalar), ('Complex radial objective', radial))):
        axis = figure.add_subplot(grid[1, column]); fit = value['fit']
        current = fit['initial_cost']; costs = [current]
        for row in fit['history']:
            if row['accepted']: current = row['candidate_cost']
            costs.append(current)
        axis.plot(range(len(costs)), np.asarray(costs)/fit['initial_cost'], marker='.', markersize=4)
        axis.set(xlabel='Trust iteration', ylabel='Cost / own initial cost', title=label)
        axis.set_ylim(0, 1.05); axis.grid(alpha=.2)
    figure.suptitle('Coordinate-invariant robust geometry is verified; extraction accuracy is not qualified')
    figure.savefig(args.out/'complex_radial_comparison.png', dpi=150); plt.close(figure)
    report.update(result='fixed_dense_phase_and_separate_metric_curves_published',
        plot_sha256=sha(args.out/'complex_radial_comparison.png'),
        phase_p95=audit['phase_p95'], full_qualification=False,
        limits=['Dashed phase lines show the p95 magnitude threshold, not pointwise acceptance',
            'Each cost curve is normalized within its own metric; the two vertical scales do not compare quality',
            'Known synthetic qualification only; no new recording, audio, DNA or C change'])
    print(json.dumps(dict(result=report['result'], plot_sha256=report['plot_sha256'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
