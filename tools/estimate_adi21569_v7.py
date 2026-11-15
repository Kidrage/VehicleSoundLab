"""Inventory conditional-phase tables and extend the unmeasured V6 cost model.

This does not optimize or benchmark a SHARC+ program. All cycles are explicit
planning assumptions; source/model files are read-only. Five offline outputs
are alternatives, and only one conditional CDF per harmonic is counted.
"""
import argparse
import hashlib
import json
import math
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

    previous = json.loads(read(repo / 'research/adi21569_estimate_v6_summary.json'))
    for path, expected in previous['input_sha256'].items():
        read(path)
        assert hashes[path] == expected, path
    for name in (
        'tools/estimate_adi21569_v7.py',
        'tools/conditional_phase_time_v1/generator.py',
        'tools/conditional_phase_time_v1/mapping.py',
        'research/conditional_phase_time_v1_plan.json',
        'research/conditional_phase_slope_v1_summary.json',
    ):
        read(repo / name)

    profiles = []
    table_root = args.workspace / 'baselines/conditional_phase_slope_v1/evidence/real5'
    for old_profile in previous['research_candidate_profiles']:
        label = old_profile['name']
        rows = []
        for order in range(1, 289):
            path = table_root / label / f'{order:03d}/model.npz'
            read(path)
            with np.load(path, allow_pickle=False) as model:
                knots = model['knots']
                low, high = model['low'], model['high']
                cdf = model['variation_cdf']
                assert len(knots) == 32
                assert 40 <= len(low) <= 42
                assert cdf.shape == (len(knots), len(low) + 1)
                assert high.shape == low.shape
                assert np.all(np.diff(knots) > 0)
                assert np.all(np.diff(cdf, axis=1) >= -2e-12)
                rows.append(dict(
                    order=order, knots=len(knots), phase_cells=len(low),
                    knot_binary_comparisons_max=math.ceil(math.log2(len(knots)+1)),
                    phase_binary_comparisons_max=math.ceil(math.log2(len(low))),
                    selected_runtime_table_FP32_bytes=4*(cdf.size+knots.size+low.size+high.size),
                    precomputed_knot_reciprocals_FP32_bytes=4*(len(knots)-1)))
        table_bytes = sum(row['selected_runtime_table_FP32_bytes'] for row in rows)
        reciprocal_bytes = sum(row['precomputed_knot_reciprocals_FP32_bytes'] for row in rows)
        profiles.append(dict(
            name=label, harmonics=len(rows), table_rows=rows,
            selected_runtime_table_FP32_bytes=table_bytes,
            added_precomputation_FP32_bytes=reciprocal_bytes+4*288,
            retained_full_profile_FP32_bytes=old_profile['numeric_profile_FP32_bytes'],
            combined_numeric_FP32_bytes=table_bytes+reciprocal_bytes+4*288+
                old_profile['numeric_profile_FP32_bytes']))
    assert len(profiles) == 6
    assert sum(p['harmonics'] for p in profiles) == 1728
    max_knots = max(r['knot_binary_comparisons_max'] for p in profiles for r in p['table_rows'])
    max_cells = max(r['phase_binary_comparisons_max'] for p in profiles for r in p['table_rows'])

    # Candidate implementation: primary stream projects amplitudes and common
    # phase (3H features); independent stream projects relative uniform (H).
    # Prune unused projections, but retain both full RNG/AR endpoint streams.
    rate, h, k = 48000, 288, 12
    updates = previous['endpoint_update_rate_Hz']
    visits = rate*h
    old = previous['research_candidate_assumed_cycle_costs']

    def cost(count, bounds):
        return [count*x/1e6 for x in bounds]

    mapping_cycles = dict(
        amplitude_product_and_scale=[2, 4],
        knot_search_effective_cycles_per_comparison=[2, 4],
        clamp_and_hat_weight_with_precomputed_reciprocal=[5, 8],
        phase_search_interpolated_CDF_effective_cycles_per_comparison=[6, 10],
        final_CDF_edges_reciprocal_and_phase_reconstruction=[16, 28])
    mapper = [mapping_cycles['amplitude_product_and_scale'][i]
              + max_knots*mapping_cycles['knot_search_effective_cycles_per_comparison'][i]
              + mapping_cycles['clamp_and_hat_weight_with_precomputed_reciprocal'][i]
              + max_cells*mapping_cycles['phase_search_interpolated_CDF_effective_cycles_per_comparison'][i]
              + mapping_cycles['final_CDF_edges_reciprocal_and_phase_reconstruction'][i]
              for i in (0, 1)]
    counts = dict(
        primary_projected_features=3*h, independent_projected_features=h,
        projection_scalar_MAC_per_second=rate*4*h*k,
        variance_corrected_features_per_second=rate*4*h,
        empirical_quantile_features_per_second=rate*3*h,
        independent_uniform_features_per_second=visits,
        conditional_inverse_CDFs_per_second=visits,
        shared_factor_normalizations_per_second=rate*2*k,
        full_two_stream_Gaussian_AR_outputs_per_second=updates*2*(4*h+k),
        stereo_partials_per_second=visits)
    terms = dict(
        projection=cost(counts['projection_scalar_MAC_per_second'], old['projection_MAC']),
        residual_interpolation_variance_and_add=cost(rate*4*h,
            old['residual_interpolation_variance_and_add_per_feature']),
        amplitude_and_common_phase_fused_CDF_quantile=cost(rate*3*h,
            old['fused_normal_CDF_quantile_per_feature']),
        independent_phase_normal_CDF=cost(visits, [4, 8]),
        conditional_inverse_CDF=cost(visits, mapper),
        both_streams_shared_factor_normalization=cost(rate*2*k,
            old['shared_factor_interpolation_variance_per_factor']),
        stereo_OSC_and_sum=cost(visits, old['varying_phase_stereo_partial']),
        both_full_Gaussian_AR_streams=cost(counts['full_two_stream_Gaussian_AR_outputs_per_second'],
            old['Gaussian_output_and_AR_state']),
        basic_controller_events_mix=old['controller_mix_events_basic_stereo_MCPS'])
    total = [sum(v[i] for v in terms.values()) for i in (0, 1)]
    result = dict(
        schema='vsl.adi21569-cycle-estimate/7',
        code_basis=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        measured=False, guaranteed_WCET=False, established_minimum_cost=False,
        optimized_target_port_implemented=False,
        input_sha256=hashes, all_V6_inputs_exact=True,
        sample_rate=rate, assumed_core_clock_MHz=1000,
        current_C_upper_MCPS=previous['current_C_largest_estimated_upper_MCPS'],
        current_C_planning_MCPS=800, current_C_allocation_MCPS=900,
        previous_research_candidate_cases=previous['research_candidate_cases'],
        conditional_candidate=dict(
            scope='One frozen anchor and one conditional variant; hypothetical native48k target port, not full driving product',
            profiles=profiles, counts=counts,
            binary_search_comparisons=dict(knots=max_knots, phase_cells=max_cells),
            additional_cycle_assumptions=dict(
                normal_CDF_only=[4, 8], conditional_inverse_CDF=mapping_cycles,
                combined_mapper_per_stereo_partial=mapper),
            terms_MCPS=terms, sum_MCPS=total,
            rounded_planning_upper_MCPS=math.ceil(total[1]/100)*100,
            cycles_per_240_frame_block=[x*1e6*240/rate for x in total]),
        qualifications=[
            'Cycle ranges are unmeasured scenarios, not guaranteed maximums or proof that further optimization cannot fit.',
            'All prior FP32/SIMD/lookup cost coefficients retained; no new instruction throughput claims.',
            'CDF binary searches evaluate only required edges from two P rows; no full CDF row constructed per sample.',
            'Five offline comparison outputs, three conditional maps and six source profiles are alternatives, not concurrent voices.',
            'LP solving, certificates, Hann observer, training and diagnostic statistics are offline and excluded.',
            'Two independent RNG/AR streams counted; unused audio-rate projections pruned without changing required random streams.',
            'Full288 harmonics and12 factors retained; maximum update333.33Hz is inherited engineering envelope, not measured ECU RPM.',
            'No lower temporal rate, order reduction, density truncation or uniform inverse-table approximation credited.',
            'Steep phase CDF tails require independent FP32/LUT error and listening qualification before deployment.',
            'Table byte counts exclude state/code/cache/stack/DMA/buffers; effective costs do not bound external-memory stalls.',
            'Existing-C and research rows are alternatives; full multi-anchor conditional morph and separate BODY/DETAIL/IR are not included.',
            'Current generator is normalized-coordinate diagnostic code; native48k aliasing and target audio have not been qualified.',
            'Blocks can exceed per-second averages when endpoint updates cluster; no target WCET or PC-to-SHARC timing conversion.',
        ],
        no_runtime_C_model_driver_hearing_change=True,
        next='CCES FP32/SIMD oscillator/projection/conditional-mapper kernels, numeric qualification, actual memory placement, maximum block counters')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                        encoding='utf-8', newline='\n')
    print(json.dumps(dict(
        verified_conditional_models=1728, all_V6_inputs_exact=True,
        current_C_upper_MCPS=result['current_C_upper_MCPS'],
        conditional_mapper_cycles=mapper, terms_MCPS=terms, total_MCPS=total,
        numeric_profile_MiB=[p['combined_numeric_FP32_bytes']/2**20 for p in profiles]), indent=2))


if __name__ == '__main__':
    main()
