"""Separate known fixture noise/model errors; never initialize an estimator."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--diagnosis',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from scipy.optimize import lsq_linear
from scipy.interpolate import BSpline
from drive_evidence_v1.sources import sha
from absolute_amplitude_v1.model import AbsoluteModel
from absolute_amplitude_v1.amplitude import cost
from aperture_model_v1.forward import real_rows
from observed_topology_v1.fixtures import make


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.joint-trust-known-noise-budget/1',result='running',sources={},
    real_audio_read=False,real_source_permitted=False,qualification_changed=False,
    may_initialize_estimator=False,analytic_truth_used_only_for_diagnosis=True,
    nonlinear_estimator_rerun=False)
try:
    parent=load(args.diagnosis/'report.json')
    assert parent['result'] in ('dense_diagnostic_rejected','dense_diagnostic_passed_not_full_qualification')
    report['diagnosis_report_sha256']=sha(args.diagnosis/'report.json')
    sources={Path(__file__)}|{repo/name for name in parent['sources']}
    for relative,digest in parent['sources'].items():
        assert sha(repo/relative)==sha(args.diagnosis/'exact_sources'/relative)==digest
    for path in sources:
        relative=path.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    topology=load(repo/'research/observed_topology_v1_plan.json')
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    case=next(row for row in topology['added_cases'] if row['id']=='unknown_thirty_six')
    time,audio,truth,_=make(case,base)
    _,clean,clean_truth,_=make({**case,'noise':0.},base)
    _,source,source_truth,_=make({**case,'noise':0.},{**base,'heldout_orders':[]})
    assert np.array_equal(truth,clean_truth) and np.array_equal(truth,source_truth)
    plan=load(args.diagnosis/'effective_plan.json')
    saved=np.load(args.diagnosis/'fit.npz')
    assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
    model=AbsoluteModel(time,plan,variant,parent['fit']['selected_indices'])
    project=lambda value:real_rows(model.original.aperture.apply(value))
    observed=project(audio[:,0])
    clean_observation=project(clean[:,0])
    source_observation=project(source[:,0])
    noise=observed-clean_observation
    heldout=clean_observation-source_observation
    predicted=model.original.prediction(saved['parameters'])
    model_error=predicted-source_observation
    residual=predicted-observed
    closure=float(abs(residual-(model_error-heldout-noise)).max())
    assert closure<1e-12
    interior=(time>=5)&(time<35)
    spline=lsq_linear(model.original.phase_basis,truth,
        bounds=(-plan['phase_control_bound_cycles'],plan['phase_control_bound_cycles']),tol=1e-13)
    approximation=model.original.phase_basis@spline.x
    phase_error=approximation-truth
    phase_error-=np.median(phase_error[interior])
    phase_p95=float(np.percentile(abs(phase_error[interior]),95))
    oracle_root=args.workspace/'references/analysis/guard_observation_v1/band_oracle1'
    oracle_report=load(oracle_root/'report.json')
    oracle=np.load(oracle_root/'oracle_amplitudes.npz')
    assert oracle_report['may_initialize_estimator'] is False
    known=oracle['parameters'].copy()
    m=model.original
    known[2*m.parts:2*m.parts+m.phase_count]=spline.x
    known_prediction=m.prediction(known)
    absolute=oracle['absolute_controls']
    c0=np.hypot(known[:m.parts],known[m.parts:2*m.parts])
    envelope=(model.full@absolute.T)/c0[None,:]
    def known_source_projection(coordinate):
        angle=2*np.pi*coordinate[:,None]*m.orders[None,:]
        samples=np.sum(envelope*(np.cos(angle)*known[None,:m.parts]
            +np.sin(angle)*known[None,m.parts:2*m.parts]),axis=1)
        return project(samples)
    exact_phase_prediction=known_source_projection(time+truth)
    oracle_normalized=float(np.linalg.norm(exact_phase_prediction-observed)/np.linalg.norm(observed))
    assert abs(oracle_normalized-oracle_report['normalized_projection_residual_at_exact_phase'])<1e-12
    spacing=plan['phase_knot_cycles']
    quintic_knots=np.r_[[0.]*6,np.arange(spacing,plan['cycles'],spacing),[float(plan['cycles'])]*6]
    quintic_full=BSpline.design_matrix(time,quintic_knots,5).toarray()
    assert quintic_full.min()>=-1e-12 and abs(quintic_full.sum(axis=1)-1).max()<1e-12
    quintic=quintic_full[:,1:]
    assert abs(quintic[0]).max()==0
    quintic_fit=lsq_linear(quintic,truth,bounds=(-plan['phase_control_bound_cycles'],
        plan['phase_control_bound_cycles']),tol=1e-13)
    quintic_phase=quintic@quintic_fit.x
    quintic_error=quintic_phase-truth
    quintic_error-=np.median(quintic_error[interior])
    quintic_prediction=known_source_projection(time+quintic_phase)
    lower,upper=m.bounds(plan,variant)
    assert np.max(lower-known)<=1e-10 and np.max(known-upper)<=1e-10
    current_outer,current_controls=model.unpack(saved['parameters'])
    _,current_phase,_=m.samples(saved['parameters'])
    def band_fractions(values,cutoff):
        centered=values[interior]-np.mean(values[interior])
        spectrum=np.fft.rfft(centered*np.hanning(len(centered)))
        frequencies=np.fft.rfftfreq(len(centered),d=1/plan['samples_per_cycle'])
        power=abs(spectrum)**2
        return float(power[frequencies>cutoff].sum()/max(power.sum(),1e-30))
    minimum_gap=float(np.min(np.diff(m.orders)))
    cutoff=minimum_gap/2
    actual_error=current_phase-truth
    actual_error-=np.median(actual_error[interior])
    noise_norm=float(np.linalg.norm(noise))
    report.update(result='diagnosed_known_noise_and_representation_no_qualification',
        projection_closure_maximum_error=closure,
        projection_norms=dict(noise=noise_norm,heldout_leak=float(np.linalg.norm(heldout)),
            model_error=float(np.linalg.norm(model_error)),actual_residual=float(np.linalg.norm(residual)),
            actual_model_vs_clean=float(np.linalg.norm(predicted-clean_observation)),
            feasible_true_phase_model_vs_clean=float(np.linalg.norm(known_prediction-clean_observation)),
            exact_known_phase_amplitude_vs_clean=float(np.linalg.norm(exact_phase_prediction-clean_observation)),
            cubic_phase_approximation_increment=float(np.linalg.norm(known_prediction-exact_phase_prediction)),
            same_spacing_quintic_increment=float(np.linalg.norm(quintic_prediction-exact_phase_prediction))),
        original_robust_costs=dict(actual_on_noisy=cost(residual,plan['soft_l1_scale']),
            actual_on_clean=cost(predicted-clean_observation,plan['soft_l1_scale']),
            feasible_true_phase_on_noisy=cost(known_prediction-observed,plan['soft_l1_scale']),
            feasible_true_phase_on_clean=cost(known_prediction-clean_observation,plan['soft_l1_scale']),
            exact_known_phase_on_clean=cost(exact_phase_prediction-clean_observation,plan['soft_l1_scale']),
            quintic_known_phase_on_clean=cost(quintic_prediction-clean_observation,plan['soft_l1_scale'])),
        fitted_model_error_noise_correlation=float(np.dot(model_error,noise)/max(np.linalg.norm(model_error)*noise_norm,1e-30)),
        common_phase_representation=dict(solver_success=bool(spline.success),
            best_L2_approximation_phase_p95_cycles=phase_p95,
            original_phase_gate=plan['rules']['maximum_point_phase_p95_cycles'],
            meets_point_gate=phase_p95<=plan['rules']['maximum_point_phase_p95_cycles']),
        higher_order_representation_diagnostic=dict(degree=5,knot_cycles=spacing,
            original_controls=m.phase_count,quintic_controls=quintic.shape[1],
            original_phase_origin_and_bound_retained=True,
            best_L2_phase_p95_cycles=float(np.percentile(abs(quintic_error[interior]),95)),
            solver_success=bool(quintic_fit.success),actual_estimator_run=False,
            fixed_declared_comparison_not_a_degree_or_knot_sweep=True),
        diagnostic_spectral_cutoff_from_half_gap=cutoff,
        above_cutoff_power_fraction=dict(analytic_true_phase=band_fractions(truth,cutoff),
            actual_phase_error=band_fractions(actual_error,cutoff)),
        amplitude_oracle_report_sha256=sha(oracle_root/'report.json'),
        limits=['Known source/noise/phase and prior analytic amplitude feasibility are used only here, never for estimation',
            'A feasible near-true-phase candidate is not the optimum at fixed true phase',
            'Quintic comparison uses analytic truth for representation diagnosis only, not initialization, actual estimation or qualification',
            'Noise correlation and representation checks are local evidence, not physical crank/RPM identifiability or real-recording uncertainty'])
    np.savez_compressed(args.out/'diagnostic_arrays.npz',time=time,true_phase=truth,
        best_L2_phase_approximation=approximation,quintic_known_phase_approximation=quintic_phase,actual_phase=current_phase,
        projected_noise=noise,projected_heldout=heldout,projected_model_error=model_error,
        actual_residual=residual,known_phase_feasible_parameters=known)
    print(json.dumps({key:report[key] for key in ('result','projection_norms','original_robust_costs','common_phase_representation','above_cutoff_power_fraction')}),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
