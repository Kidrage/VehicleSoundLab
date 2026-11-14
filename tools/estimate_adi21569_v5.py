"""Extend the hash-bound V4 cost model to both current F3 local triplets.

Cycle costs are optimization assumptions, not measured SHARC+ cycles or WCET.
Only estimate artifacts are written; runtime and model files are read-only.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    hashes = {}

    def read(name):
        raw = (repo / name).read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        return raw.decode('utf-8')

    base = json.loads(read('research/adi21569_estimate_v4_summary.json'))
    changes = {}
    for name, expected in base['input_sha256'].items():
        read(name)
        if hashes[name] != expected:
            changes[name] = dict(previous=expected, current=hashes[name])
    # Current changes to this older inventory are catalog assembly, not DSP.
    # Reject future unreviewed model/hot-path changes instead of reusing costs.
    assert set(changes) <= {'experiments/catalog_drive_v1/models.c'}, changes

    for name in ['modules/dna_atlas/voice.h', 'modules/dna_atlas/bank.c',
                 'modules/dna_atlas/bank.h', 'modules/sound_dna/texture.h',
                 'modules/sound_dna/profile.c',
                 'experiments/catalog_drive_v1/F3_local_models.c',
                 'experiments/catalog_drive_v1/F3_local_models.h',
                 'modules/drive_catalog/catalog.c',
                 'tools/estimate_adi21569_v5.py']:
        read(name)
    index = json.loads(read('voices/F3_fifth_local_v1/index.json'))
    assert len(index['profiles']) == 6
    rate = base['sample_rate']
    old = base['inherited_assumptions']
    root_max = old['bench_RPM_max'] * old['standard_root_per_rpm']
    cycles = dict(
        two_anchor_stereo_harmonic=old['inherited']['stereo_harmonic_two_anchor_cycles'],
        projection_MAC=old['inherited']['texture_MAC_effective_cycles'],
        normal_output_and_state=[12, 30],
        auxiliary_events_basic_stereo_space=[30, 50], controller_mix=[5, 10])

    def cost(count, bounds):
        return [count * value / 1e6 for value in bounds]

    cases = dict(base['cases'])
    inventory = {}
    for group in ['first', 'second']:
        rows = [p for p in index['profiles'] if p['group'] == group]
        assert len(rows) == 3
        profiles = []
        for row in rows:
            t = read(row['path']).split()
            assert hashes[row['path']] == row['sha256']
            assert t[0] == 'VSL_SOUND_DNA' and int(t[2]) == rate
            profile = dict(path=row['path'], harmonics=int(t[5]),
                           components=int(t[6]), base_hz=float(t[7]))
            assert profile['harmonics'] == 288 and profile['components'] == 12
            assert profile['base_hz'] == row['root_hz']
            profiles.append(profile)
        # One bank; at most two neighbors contribute per harmonic, while all
        # three texture states advance. Count independent RNG fallback as well
        # as state work: do not credit ideal batch sharing as a guaranteed gain.
        updates = 4 * root_max
        counts = dict(
            stereo_harmonic_visits_per_second=288 * rate,
            all_three_projection_MAC_per_second=3 * 288 * 4 * (12 + 4) * updates,
            conservative_all_three_normal_state_outputs_per_second=3 * (4 * 288 + 12) * updates)
        terms = dict(
            two_neighbor_DNA=cost(counts['stereo_harmonic_visits_per_second'],
                                  cycles['two_anchor_stereo_harmonic']),
            all_three_texture_projection=cost(counts['all_three_projection_MAC_per_second'],
                                              cycles['projection_MAC']),
            all_three_texture_random_and_state=cost(
                counts['conservative_all_three_normal_state_outputs_per_second'],
                cycles['normal_output_and_state']),
            auxiliary_events_basic_stereo_space=cycles['auxiliary_events_basic_stereo_space'],
            controller_mix=cycles['controller_mix'])
        name = 'F3_fifth_' + group + '_local_triplet'
        cases[name] = dict(terms_MCPS=terms,
                          sum_MCPS=[sum(v[i] for v in terms.values()) for i in range(2)])
        inventory[name] = dict(profiles=profiles, counts=counts,
                               audio_neighbors_max=2, texture_states=3,
                               separate_residual_or_resonant_or_low_layer=False)

    upper = max(item['sum_MCPS'][1] for item in cases.values())
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo,
                                   text=True).strip()
    report = dict(
        schema='vsl.adi21569-cycle-estimate/5', code_basis=head,
        measured=False, guaranteed_WCET=False, optimized_target_port_implemented=False,
        sample_rate=rate, assumed_core_clock_MHz=1000,
        scope='One selected current catalog recipe at a time; stereo; 12 entries are alternatives',
        inherited_hot_path_and_parameter_hashes_exact=True,
        inherited_nonRT_source_changes=changes, input_sha256=hashes,
        assumptions=dict(inherited_from_V4=True, preserves_model_orders=True,
                         root_max_hz=root_max, bench_RPM_max=old['bench_RPM_max'],
                         root_per_rpm_is_engineering_hypothesis=True,
                         full_harmonic_bank_counted=True,
                         no_batch_rng_saving_credited=True,
                         optimized_costs=cycles),
        inventory=inventory, cases=cases,
        largest_estimated_recipe=max(cases, key=lambda name: cases[name]['sum_MCPS'][1]),
        largest_estimated_upper_MCPS=upper,
        rounded_catalog_stereo_planning_upper_MCPS=math.ceil(upper / 100) * 100,
        recommended_algorithm_allocation_MCPS=900,
        basic_12channel_increment_MCPS=base['basic_12channel_increment_MCPS'],
        block_budget=base['block_budget'], exclusions=base['exclusions'],
        qualifications=base['qualifications'] + [
            'New triplets have no separate resonant/residual/low runtime layer.',
            'All three statistical states count, even outside acoustic support.',
            'Paired extreme-rate full-bank and update counts are a planning envelope, not per-block WCET.',
            '12 catalog entries are observation/recipe alternatives, not 12 distinct engines or simultaneous voices.'],
        next=base['next'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                   allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(cases={name: item['sum_MCPS'] for name, item in cases.items()},
                          largest=report['largest_estimated_recipe'],
                          planning_upper_MCPS=report['rounded_catalog_stereo_planning_upper_MCPS'])))


if __name__ == '__main__':
    main()
