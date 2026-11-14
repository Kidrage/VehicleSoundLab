"""Source inventory plus explicit assumed cycle costs; never an ADI measurement."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
rate = 48000
inputs = {}


def tokens(name):
    path = repo / name
    inputs[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return iter(path.read_text(encoding='utf-8').split())


def take(t, n):
    return [next(t) for _ in range(n)]


def dna(name):
    t = tokens(name)
    head = take(t, 7)
    return dict(tag=head[0], rate=int(head[2]), harmonics=int(head[5]), components=int(head[6]))


def rdetail(name):
    t = tokens(name)
    head = take(t, 6)
    rows = []
    for _ in range(int(head[3])):
        order, sections, envelope = map(int, take(t, 3))
        low, high, sigma, gain, right = map(float, take(t, 5))
        take(t, order + 1 + 6 * sections + 2 * envelope)
        rows.append(dict(order=order, sections=sections, envelope=envelope, hz=[low, high]))
    return rows


def spectral(name):
    t = tokens(name)
    head = take(t, 5)
    rows = []
    for _ in range(int(head[3])):
        count = int(next(t))
        take(t, 2 + count)
        rows.append(dict(taps=count, partitions=(count + 255) // 256))
    return rows


moving = dna('voices/dna_bank_v1/V10 Exterior.model')
low = dna('voices/coherent_low_v1/measured_phase.model')
details = rdetail('voices/resonant_detail_c_v1/moving_35.rdetail')
stationary_names = [
    'voices/exterior_anchors_v1/A Stationary Low.model',
    'voices/exterior_anchors_v1/A Stationary Lower Mid.model',
    'voices/stationary_bridge_v1/A Bridge Mid Two.model',
    'voices/exterior_anchors_v1/A Stationary Upper Mid.model',
    'voices/exterior_anchors_v1/A Stationary High.model']
stationary = [dna(n) for n in stationary_names]
stationary_detail_names = [
    'voices/stationary_recipe_v1/A Stationary Lower Mid.rdetail',
    'voices/stationary_bridge_v1/A Bridge Mid Two.rdetail',
    'voices/stationary_recipe_v1/A Stationary Upper Mid.rdetail',
    'voices/stationary_recipe_v1/A Stationary High.rdetail']
stationary_details = [rdetail(n) for n in stationary_detail_names]
fine = spectral('experiments/spectral_texture_v1/F2_fine_static.sfir')
assert moving['harmonics'] == 300 and low['harmonics'] == 7
assert all(v['harmonics'] == 288 and v['components'] == 12 for v in stationary)
assert all(v['order'] == 24 and v['sections'] == 4 and v['envelope'] == 0
           for bank in stationary_details for v in bank)
assert len(fine) == 6 and all(v['taps'] == 8192 for v in fine)

# These coefficients are ENGINEERING ASSUMPTIONS for an optimized SHARC+
# implementation, including arithmetic, scheduling and loads. They are neither
# instruction-count proofs nor measured compiler/board results.
assumptions = dict(
    precision='FP32 signal/state, sensitive sections separately assessed',
    stereo_harmonic_single_anchor_cycles=[12, 22],
    stereo_harmonic_two_anchor_cycles=[20, 34],
    scalar_filter_MAC_effective_cycles=[.75, 1.4],
    texture_MAC_effective_cycles=[.75, 1.25],
    complex_frequency_MAC_cycles=[2.5, 4.5],
    complex_FFT_butterfly_cycles=[3, 6],
    texture_observation_root_hz=70,
    scope='One selected vehicle recipe; no simultaneous sum of all catalog entries',
    prerequisites=[
        'SIMD/vector block kernels and aligned hot state; no audio-thread allocation/IO',
        'Block/control-rate coefficient preparation with bounded interpolation error',
        'Replace repeated scalar libm and Box-Muller calls with qualified vector/table methods',
        'Real-signal FFT optimization; distributed FFT/texture jobs within audio deadlines',
        'Target SRAM/L2 placement and DMA/cache scheduling validated on the board'],
    preserves_order_counts=True,
    changes_need_error_and_listening_acceptance=True)

counts = dict(
    moving_stereo_harmonic_visits_per_s=moving['harmonics'] * rate,
    stationary_stereo_harmonic_visits_per_s=288 * rate,
    stationary_AR_SOS_MAC_per_s=sum(v['order'] + 5*v['sections']
        for bank in stationary_details for v in bank) * rate,
    stationary_texture_MAC_per_s=5 * 288 * 4 * (12 + 4) * 4 * 70,
    fine_complex_MAC_per_s=sum(v['partitions'] for v in fine) * 512 * rate/256,
    fine_FFT_butterflies_per_s=len(fine) * 2 * (512/2) * 9 * rate/256)


def cost(count, bounds):
    return [count*x/1e6 for x in bounds]


def total(rows):
    return [sum(v[i] for v in rows.values()) for i in range(2)]


moving_cost = dict(
    DNA=cost(counts['moving_stereo_harmonic_visits_per_s'], [12, 22]),
    DNA_texture=[6, 16], coherent_low=[4, 8],
    resonant_detail_and_excitation=[18, 35],
    auxiliary_events_basic_stereo_space=[30, 50], controller_mix=[5, 10])
fine_cost = dict(moving_cost,
    fine_frequency_products=cost(counts['fine_complex_MAC_per_s'], [2.5, 4.5]),
    fine_FFTs=cost(counts['fine_FFT_butterflies_per_s'], [3, 6]),
    idle_13_modes_and_amplitude=[8, 16], fine_block_mix=[2, 4])
stationary_cost = dict(
    DNA=cost(counts['stationary_stereo_harmonic_visits_per_s'], [20, 34]),
    five_anchor_texture_projection=cost(counts['stationary_texture_MAC_per_s'], [.75, 1.25]),
    texture_random_and_state=[9, 18],
    all_32_AR_SOS_filters=cost(counts['stationary_AR_SOS_MAC_per_s'], [.75, 1.4]),
    detail_excitation_and_mix=[8, 16],
    auxiliary_events_basic_stereo_space=[30, 50], controller_mix=[5, 10])
cases = {name: dict(terms_MCPS=rows, sum_MCPS=total(rows)) for name, rows in
         [('moving35', moving_cost), ('moving35_plus_current_fine_idle', fine_cost),
          ('stationary_five_anchors_four_detail_banks', stationary_cost)]}
report = dict(schema='vsl.adi21569-cycle-estimate/2', measured=False,
    code_basis='6125782', sample_rate=rate, assumed_clock_MHz=1000,
    assumptions=assumptions, input_sha256=inputs,
    inventory=dict(moving=moving, low=low, moving_detail=details,
        stationary_DNA=stationary, stationary_detail=stationary_details, fine_idle_FIR=fine),
    operation_counts=counts, cases=cases,
    rounded_stereo_planning_upper_MCPS=700,
    current_basic_12channel_increment_MCPS=[10, 30],
    recommended_algorithm_allocation_MCPS=800,
    guaranteed_WCET=False,
    not_included=['Offline audio/video analysis or fitting', 'PC UI/file/network/research capture',
        'Unimplemented full multichannel IR/HRTF/BRIR', 'Multiple simultaneously running engines',
        'Other vehicle audio products, amplifiers or operating-system workloads'],
    risks=['No CCES binary/disassembly/hardware counter evidence',
        'Cycle coefficients are assumptions, not SHARC instruction guarantees',
        'FP32 precision, approximation error and timbre need target validation',
        'Memory stalls and aligned texture/FFT bursts can exceed average-rate estimates'],
    next='Measure max callback cycles on21569 across states/transitions and cache/DMA conditions; divide cycles by audio block duration. No x86 timing conversion.')
a.out.parent.mkdir(parents=True, exist_ok=True)
a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({name:v['sum_MCPS'] for name,v in cases.items()}))
