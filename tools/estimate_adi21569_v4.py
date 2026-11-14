"""Current catalog inventory extension. Assumed optimized cycles, NOT target WCET.

Retain V3 coefficients and alternatives; explicitly inventory E/F3 stereo VAR
recipes now present in the catalog. Does not modify runtime/model/audio files.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
inputs = {}


def read(name):
    raw = (repo / name).read_bytes()
    inputs[name] = hashlib.sha256(raw).hexdigest()
    return raw.decode('utf-8')


base = json.loads(read('research/adi21569_estimate_v3_summary.json'))
v2 = json.loads(read('research/adi21569_estimate_v2_summary.json'))
# Preserve all old inventory assumptions only if its parameter bytes still match.
for name, expected in base['input_sha256'].items():
    read(name)
    if name.startswith(('voices/', 'experiments/spectral_texture_v1/')):
        assert inputs[name] == expected, name


def dna(name):
    t = read(name).split()
    assert t[0] == 'VSL_SOUND_DNA' and int(t[2]) == 48000
    return dict(harmonics=int(t[5]), components=int(t[6]), base_hz=float(t[7]))


def stereo(name):
    t = iter(read(name).split())
    assert next(t) == 'VSL_STEREO_RESONANCE' and int(next(t)) == 1
    rate, count, warmup = [int(next(t)) for _ in range(3)]
    root = float(next(t))
    rows = []
    for _ in range(count):
        order, sections = int(next(t)), int(next(t))
        low, high, gain = [float(next(t)) for _ in range(3)]
        # VAR 2x2 taps, innovation 2x2, stereo-shared SOS, Lyapunov certificate.
        for _ in range(4 * order + 4 + 6 * sections + (2 * order)**2):
            float(next(t))
        rows.append(dict(order=order, sections_per_channel=sections,
                         low_hz=low, high_hz=high, gain=gain))
    assert next(t, None) is None and rate == 48000
    return dict(rate=rate, bands=rows, warmup_nonRT_frames=warmup, base_hz=root)


def cost(count, bounds):
    return [count * x / 1e6 for x in bounds]


rate = base['sample_rate']
root_max = base['assumptions']['bench_RPM_max'] * base['assumptions']['standard_root_per_rpm']
assumed = dict(
    stereo_harmonic_cycles=v2['assumptions']['stereo_harmonic_single_anchor_cycles'],
    texture_MAC_cycles=v2['assumptions']['texture_MAC_effective_cycles'],
    filter_MAC_cycles=v2['assumptions']['scalar_filter_MAC_effective_cycles'],
    gaussian_and_state_cycles_per_output=[12, 30],
    detail_support_shape_mix_MCPS=[8, 16],
    auxiliary_events_basic_stereo_space_MCPS=[30, 50], controller_mix_MCPS=[5, 10])
cases = dict(base['cases'])
inventory = {}
for name, stem in [('E_decel_stereo', 'voices/E_decel_source_v1/E slowing cabin'),
                   ('F3_additive_stereo', 'voices/F3_before_upshift_v1/F3 before upshift')]:
    main = dna(stem + '.model')
    detail = stereo(stem + '.sres')
    assert main['harmonics'] == 288 and main['components'] == 12
    assert len(detail['bands']) == (10 if name.startswith('F3') else 8)
    assert all(b['order'] == 24 and b['sections_per_channel'] == 4 for b in detail['bands'])
    updates = 4 * root_max
    n = len(detail['bands'])
    counts = dict(
        full_bank_stereo_harmonic_visits_per_s=main['harmonics'] * rate,
        texture_projection_MAC_per_s=main['harmonics'] * 4 * (main['components'] + 4) * updates,
        texture_normal_state_outputs_per_s=(4 * main['harmonics'] + main['components']) * updates,
        VAR_MAC_per_s=sum(4 * b['order'] for b in detail['bands']) * rate,
        innovation_matrix_MAC_per_s=4 * n * rate,
        stereo_SOS_MAC_per_s=sum(2 * 5 * b['sections_per_channel'] for b in detail['bands']) * rate,
        detail_normal_outputs_per_s=2 * n * rate)
    rows = dict(
        single_anchor_DNA=cost(counts['full_bank_stereo_harmonic_visits_per_s'], assumed['stereo_harmonic_cycles']),
        texture_projection=cost(counts['texture_projection_MAC_per_s'], assumed['texture_MAC_cycles']),
        texture_random_and_state=cost(counts['texture_normal_state_outputs_per_s'], assumed['gaussian_and_state_cycles_per_output']),
        stereo_VAR_innovation_SOS=cost(sum(counts[k] for k in ['VAR_MAC_per_s', 'innovation_matrix_MAC_per_s', 'stereo_SOS_MAC_per_s']), assumed['filter_MAC_cycles']),
        detail_excitation=cost(counts['detail_normal_outputs_per_s'], assumed['gaussian_and_state_cycles_per_output']),
        detail_support_shape_mix=assumed['detail_support_shape_mix_MCPS'],
        auxiliary_events_basic_stereo_space=assumed['auxiliary_events_basic_stereo_space_MCPS'],
        controller_mix=assumed['controller_mix_MCPS'])
    cases[name] = dict(terms_MCPS=rows, sum_MCPS=[sum(r[i] for r in rows.values()) for i in range(2)])
    inventory[name] = dict(dna=main, detail=detail, operation_counts=counts)

for name in ['experiments/catalog_drive_v1/F3_models.c',
             'experiments/catalog_drive_v1/decel_models.c',
             'modules/stereo_resonance/voice.c', 'modules/resonant_detail/excitation.c',
             'modules/resonant_detail/filter.c', 'modules/drive_resonance/voice.c',
             'modules/drive_recipe/voice.c', 'modules/drive_recipe/shape.c',
             'modules/drive_recipe/bank.c', 'modules/atlas_drive/render.c',
             'modules/sound_dna/oscillator.c']:
    read(name)

upper = max(v['sum_MCPS'][1] for v in cases.values())
report = dict(
    schema='vsl.adi21569-cycle-estimate/4', code_basis='0246402',
    measured=False, guaranteed_WCET=False, optimized_port_implemented=False,
    sample_rate=rate, assumed_core_clock_MHz=1000,
    scope='One current catalog recipe at a time; stereo; ten entries are alternatives',
    inherited_V3_inventory_parameters_exact=True,
    inherited_source_changes={k: dict(old=h, current=inputs[k]) for k, h in base['input_sha256'].items() if inputs[k] != h},
    input_sha256=inputs, inherited_assumptions=base['assumptions'],
    added_stereo_recipe_assumptions=assumed, inventory=inventory, cases=cases,
    largest_estimated_recipe=max(cases, key=lambda k: cases[k]['sum_MCPS'][1]),
    largest_estimated_upper_MCPS=upper,
    rounded_catalog_stereo_planning_upper_MCPS=math.ceil(upper / 100) * 100,
    recommended_algorithm_allocation_MCPS=900,
    basic_12channel_increment_MCPS=base['basic_12channel_increment_MCPS'],
    block_budget=dict(frames=240, seconds=240/rate, core_cycles_at_assumed_clock=5_000_000,
                      cycles_at_800_MCPS=4_000_000, cycles_at_900_MCPS=4_500_000),
    qualifications=[
        'Same model orders; target FP32/SIMD/block kernels and SRAM/DMA scheduling assumed, not implemented.',
        'MAC counts are not MCPS; coefficients include assumed scheduling/loading cost, not measured instructions.',
        'No per-callback worst-case guarantee: FFT/statistical bursts must be measured and scheduled.',
        'All model banks continue where current runtime does; no silent gate or unqualified order reduction credited.',
        'Warmup/certificate/model IO are non-RT; no new timbre acceptance or target numeric equivalence implied.'],
    exclusions=base['exclusions'], risks=base['risks'],
    next='CCES optimized target port, numeric/listening qualification, then max callback cycles across state/anchor/FFT/cache/DMA scenarios.')
assert report['rounded_catalog_stereo_planning_upper_MCPS'] == 800
args.out.parent.mkdir(parents=True, exist_ok=True)
args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(cases={k: v['sum_MCPS'] for k, v in cases.items()},
                     largest=report['largest_estimated_recipe'],
                     source_changes=list(report['inherited_source_changes']), planning_upper_MCPS=800)))
