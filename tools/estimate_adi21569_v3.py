"""Extend V2 with legacy catalog recipes and the current 10k RPM bench limit.

All cycle coefficients are assumptions, not SHARC measurements or WCET bounds.
No runtime source, model, or audio is modified.
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
base_path = repo / 'research/adi21569_estimate_v2_summary.json'
base = json.loads(base_path.read_text(encoding='utf-8'))
hashes = {}


def read(name):
    path = repo / name
    data = path.read_bytes()
    hashes[name] = hashlib.sha256(data).hexdigest()
    return data.decode('utf-8').split()


# Reuse only the declared costs of V2; verify that its actual parameter inputs
# still match. This is a cost-model extension, not an independent hardware test.
for name, expected in base['input_sha256'].items():
    read(name)
    assert hashes[name] == expected, name


def dna(name):
    t = read(name)
    assert t[0] == 'VSL_SOUND_DNA'
    return dict(harmonics=int(t[5]), components=int(t[6]), base_hz=float(t[7]))


def residual(name):
    t = read(name)
    assert t[0] == 'VSL_SOUND_RESIDUAL'
    return dict(bands=int(t[3]), partials=int(t[4]),
                oscillators=2 * int(t[3]) * int(t[4]))


def cost(count, bounds):
    return [count * x / 1e6 for x in bounds]


def total(rows):
    return [sum(v[i] for v in rows.values()) for i in range(2)]


rate = base['sample_rate']
root_max = 10000 / 120
root_ratio = root_max / base['assumptions']['texture_observation_root_hz']
cases = {}
for name, item in base['cases'].items():
    rows = dict(item['terms_MCPS'])
    # Audio-rate harmonic counts are already conservative full-bank counts.
    # Update only the source-clock-dependent V2 texture allowances here.
    keys = (['five_anchor_texture_projection', 'texture_random_and_state']
            if name.startswith('stationary') else ['DNA_texture'])
    for key in keys:
        rows[key] = [v * root_ratio for v in rows[key]]
    cases[name] = dict(terms_MCPS=rows, sum_MCPS=total(rows))

names = ['A Stationary Low', 'A Stationary Lower Mid',
         'A Stationary Upper Mid', 'A Stationary High']
exterior = [dna('voices/exterior_anchors_v1/' + n + '.model') for n in names]
cabin = [dna('voices/cabin_anchors_v1/' + n + '.model')
         for n in ['E Cabin Lower', 'E Cabin Upper']]
legacy = residual('voices/residual_atlas_v1/A Stationary High.residual')
for n in names:
    assert residual('voices/residual_atlas_v1/' + n + '.residual') == legacy
for n in ['E Cabin Lower', 'E Cabin Upper']:
    assert residual('voices/residual_atlas_v1/' + n + '.residual') == legacy
assert all(m['harmonics'] == 288 and m['components'] == 12 for m in exterior + cabin)
legacy_osc_cycles = [4, 8]

# residual_atlas shares one evolving cloud across the anchors. It is NOT four
# copies of 512 oscillators. Its stereo power/coherence matrix is interpolated.
for name, count in [('legacy_exterior_four', 4), ('legacy_cabin_two', 2)]:
    projection = count * 288 * 4 * (12 + 4) * 4 * root_max
    rows = dict(
        two_anchor_DNA=cost(288 * rate, [20, 34]),
        all_anchor_texture_projection=cost(projection, [.75, 1.25]),
        texture_random_and_state=[9 * count / 5 * root_ratio,
                                  18 * count / 5 * root_ratio],
        residual_OSC_cloud=cost(legacy['oscillators'] * rate, legacy_osc_cycles),
        residual_covariance_and_renormalization=[5, 10],
        auxiliary_events_basic_stereo_space=[30, 50], controller_mix=[5, 10])
    cases[name] = dict(terms_MCPS=rows, sum_MCPS=total(rows))

settle = dna('voices/startup_settle_v1/A start cabin settle.model')
start_residual = residual('voices/startup_detail_v1/A startup settling detail.residual')
settle_root_max = settle['base_hz'] / 850 * 10000
settle_updates = 4 * settle_root_max
projection = settle['harmonics'] * 4 * (settle['components'] + 4) * settle_updates
random_outputs = (4 * settle['harmonics'] + settle['components']) * settle_updates
rows = dict(
    single_anchor_DNA=cost(settle['harmonics'] * rate, [12, 22]),
    texture_projection=cost(projection, [.75, 1.25]),
    texture_random_and_state=cost(random_outputs, [12, 30]),
    residual_OSC_cloud=cost(start_residual['oscillators'] * rate, legacy_osc_cycles),
    residual_covariance_and_renormalization=[5, 10],
    startup_and_catch_layers=[5, 15],
    auxiliary_events_basic_stereo_space=[30, 50], controller_mix=[5, 10])
cases['legacy_start_settle'] = dict(terms_MCPS=rows, sum_MCPS=total(rows))

for name in ['experiments/catalog_drive_v1/models.c',
             'experiments/catalog_drive_v1/decel_models.c',
             'modules/residual_atlas/voice.c', 'modules/sound_residual/oscillator.c',
             'modules/dna_atlas/voice.c', 'modules/sound_dna/texture.c',
             'modules/atlas_drive/control.c', 'src/drive/drive.c', 'src/core/profiles.c']:
    read(name)

upper = max(v['sum_MCPS'][1] for v in cases.values())
report = dict(
    schema='vsl.adi21569-cycle-estimate/3', measured=False, guaranteed_WCET=False,
    code_basis='168a035', sample_rate=rate, assumed_clock_MHz=1000,
    basis_v2_sha256=hashlib.sha256(base_path.read_bytes()).hexdigest(),
    input_sha256=hashes,
    scope='One selected existing recipe at a time, stereo; not all catalog entries summed',
    assumptions=dict(
        inherited=base['assumptions'], bench_RPM_max=10000,
        standard_root_per_rpm=1 / 120,
        legacy_complex_OSC_effective_cycles=legacy_osc_cycles,
        settle_random_state_cycles_per_normal_output=[12, 30],
        legacy_costs_include_expected_SIMD_load_schedule_overhead=True,
        state='No optimized SHARC build, assembly audit, or board counters exist'),
    inventory=dict(legacy_cloud=legacy, startup_cloud=start_residual,
                   startup_DNA=settle, startup_root_max_hz=settle_root_max),
    cases=cases,
    rounded_catalog_stereo_planning_upper_MCPS=math.ceil(upper / 100) * 100,
    recommended_algorithm_allocation_MCPS=900,
    basic_12channel_increment_MCPS=[10, 30],
    coverage_note='Adds missing legacy OSC recipes; nine UI entries are not nine concurrent engines. '
                  'The single-anchor E stereo VAR recipe and two smaller analytic examples do '
                  'not increase these inventory envelopes. This is not exhaustive path WCET.',
    exclusions=base['not_included'], risks=base['risks'],
    next='Target CCES FP32/SIMD port, memory placement and maximum callback cycle measurement; '
         'do not infer SHARC cycles from PC timing or operation counts alone.')
args.out.parent.mkdir(parents=True, exist_ok=True)
args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8', newline='\n')
print(json.dumps({k: v['sum_MCPS'] for k, v in cases.items()}))
