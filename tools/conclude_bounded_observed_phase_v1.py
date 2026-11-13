"""Derive fixed-case ratios and original-bound activity without any fitting."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/python_deps')]
import numpy as np
from drive_evidence_v1.sources import sha


def load(path): return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-observed-phase-conclusion/1', result='running', sources={},
    real_audio_read=False, model_exported=False, runtime_changed=False, nonlinear_fits_run=False,
    full_qualification=False)
try:
    root = args.workspace/'references/analysis/bounded_observed_phase_v1'
    pair = load(root/'pair2/report.json'); audit = load(root/'audit1/report.json'); review = load(root/'review1/report.json')
    assert audit['all_actual40_steps_audited'] and review['result'] == 'fixed_observed_pairs_cross_evaluated_and_published_no_estimator_change'
    assert review['reports_sha256']['pair2'] == audit['candidate_report_sha256'] == sha(root/'pair2/report.json')
    paths = {Path(__file__)}
    for name, digest in review['sources'].items():
        assert sha(repo/name) == sha(root/'review1/exact_sources'/name) == digest; paths.add(repo/name)
    for path in paths:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    parent = args.workspace/'references/analysis/complex_radial_v1/fit1'
    plan = load(parent/'effective_plan.json'); settings = load(parent/'effective_settings.json')
    arrays = np.load(root/'pair2/direction.npz'); parts = len(plan['source_orders'])
    start = 2*parts+len(arrays['direction']); tolerance = settings['maximum_primal_violation']
    bounds = []
    for key in ('baseline', 'minus', 'plus'):
        parameters = arrays['base_parameters' if key == 'baseline' else key+'_parameters']
        beta = parameters[start:]; cartesian = parameters[:2*parts]
        count = int(np.count_nonzero(abs(abs(beta)-plan['amplitude_control_bound']) <= tolerance))
        direct = sum(math.isclose(abs(float(v)), plan['amplitude_control_bound'], abs_tol=tolerance, rel_tol=0) for v in beta)
        assert count == direct
        bounds.append(dict(model=key, relative_envelope_controls=len(beta), relative_envelope_bound_count=count,
            cartesian_bound_count=int(np.count_nonzero(abs(abs(cartesian)-1) <= tolerance)),
            relative_envelope_minimum=float(beta.min()), relative_envelope_maximum=float(beta.max()),
            bound_tolerance_from_original_settings=tolerance))
    ratios = []
    for metric in ('native', 'marginal'):
        base = next(row for row in review['comparisons'] if row['metric'] == metric and row['model'] == 'baseline')
        for key in ('minus', 'plus'):
            row = next(row for row in review['comparisons'] if row['metric'] == metric and row['model'] == key)
            ratios.append(dict(metric=metric, model=key,
                original_data_radial_cost_ratio_to_same_metric_baseline=row['radial_original_data_cost']/base['radial_original_data_cost']))
    final_cases = []
    for row, checked in zip(pair['cases'], audit['cases']):
        assert row['id'] == checked['id']
        final_cases.append(dict(id=row['id'], norm_reduction_fraction=1-row['raw_difference_after']/row['raw_difference_before'],
            phase_p95=row['measured_phase_difference_p95'], raw_difference_before=row['raw_difference_before'],
            raw_difference_after=row['raw_difference_after'], iterations=row['fit']['iterations'],
            accepted_steps=row['fit']['accepted_steps'], every_QP_certified=row['fit']['every_subproblem_certified'],
            after_edge_energy_fraction=1-checked['partitions']['after']['interior_energy_fraction'],
            after_interior_difference_norm=checked['partitions']['after']['region_norms']['interior']))
    report.update(result='fixed_observed_direction_visible_after_bounded_compensation_not_original_error_explanation',
        reports_sha256={n: sha(root/n/'report.json') for n in ('pair2', 'audit1', 'review1')},
        original_bound_activity=bounds, fixed_case_summaries=final_cases, same_metric_cost_ratios=ratios,
        next_step='Return original dense36 extraction bias: observed initialization and observation/noise correlation evidence. '
            'Do not keep scanning weak directions, loosen bounds, infer causality from active controls, or use truth/heldouts for fits.',
        limits=['Active envelope bounds do not by themselves prove insufficient model bandwidth or cause of phase bias',
            'Only this fixed direction/sign2 and finite local fits; no all-direction uniqueness or global minimum',
            'Neither fixed-pair norms nor cost ratios certify estimator recovery or real engine naturalness'])
    print(json.dumps(dict(result=report['result'], bounds=bounds, ratios=ratios)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
