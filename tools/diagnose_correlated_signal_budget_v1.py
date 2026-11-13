"""Measure exact model/omission/noise residual terms after the frozen marginal fit."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from correlated_observation_v1.decomposition import analytic_components
from aperture_model_v1.forward import real_rows


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.correlated-signal-budget/1', result='running', sources={}, cases=[],
    real_audio_read=False, nonlinear_estimator_rerun=False, initialization_changed=False,
    heldout_added_to_fit=False, model_exported=False, runtime_changed=False)
try:
    fit_report = load(args.candidate/'report.json')
    assert fit_report['result'] == 'dense_marginal_metric_rejected'
    assert fit_report['parent_report_sha256'] == sha(args.native/'report.json')
    paths = {Path(__file__), repo/'research/correlated_signal_budget_v1_plan.json',
        repo/'tools/correlated_observation_v1/decomposition.py'}|{repo/p for p in fit_report['sources']}
    for path in paths:
        relative = path.relative_to(repo)
        if relative.as_posix() in fit_report['sources']:
            assert sha(path) == fit_report['sources'][relative.as_posix()]
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    plan = load(args.candidate/'effective_plan.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    topology = load(repo/'research/observed_topology_v1_plan.json')
    base = load(repo/topology['base_plan'])
    case = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    inputs = np.load(args.candidate/'input.npz')
    time, audio = inputs['time'], inputs['audio']
    exact, omitted, noise = analytic_components(time, case['fixture_orders'], base['heldout_orders'], case)
    closure = float(abs(audio-(exact+omitted+noise)).max())
    assert closure <= plan['rules']['maximum_forward_check_error']
    model, native = (QuinticAbsoluteModel(time, plan, variant, []) for _ in range(2))
    model.original.aperture = MarginalAperture(model.original.aperture)
    saved_arrays = {}
    for label, path in (('native_fit', args.native), ('marginal_fit', args.candidate)):
        fitted = np.load(path/'fit.npz')['parameters']
        predicted = native.original.samples(fitted)[0]
        raw = np.column_stack((predicted-exact[:, 0], -omitted[:, 0], -noise[:, 0]))
        actual = predicted-audio[:, 0]
        raw_error = float(abs(raw.sum(axis=1)-actual).max())
        assert raw_error <= plan['rules']['maximum_forward_check_error']
        saved_arrays[label+'_raw_components'] = raw
        for name, operator in (('native', native.original.aperture), ('marginal', model.original.aperture)):
            transformed = real_rows(operator.apply(raw))
            residual = real_rows(operator.apply(actual))
            error = float(abs(transformed.sum(axis=1)-residual).max())
            assert error <= plan['rules']['maximum_forward_check_error']
            gram = transformed.T@transformed
            total = float(residual@residual)
            assert abs(float(gram.sum())-total) <= plan['rules']['maximum_forward_check_error']
            norms = np.sqrt(np.diag(gram))
            correlation = gram/(norms[:, None]*norms[None, :])
            report['cases'].append(dict(parameters=label, metric=name,
                component_order=['model_waveform_error', 'negative_omitted_carriers', 'negative_source_noise'],
                observation_closure_maximum_error=error,
                complete_energy_Gram=gram.tolist(), residual_energy=total,
                component_norms=norms.tolist(), component_correlations=correlation.tolist(),
                energy_closure_absolute_error=abs(float(gram.sum())-total)))
            saved_arrays[label+'_'+name+'_components'] = transformed
    np.savez_compressed(args.out/'components.npz', **saved_arrays)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for index, name in enumerate(('native', 'marginal')):
        selected = [row for row in report['cases'] if row['metric'] == name]
        for k, row in enumerate(selected):
            axes[index].bar(np.arange(3)+(k-.5)*.35, row['component_norms'], width=.35,
                            label=row['parameters'])
        axes[index].set(xticks=np.arange(3), xticklabels=['Model error', 'Omitted carriers', 'Source noise'],
            ylabel='Projected component L2 norm', title=name+' metric; cross terms reported separately')
        axes[index].legend()
    figure.savefig(args.out/'correlated_signal_budget.png', dpi=150)
    plt.close(figure)
    report.update(result='known_fixture_raw_and_observation_residual_budgets_closed',
        candidate_report_sha256=sha(args.candidate/'report.json'), fixture_closure_maximum_error=closure,
        source_noise_sigma=case['noise']*case['gain'], plot_sha256=sha(args.out/'correlated_signal_budget.png'),
        limitations=['Known synthetic fixture only; not real engine/source separation or a corrected estimator',
            'Components have cross terms; their separate energies do not add without the complete Gram',
            'No unique causal attribution, global optimum, confidence interval or unavoidable phase lower bound'])
    print(json.dumps(dict(result=report['result'], cases=report['cases'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
