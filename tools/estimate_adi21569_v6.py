"""Separate unchanged runtime C costs from the audio-rate research candidate.

All cycle coefficients are assumptions, not measured SHARC+ instructions or
WCET. This inventories existing inputs; it does not implement an optimization.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
    import numpy as np

    repo = Path(__file__).resolve().parents[1]
    hashes = {}

    def read(path):
        path = Path(path)
        raw = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        return raw

    base = json.loads(read(repo / 'research/adi21569_estimate_v5_summary.json'))
    for name, expected in base['input_sha256'].items():
        raw = read(repo / name)
        assert hashlib.sha256(raw).hexdigest() == expected, name
    for name in (
        'tools/estimate_adi21569_v6.py',
        'tools/relative_phase_v1/render.py',
        'tools/relative_phase_v1/coordinates.py',
        'tools/relative_phase_v1/profile.py',
        'tools/radial_copula_v1/latent.py',
        'tools/radial_copula_v1/quantiles.py',
    ):
        read(repo / name)

    folder = args.workspace / 'references/analysis/relative_phase_v1/real1'
    producer = json.loads(read(folder / 'report.json'))
    expected_profiles = {r['label']: r['profile_sha256'] for r in producer['cases']}
    profiles = []
    for path in sorted(folder.glob('*/profile.npz')):
        read(path)
        assert hashes[str(path)] == expected_profiles[path.parent.name]
        with np.load(path, allow_pickle=False) as model:
            h, channels = model['fixed_phase'].shape
            width, components = model['basis'].shape
            assert (h, channels, width, components) == (288, 2, 1152, 12)
            assert model['amplitude'].shape[1] == model['phase'].shape[1] == 576
            assert model['residual_rho'].shape == (1152,)
            assert model['active'].all()
            profiles.append(dict(
                name=path.parent.name, harmonics=h, channels=channels,
                features=width, components=components,
                quantile_rows=int(model['amplitude'].shape[0]),
                numeric_profile_FP32_bytes=sum(
                    model[k].size * 4 for k in model.files
                    if model[k].dtype.kind in 'fc'),
                distinct_factor_rho=int(len(np.unique(model['rho']))),
                distinct_residual_rho=int(len(np.unique(model['residual_rho'])))))
    assert len(profiles) == 6

    # Preserve V5's effective MAC cost assumption for comparability. Other new
    # coefficients explicitly assume fused FP32/SIMD/table kernels, not scipy
    # ndtr, per-sample libm cos, or the present float64 NumPy implementation.
    costs = dict(
        projection_MAC=[.75, 1.25],
        residual_interpolation_variance_and_add_per_feature=[4, 8],
        fused_normal_CDF_quantile_per_feature=[6, 12],
        shared_factor_interpolation_variance_per_factor=[8, 16],
        fixed_phase_stereo_partial=[12, 22],
        varying_phase_stereo_partial=[20, 34],
        Gaussian_output_and_AR_state=[12, 30],
        controller_mix_events_basic_stereo_MCPS=[35, 60])
    rate, h, k = 48000, 288, 12
    update_rate = 4 * base['assumptions']['root_max_hz']

    def cost(count, coefficient):
        return [count * x / 1e6 for x in coefficient]

    cases = {}
    for name, features, oscillator in (
        ('amplitude_only_fixed_phase', 2*h, 'fixed_phase_stereo_partial'),
        ('amplitude_and_relative_phase', 4*h, 'varying_phase_stereo_partial'),
    ):
        counts = dict(
            projection_scalar_MAC_per_second=rate * features * k,
            nonlinear_feature_evaluations_per_second=rate * features,
            shared_factor_evaluations_per_second=rate * k,
            stereo_partial_evaluations_per_second=rate * h,
            Gaussian_and_AR_outputs_per_second=update_rate * (4*h+k))
        terms = dict(
            projection=cost(counts['projection_scalar_MAC_per_second'], costs['projection_MAC']),
            residual_interpolation_variance_and_add=cost(rate * features,
                costs['residual_interpolation_variance_and_add_per_feature']),
            fused_normal_CDF_quantile=cost(rate * features,
                costs['fused_normal_CDF_quantile_per_feature']),
            shared_factor_interpolation_variance=cost(rate * k,
                costs['shared_factor_interpolation_variance_per_factor']),
            stereo_OSC_and_sum=cost(rate * h, costs[oscillator]),
            Gaussian_and_AR_state=cost(counts['Gaussian_and_AR_outputs_per_second'],
                costs['Gaussian_output_and_AR_state']),
            controller_mix_events_basic_stereo=costs['controller_mix_events_basic_stereo_MCPS'])
        cases[name] = dict(counts=counts, terms_MCPS=terms,
                          sum_MCPS=[sum(x[i] for x in terms.values()) for i in (0, 1)])

    result = dict(
        schema='vsl.adi21569-cycle-estimate/6',
        code_basis=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo,
                                           text=True).strip(),
        measured=False, guaranteed_WCET=False,
        optimized_target_port_implemented=False,
        input_sha256=hashes, existing_V5_inventory_exact=True,
        current_C_cases_MCPS={n: r['sum_MCPS'] for n, r in base['cases'].items()},
        current_C_largest_recipe=base['largest_estimated_recipe'],
        current_C_largest_estimated_upper_MCPS=base['largest_estimated_upper_MCPS'],
        current_C_planning_upper_MCPS=800, current_C_allocation_MCPS=900,
        research_candidate_profiles=profiles,
        research_candidate_scope='One fixed-anchor source, one variant, 48k stereo; not integrated full driving recipe',
        research_candidate_assumed_cycle_costs=costs,
        research_candidate_cases=cases,
        research_candidate_extra_LF_resonant_IR_layers_counted=False,
        assumed_clock_MHz=1000, sample_rate=rate,
        endpoint_update_rate_Hz=update_rate,
        basic_12channel_increment_MCPS=base['basic_12channel_increment_MCPS'],
        qualifications=[
            'All costs are unmeasured planning scenarios, not maximum-cycle guarantees or an established optimum.',
            'Current C and research candidates are alternatives; do not add entire recipes together.',
            'Full 288 partials and 12 components counted; no lower modulation rate/order or altered time law credited.',
            'Fixed-phase estimate prunes unused phase projection/mapping only; keeps full endpoint RNG/AR advancement.',
            'Common-factor normalization precedes projection; distinct rhos prevent a single shared postprojection normalization.',
            'Fused CDF/quantile, variance, phase/OSC lookup kernels require target numeric and listening qualification.',
            'Candidate costs include basic controller/event/mix allowance, but no separate LF, resonant detail, IR or wide-RPM atlas.',
            'Candidate is an offline Python experiment; no C port, full state coverage or listening acceptance is implied.',
            'Conditional relative-phase model is not implemented or estimated here.',
            'Profile FP32 byte counts exclude runtime state, code, stack, extra LUTs, other banks and buffers.',
            'Memory placement and cache/DMA contention can exceed the assumed effective cycle costs.',
            'Full-bank audio counts and maximum endpoint update counts form a conservative combined planning envelope.',
            'No PC execution time converted into SHARC cycles; no FFT/FIR accelerator benefit assumed.',
        ],
        exclusions=base['exclusions'],
        next='Target FP32/SIMD kernel prototypes and CCES counters; measure longest block including updates and memory contention.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                        encoding='utf-8', newline='\n')
    print(json.dumps(dict(existing_C_upper_MCPS=result['current_C_largest_estimated_upper_MCPS'],
                          candidate_cases_MCPS={n: r['sum_MCPS'] for n, r in cases.items()},
                          profiles_verified=len(profiles)), indent=2))


if __name__ == '__main__':
    main()
