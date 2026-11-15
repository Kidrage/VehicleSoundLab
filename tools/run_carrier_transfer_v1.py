"""Known-first exact carrier partition and signed spectral accounting."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--stage', choices=['known', 'real'], required=True)
    parser.add_argument('--known', type=Path)
    parser.add_argument('--known-audit', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from carrier_transfer_v1.fixtures import generate as fixture
    from carrier_transfer_v1.replay import generate
    from carrier_transfer_v1.spectral import measure, collapse, summary
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', stage=args.stage, sources={}, inputs={}, cases=[])
    try:
        names = ['research/carrier_transfer_v1_plan.json', 'tools/run_carrier_transfer_v1.py',
                 'tools/carrier_transfer_v1/groups.py', 'tools/carrier_transfer_v1/spectral.py',
                 'tools/carrier_transfer_v1/fixtures.py', 'tools/carrier_transfer_v1/replay.py',
                 'tools/conditional_phase_time_v1/mapping.py', 'tools/radial_copula_v1/latent.py',
                 'tools/radial_copula_v1/quantiles.py']
        for name in names:
            path = args.out/'exact_sources'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, path)
            report['sources'][name] = sha(path)
        plan = load(repo/names[0])
        gate = plan['checks']
        def consume(path):
            report['inputs'][str(path)] = sha(path)
            return path
        def assess(audio, root):
            value = measure(audio, root, plan['bands_Hz'])
            scale = max(float(np.diagonal(value['all_frequency_Gram'], axis1=-2, axis2=-1).real.sum(axis=-1).max()), 1e-24)
            error = float(abs(value['all_frequency_Gram'].real-value['time_energy_Gram']).max()/scale)
            assert error < gate['Parseval_scaled'], error
            residuals = {}
            for prefix in ('line', 'broad'):
                matrix = value[prefix+'_Gram']
                assert abs(matrix-matrix.conj().swapaxes(-1, -2)).max()/scale < gate['independent_Gram_scaled']
                minimum = float(np.linalg.eigvalsh(matrix).min())
                assert minimum >= -gate['independent_Gram_scaled']*scale
                stats = summary(matrix)
                residual = float(abs(stats['total_power']-stats['low_power']-stats['rest_power']-stats['signed_low_rest_cross']).max()/scale)
                assert residual < gate['independent_Gram_scaled']
                residuals[prefix] = residual
                value.update({prefix+'_'+name:part for name, part in stats.items()})
            return value, error, residuals
        if args.stage == 'known':
            for label in plan['known']:
                audio, metadata = fixture(label)
                value, parseval, identities = assess(audio, 64.)
                path = args.out/(label+'.npz')
                np.savez_compressed(path, grouped_audio=audio, **metadata, **value)
                report['cases'].append(dict(label=label, sha256=sha(path), Parseval_scaled= parseval,
                                            signed_identity_scaled=identities))
            report['result'] = 'carrier_transfer_known_ready'
        else:
            known = load(consume(args.known/'report.json'))
            audit = load(consume(args.known_audit/'report.json'))
            assert known['result'] == 'carrier_transfer_known_ready'
            assert audit['result'] == 'independent_carrier_transfer_known_passed'
            assert audit['producer_sha256'] == sha(args.known/'report.json')
            assert known['sources'] == report['sources']
            parent = args.workspace/'baselines/conditional_phase_time_v1'
            manifest = consume(parent/'manifest.json')
            assert sha(manifest) == load(repo/'research/conditional_phase_time_v1_summary.json')['manifest_sha256']
            entries = {row['path']:row['sha256'] for row in load(manifest)['files']}
            def frozen(name):
                path = consume(parent/name)
                assert sha(path) == entries[name]
                return path
            old = load(frozen('evidence/real1/report.json'))
            for case in old['cases']:
                label, root = case['label'], case['root_hz']
                folder = args.out/label
                folder.mkdir()
                with np.load(frozen(f'evidence/real1/{label}/bundle.npz')) as raw:
                    bundle = {name:raw[name] for name in raw.files}
                result = dict(label=label, root_hz=root, seeds=[])
                for seed in case['seeds']:
                    with np.load(frozen(f'evidence/real1/{label}/probe_{seed["seed"]}.npz')) as capture:
                        grouped, tags = generate(bundle, capture['state'], capture['independent_state'], root,
                                                 seed['frames'], plan['carrier_edges_Hz'], plan['block'])
                        record = dict(seed=seed['seed'], variants={})
                        for name in plan['variants']:
                            audio = grouped[name]
                            error = float(abs(audio.sum(axis=1)-capture[name+'_audio']).max())
                            assert error < gate['wave_sum_FS'], error
                            value, parseval, identities = assess(audio, root)
                            recoveries = {}
                            for prefix in ('line', 'broad'):
                                matrix = collapse(value[prefix+'_Gram'])
                                power = matrix[:, :, [0, 1], [0, 1]].real.reshape(len(matrix), -1)
                                cross = matrix[:, :, 0, 1]
                                target_power = capture[name+('_power' if prefix == 'line' else '_broadband_power')]
                                target_cross = capture[name+('_cross' if prefix == 'line' else '_broadband_cross')]
                                scale = max(float(abs(target_power).max()), 1e-24)
                                delta = max(float(abs(power-target_power).max()), float(abs(cross-target_cross).max()))/scale
                                assert delta < gate['recovered_parent_scaled'], delta
                                recoveries[prefix] = delta
                            path = folder/f'{name}_{seed["seed"]}.npz'
                            np.savez_compressed(path, grouped_audio=audio, group_tags=tags, **value)
                            record['variants'][name] = dict(file=path.name, sha256=sha(path),
                                parent_wave_sum_error_FS=error, Parseval_scaled=parseval,
                                parent_recovery_scaled=recoveries, signed_identity_scaled=identities)
                    result['seeds'].append(record)
                    print('PARTITIONED exact frozen wave', label, seed['seed'], flush=True)
                report['cases'].append(result)
                save(args.out/'report.json', report)
            report['result'] = 'all90_carrier_partitions_ready'
        report['native_audio_C_driver_or_hearing_adoption'] = False
        save(args.out/'report.json', report)
        print(report['result'], flush=True)
    except BaseException as exc:
        report.update(result='failed', error=repr(exc))
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
