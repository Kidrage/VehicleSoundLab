"""Check finite original-bound clock changes and coefficient compensation."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import scipy
from scipy.special import log_ndtr
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from bounded_clock_pair_v1.pair import construct
from bounded_clock_pair_v1.checks import check


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-clock-pair/1', result='running', sources={},
    real_audio_read=False, truth_used=False, heldout_used=False, nonlinear_estimator_run=False,
    linear_coefficient_solves=True, phase_estimator_qualified=False,
    model_exported=False, runtime_changed=False)
try:
    parent = load(args.native/'report.json')
    paths = {Path(__file__), repo/'research/bounded_clock_pair_v1_plan.json',
             *sorted((repo/'tools/bounded_clock_pair_v1').glob('*.py'))}
    for relative, digest in parent['sources'].items():
        assert sha(repo/relative) == sha(args.native/'exact_sources'/relative) == digest
        paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    plan = load(args.native/'effective_plan.json')
    inputs = np.load(args.native/'input.npz')
    model = QuinticAbsoluteModel(inputs['time'], plan, load(repo/'research/minority_phase_v1_plan.json'), [])
    rows, saved, construction = construct(model, inputs['initial_parameters'], plan)
    np.savez_compressed(args.out/'pairs.npz', **saved)
    report.update(native_input_sha256=sha(args.native/'input.npz'),
        native_plan_sha256=sha(args.native/'effective_plan.json'),
        native_report_sha256=sha(args.native/'report.json'),
        pairs_sha256=sha(args.out/'pairs.npz'), construction=construction,
        numeric_libraries=dict(numpy=np.__version__, scipy=scipy.__version__),
        controls=check(model, inputs['initial_parameters'], plan, rows, saved))
    # Synthetic sigma is used for this diagnostic only after constructing pairs.
    topology = load(repo/'research/observed_topology_v1_plan.json')
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    sigma = case['noise']*case['gain']
    for row, key in zip(rows, ('minus', 'plus')):
        difference = saved[key+'_waveform']-saved['base_waveform']
        distance = float(np.linalg.norm(difference)/sigma)
        native_difference = model.original.aperture.apply(difference)
        row.update(known_raw_white_sigma=sigma, fixed_pair_raw_Gaussian_distance=distance,
            fixed_pair_Gaussian_KL=distance*distance/2,
            fixed_pair_equal_prior_log_binary_error=float(log_ndtr(-distance/2)),
            native_relative_model_difference=float(np.linalg.norm(native_difference)/
                np.linalg.norm(model.original.aperture.apply(saved['base_waveform']))),
            difference_to_expected_full_noise_norm=distance/np.sqrt(len(difference)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(2, 1, figsize=(10, 6), layout='constrained')
    axes[0].plot(saved['time'], saved['perturbation'])
    axes[0].set(ylabel='Clock perturbation (cycles)', title='One predeclared minimum-gap direction; both signs feasible')
    for key in ('minus', 'plus'):
        axes[1].plot(saved['time'], saved[key+'_waveform']-saved['base_waveform'], label=key, linewidth=.7)
    axes[1].set(xlabel='Coarse-cycle coordinate', ylabel='Finite raw model difference')
    axes[1].legend()
    figure.savefig(args.out/'bounded_clock_pairs.png', dpi=150)
    plt.close(figure)
    report.update(result='finite_bounded_clock_pairs_measured_not_phase_qualification', cases=rows,
        plot_sha256=sha(args.out/'bounded_clock_pairs.png'),
        limitations=['One predeclared direction and fixed real envelopes; not all nuisance/phase directions',
            'Raw Gaussian binary distance assumes the stated synthetic independent sample noise and fixed hypotheses',
            'Neither a confidence interval, a global phase identifiability claim nor real coloured-noise calibration',
            'No actual recording fit, real model, changed gates or full33/HF qualification'])
    print(json.dumps(dict(result=report['result'], controls=report['controls'], cases=rows)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
