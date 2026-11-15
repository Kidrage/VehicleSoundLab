"""Revalidate V7 inputs and expose periodic-job concentration per audio block.

This reuses UNMEASURED target cycle assumptions. It is neither an optimized
SHARC implementation nor a WCET proof. No runtime/model/audio files are changed.
Only the already-declared endpoint and fine-FIR jobs receive burst factors;
unmodelled stalls, controller/event bursts and bank switching remain unbounded.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess


def periodic_envelope(events_per_sample, frames):
    """Max events for an accumulator initially in [0,1), without backlog."""
    expected = events_per_sample * frames
    maximum = -(-expected.numerator // expected.denominator)
    return dict(mean_events=float(expected), max_events=maximum,
                concentration_factor=float(Fraction(maximum, 1) / expected))


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
        raw = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        return raw

    v7 = json.loads(read('research/adi21569_estimate_v7_summary.json'))
    for path, expected in v7['input_sha256'].items():
        read(path)
        if hashes[str(Path(path))] != expected:
            raise ValueError(f'V7 input changed: {path}')
    v5 = json.loads(read('research/adi21569_estimate_v5_summary.json'))
    v3 = json.loads(read('research/adi21569_estimate_v3_summary.json'))
    for name in ('tools/estimate_adi21569_v8.py',
                 'modules/partitioned_fir/fft.h',
                 'modules/partitioned_fir/filter.c',
                 'modules/spectral_texture/voice.c'):
        read(name)

    rate = v7['sample_rate']
    assert rate == 48000
    header = (repo / 'modules/partitioned_fir/fft.h').read_text()
    assert '#define PF_BLOCK 256' in header
    assert '#define PF_FFT (2*PF_BLOCK)' in header
    standard_root = Fraction(10000, 120)
    startup_root = Fraction(str(v3['inventory']['startup_root_max_hz']))
    endpoint_terms = {
        'DNA_texture', 'five_anchor_texture_projection',
        'all_anchor_texture_projection', 'texture_projection',
        'texture_random_and_state', 'all_three_texture_projection',
        'all_three_texture_random_and_state',
    }
    fine_terms = {'fine_frequency_products', 'fine_FFTs'}
    cases = {}
    for name, old in v5['cases'].items():
        root = startup_root if name == 'legacy_start_settle' else standard_root
        blocks = {}
        for frames in (240, 256, 512):
            endpoint = periodic_envelope(4 * root / rate, frames)
            fine = periodic_envelope(Fraction(1, 256), frames)
            terms = {}
            changed = {}
            for key, values in old['terms_MCPS'].items():
                multiplier = (endpoint['concentration_factor'] if key in endpoint_terms
                              else fine['concentration_factor'] if key in fine_terms
                              else 1.0)
                terms[key] = [v * multiplier for v in values]
                if multiplier != 1:
                    changed[key] = multiplier
            summed = [sum(v[i] for v in terms.values()) for i in (0, 1)]
            blocks[str(frames)] = dict(
                endpoint_schedule=endpoint,
                fine_FIR_schedule=fine if name == 'moving35_plus_current_fine_idle' else None,
                terms_MCPS=terms, adjusted_terms=changed, sum_MCPS=summed,
                cycles_per_block=[v * 1e6 * frames / rate for v in summed],
                guaranteed_WCET=False)
        cases[name] = dict(previous_average_MCPS=old['sum_MCPS'],
                          endpoint_root_envelope_hz=float(root), blocks=blocks)
    largest = {}
    for frames in (240, 256, 512):
        key = str(frames)
        name = max(cases, key=lambda n: cases[n]['blocks'][key]['sum_MCPS'][1])
        upper = cases[name]['blocks'][key]['sum_MCPS'][1]
        largest[key] = dict(recipe=name, known_job_concentration_upper_MCPS=upper,
                            rounded_planning_MCPS=math.ceil(upper / 100) * 100)

    candidate = v7['conditional_candidate']
    assert all(math.isclose(sum(v[i] for v in candidate['terms_MCPS'].values()),
                            candidate['sum_MCPS'][i], rel_tol=1e-14)
               for i in (0, 1))
    result = dict(
        schema='vsl.adi21569-cycle-estimate/8',
        code_basis=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo,
                                           text=True).strip(),
        measured=False, optimized_target_port_implemented=False,
        established_minimum_cost=False, guaranteed_WCET=False,
        previous_goal_turn_classification='progress: frozen real phase-lift experiment; not target optimization',
        sample_rate=rate, assumed_core_clock_MHz=1000,
        verified_V7_input_count=len(v7['input_sha256']), all_V7_inputs_exact=True,
        input_sha256=hashes, cases=cases, largest_by_block=largest,
        current_C_planning_MCPS=800, current_C_allocation_MCPS=900,
        basic_12channel_extra_MCPS=[10, 30],
        conditional_research_reference_MCPS=candidate['sum_MCPS'],
        conditional_reference_scope=candidate['scope'],
        qualifications=[
            'Reuses V2-V7 effective FP32/SIMD cycle assumptions; no new target throughput evidence.',
            'Current C cases are alternative single-vehicle recipes, never simultaneous sums.',
            'Engineering bench envelope is 10000 RPM with existing recipe-specific root mapping, not every API input.',
            'Full harmonic counts and all anchor texture states retained; no bank RNG sharing credited.',
            'Endpoint accumulator starts below one, without pre-existing backlog; initialization/warmup is non-RT.',
            'ceil(events/frame * frames) bounds only the declared ideal periodic schedules, not floating-point timing or target WCET.',
            'Endpoint projection/RNG terms are treated wholly as burst work, conservatively retaining their old cost allowance.',
            'Fine-FIR products/FFTs use the actual 256-sample internal block; remaining mix/reserves stay inherited.',
            'Controller/event/covariance bursts, finite-precision scheduling, cache/DMA stalls and switching costs are not bounded.',
            'The research reference retains the V7 single-anchor hypothetical native48k cost model; subsequent lifts were rejected.',
            'No full spatial IR/HRTF/BRIR, multiple vehicles or other product workloads included.',
            'No PC timings converted to SHARC cycles; no target compiler or board measurements asserted.',
        ],
        no_runtime_C_model_driver_hearing_change=True,
        next='CCES optimized kernels with numeric/hearing checks, memory placement, then longest-block board counters')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                   allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(verified_V7_input_count=result['verified_V7_input_count'],
                          largest_by_block=largest,
                          conditional_research_reference_MCPS=candidate['sum_MCPS']), indent=2))


if __name__ == '__main__':
    main()
