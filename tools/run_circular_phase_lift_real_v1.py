"""All frozen sources, one lift rule, original observer and signed spectra."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from circular_phase_lift_v1.replay import generate
    from conditional_phase_time_v1.observer import analyze, summary, power_statistics
    from carrier_transfer_v1.spectral import measure, collapse, summary as gram_summary
    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', cases=[], sources={}, inputs={})
    try:
        names = ['research/circular_phase_lift_real_v1_plan.json', 'tools/run_circular_phase_lift_real_v1.py',
                 'tools/circular_phase_lift_v1/lift.py', 'tools/circular_phase_lift_v1/replay.py',
                 'tools/radial_copula_v1/latent.py', 'tools/radial_copula_v1/quantiles.py',
                 'tools/conditional_phase_time_v1/mapping.py', 'tools/conditional_phase_time_v1/observer.py',
                 'tools/sound_dna/windowed.py', 'tools/carrier_transfer_v1/groups.py',
                 'tools/carrier_transfer_v1/spectral.py']
        for name in names:
            dest = args.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            report['sources'][name] = sha(dest)
        plan = load(repo/names[0])
        gate = plan['checks']
        def consume(path):
            report['inputs'][str(path)] = sha(path)
            return path
        root = args.workspace/'baselines/carrier_transfer_v1'
        assert sha(consume(root/'manifest.json')) == load(repo/'research/carrier_transfer_v1_summary.json')['manifest_sha256']
        carrier_entries = {v['path']:v['sha256'] for v in load(root/'manifest.json')['files']}
        known_root = root/'evidence/followup_known/circular_phase_lift_v1'
        known = load(consume(known_root/'known1/report.json'))
        audit = load(consume(known_root/'known_audit1/report.json'))
        assert known['result'] == 'circular_phase_lift_known_ready' and len(known['cases']) == 8
        assert audit['result'] == 'independent_circular_phase_lift_known_passed'
        assert audit['producer_sha256'] == sha(known_root/'known1/report.json')
        for name, digest in known['sources'].items():
            assert sha(repo/name) == digest == sha(consume(known_root/'known1/exact_sources'/name))
        assert sha(known_root/'known1/report.json') == carrier_entries['evidence/followup_known/circular_phase_lift_v1/known1/report.json']
        assert sha(known_root/'known_audit1/report.json') == carrier_entries['evidence/followup_known/circular_phase_lift_v1/known_audit1/report.json']
        parent = args.workspace/'baselines/conditional_phase_time_v1'
        assert sha(consume(parent/'manifest.json')) == load(repo/'research/conditional_phase_time_v1_summary.json')['manifest_sha256']
        entries = {v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
        def frozen(name):
            path = consume(parent/name)
            assert sha(path) == entries[name]
            return path
        old = load(frozen('evidence/real1/report.json'))
        for case in old['cases']:
            label, frequency = case['label'], case['root_hz']
            folder = args.out/label
            folder.mkdir()
            with np.load(frozen(f'evidence/real1/{label}/bundle.npz')) as raw:
                bundle = {name:raw[name] for name in raw.files}
            frozen(f'evidence/real1/{label}/source.npz')
            row = dict(label=label, root_hz=frequency, source_rows=case['source_rows'], seeds=[])
            for seed in case['seeds']:
                with np.load(frozen(f'evidence/real1/{label}/probe_{seed["seed"]}.npz')) as raw:
                    capture = {name:raw[name] for name in ('state','independent_state','probe_positions')}
                    capture.update({name+'_audio':raw[name+'_audio'] for name in plan['variants']})
                grouped, diagnostics, replay_errors, partition_errors = generate(bundle, capture, frequency, plan['carrier_edges_Hz'], plan['block'])
                assert max(replay_errors.values()) < gate['original_wave_FS']
                assert max(partition_errors.values()) < gate['original_wave_FS']
                seed_row = dict(seed=seed['seed'], variants={}, replay_errors_FS=replay_errors,
                                partition_errors_FS=partition_errors)
                if not report['cases'] and seed['seed'] == plan['seeds'][0]:
                    paired, _, _, _ = generate(bundle, capture, frequency, plan['carrier_edges_Hz'], plan['identity_block'])
                    errors = {name:float(abs(grouped[name]-paired[name]).max()) for name in plan['variants']}
                    assert max(errors.values()) < gate['chunk_identity_FS']
                    seed_row['chunk_errors_FS'] = errors
                    del paired
                for name in plan['variants']:
                    group = grouped[name]
                    audio = group.sum(axis=1)
                    observed = analyze(audio, 288, frequency, plan['bands_Hz'])
                    spectral = measure(group, frequency, plan['bands_Hz'])
                    values = dict(audio=audio, grouped_audio=group, **observed, **spectral)
                    for prefix in ('line', 'broad'):
                        matrix = collapse(spectral[prefix+'_Gram'])
                        power = matrix[:, :, [0,1], [0,1]].real.reshape(241, 8)
                        expected = observed['power' if prefix == 'line' else 'broadband_power']
                        scale = np.maximum(expected.reshape(241, 4, 2).mean(axis=(0,2)),1e-24)
                        assert (abs(power-expected).reshape(241,4,2)/scale[None,:,None]).max() < gate['Gram_per_band_scaled']
                        values.update({prefix+'_group_'+key:value for key,value in gram_summary(spectral[prefix+'_Gram']).items()})
                        chunks = []
                        cross = observed['cross' if prefix == 'line' else 'broadband_cross']
                        for start in range(0,len(power)-case['source_rows']+1,case['source_rows']):
                            chunks.append(power_statistics(expected[start:start+case['source_rows']],cross[start:start+case['source_rows']]))
                        for field in ('mean','CV','complex_coherence'):
                            values['chunks_'+prefix+'_'+field] = np.stack([c[field] for c in chunks])
                    difference = float(abs(audio-capture[name+'_audio']).max())
                    if name != 'fixed':
                        d = diagnostics[name]
                        assert d['maximum_circular_error'] < gate['circular_invariant']
                        assert d['maximum_gauge_wave_error'] < gate['independent_wave_FS']
                        values.update({'lift_'+key:value for key,value in d.items()})
                        if not d['branch_counts'].any():
                            assert difference < gate['original_wave_FS']
                    else:
                        assert difference < gate['original_wave_FS']
                    path = folder/f'{name}_{seed["seed"]}.npz'
                    np.savez_compressed(path, **values)
                    seed_row['variants'][name] = dict(file=path.name, sha256=sha(path),
                        observed_rows=len(observed['power']), statistics=summary(observed),
                        maximum_wave_change_FS=difference,
                        branch_increments=int(diagnostics[name]['branch_counts'].sum()) if name != 'fixed' else 0)
                row['seeds'].append(seed_row)
                print('LIFTED frozen phase paths',label,seed['seed'],flush=True)
            report['cases'].append(row)
            save(args.out/'report.json', report)
        assert len(report['cases']) == 6
        report.update(result='all90_frozen_phase_lift_candidates_ready', native48k_or_C_or_listening=False,
                      no_new_random_draws=True, normalized_coordinate_only=True)
        save(args.out/'report.json', report)
        print(report['result'],flush=True)
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
