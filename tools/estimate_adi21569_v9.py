"""Recheck current C budgets and cost the NEW two-row quantile phase law.

All target cycles remain unmeasured assumptions. The quantile law changes the
distribution; it is not an equivalent optimization of the old CDF mixture.
Neither implementation described below is a qualified target implementation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    hashes = {}

    def read(path):
        path = Path(path)
        if not path.is_absolute():
            path = repo / path
        data = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(data).hexdigest()
        return data

    v8 = json.loads(read('research/adi21569_estimate_v8_summary.json'))
    for path, expected in v8['input_sha256'].items():
        read(path)
        if hashes[str(Path(path))] != expected:
            raise ValueError(f'V8 input changed: {path}')
    v7 = json.loads(read('research/adi21569_estimate_v7_summary.json'))
    for name in (
        'tools/estimate_adi21569_v9.py',
        'tools/quantile_surface_v1/surface.py',
        'tools/quantile_surface_v1/render.py',
        'tools/quantile_surface_v1/prepare.py',
        'research/quantile_surface_real_v1_plan.json',
    ):
        read(name)

    old = v7['conditional_candidate']
    rate, h, factors = 48000, 288, 12
    assert v8['sample_rate'] == rate
    profiles = old['profiles']
    assert len(profiles) == 6
    rows = [r for p in profiles for r in p['table_rows']]
    assert len(rows) == 1728
    knot_search = max(r['knot_binary_comparisons_max'] for r in rows)
    cell_search = max(r['phase_binary_comparisons_max'] for r in rows)
    assert (knot_search, cell_search) == (6, 6)
    visits = rate * h
    assert old['counts']['projection_scalar_MAC_per_second'] == rate * 4*h*factors

    # Plain row-CDF searches replace interpolated-CDF searches. Simple-search
    # costs reuse V7's knot-comparison assumptions; this is not board evidence.
    # Compact row reconstruction reuses V7's 16..28-cycle inverse allowance.
    # Slope preparation trades one extra FP32 per cell for removing runtime
    # division: low + (u-cdf_left) * prepared_slope. Its 4..8 cycles per row
    # include assumed effective loads/arithmetic after SIMD scheduling.
    common = dict(
        amplitude_product_and_scale=[2, 4],
        knot_search=[knot_search*2, knot_search*4],
        clamp_and_weight=[5, 8],
        two_row_cell_search=[2*cell_search*2, 2*cell_search*4],
        final_quantile_blend=[2, 4])
    implementations = {}
    for name, row_cost in (
        ('compact_runtime_reciprocal', [16, 28]),
        ('prepared_cell_slopes', [4, 8]),
    ):
        mapping_terms = dict(common, two_row_reconstruction=[2*x for x in row_cost])
        mapper = [sum(v[i] for v in mapping_terms.values()) for i in (0, 1)]
        terms = {k: v for k, v in old['terms_MCPS'].items()
                 if k != 'conditional_inverse_CDF'}
        terms['two_row_quantile_mapping'] = [visits*x/1e6 for x in mapper]
        total = [sum(v[i] for v in terms.values()) for i in (0, 1)]
        memory = []
        for p in profiles:
            extra = (sum(4*r['knots']*r['phase_cells'] for r in p['table_rows'])
                     if name == 'prepared_cell_slopes' else 0)
            memory.append(dict(name=p['name'], extra_FP32_bytes=extra,
                               numeric_profile_FP32_bytes=p['combined_numeric_FP32_bytes']+extra))
        implementations[name] = dict(
            mapper_cycle_terms=mapping_terms,
            assumed_mapper_cycles_per_stereo_partial=mapper,
            terms_MCPS=terms, sum_MCPS=total,
            rounded_planning_upper_MCPS=math.ceil(total[1]/100)*100,
            cycles_per_240_frame_block=[x*1e6*240/rate for x in total],
            numeric_profile_sizes=memory,
            measured=False, guaranteed_WCET=False,
            target_numeric_and_hearing_qualification=False)

    result = dict(
        schema='vsl.adi21569-cycle-estimate/9',
        code_basis=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo,
                                           text=True).strip(),
        measured=False, optimized_target_port_implemented=False,
        established_minimum_cost=False, guaranteed_WCET=False,
        input_sha256=hashes, verified_V8_input_count=len(v8['input_sha256']),
        all_V8_inputs_exact=True,
        sample_rate=rate, assumed_core_clock_MHz=1000,
        current_C_cases=v8['cases'], current_C_largest_by_block=v8['largest_by_block'],
        current_C_planning_MCPS=800, current_C_allocation_MCPS=900,
        previous_conditional_research_reference_MCPS=old['sum_MCPS'],
        quantile_surface_research=dict(
            scope='Single anchor, single chosen map; hypothetical native48k target port, not a full driving product',
            law='Invert two adjacent row CDFs separately at the same u, then blend their phase quantiles',
            counts=dict(
                harmonics=h, factors=factors,
                projected_features=4*h,
                projection_scalar_MAC_per_second=rate*4*h*factors,
                stereo_partials_per_second=visits,
                row_inverses_per_second=2*visits,
                max_knot_search_comparisons=knot_search,
                max_two_row_cell_search_comparisons=2*cell_search),
            implementations=implementations),
        basic_12channel_extra_MCPS=v8['basic_12channel_extra_MCPS'],
        qualifications=[
            'Cycle intervals are planning scenarios, not measured maxima or proof of a minimum achievable cost.',
            'Current C recipes are alternatives; source counts, anchor states and V8 periodic job concentration are retained.',
            'Research recipes are alternatives to current C, not extra MCPS to add to its full budget.',
            'Quantile blending is a new distribution with known circular-seam/moment limitations, not an accepted audio preset.',
            'Required per-sample projections and both original RNG/AR streams retained; no temporal-rate or rank reduction credited.',
            'Two six-step phase searches counted even when neighboring row searches could happen to share an index.',
            'Prepared slopes require extra table space and independent FP32 tail/rounding validation; savings are not yet established.',
            'Costs assume effective SIMD, lookup/arithmetic scheduling and sufficiently fast table access; memory stalls are not bounded.',
            'Research cost inherits mean RNG/AR scheduling; unlike V8 C cases it does not establish a block concentration envelope.',
            'State/code/stack/cache/DMA/buffers not included in numeric profile sizes.',
            'No native48k anti-aliasing, target numeric or timbre qualification established for the new research law.',
            'Full research multi-anchor driving/BODY/DETAIL/IR, physical 7.1.4 convolution, other workloads and multiple vehicles excluded.',
            'Offline fitting, LP solves, waveform observers and PC UI excluded; PC seconds never converted to SHARC cycles.',
        ],
        no_runtime_C_model_driver_hearing_change=True,
        next='Qualify CCES kernels, FP32 error and actual memory placement, then measure longest audio-block cycles on ADSP-21569')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                   allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(
        verified_V8_input_count=result['verified_V8_input_count'],
        current_C_planning_MCPS=800,
        research={k: dict(sum_MCPS=v['sum_MCPS'],
                         mapper_cycles=v['assumed_mapper_cycles_per_stereo_partial'],
                         numeric_profile_MiB=[x['numeric_profile_FP32_bytes']/2**20
                                              for x in v['numeric_profile_sizes']])
                  for k, v in implementations.items()}), indent=2))


if __name__ == '__main__':
    main()
