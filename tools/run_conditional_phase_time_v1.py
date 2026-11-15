"""Known controls, frozen maps and paired waveforms through the original observer."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--stage', choices=['known', 'real'], required=True)
    parser.add_argument('--known', type=Path)
    parser.add_argument('--known-audit', type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from conditional_phase_time_v1.fixtures import generate as fixture
    from conditional_phase_time_v1.generator import generate
    from conditional_phase_time_v1.mapping import decode
    from conditional_phase_time_v1.observer import analyze, summary, power_statistics
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', stage=args.stage, sources={}, inputs={}, cases=[])
    try:
        names = ['research/conditional_phase_time_v1_plan.json', 'tools/run_conditional_phase_time_v1.py',
                 'tools/conditional_phase_time_v1/mapping.py', 'tools/conditional_phase_time_v1/observer.py',
                 'tools/conditional_phase_time_v1/fixtures.py', 'tools/conditional_phase_time_v1/generator.py',
                 'tools/radial_copula_v1/latent.py', 'tools/radial_copula_v1/quantiles.py',
                 'tools/sound_dna/windowed.py', 'tools/sound_dna/statistics.py']
        for name in names:
            path = args.out/'exact_sources'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, path)
            report['sources'][name] = sha(path)
        plan = load(repo/names[0])
        bands = plan['bands_Hz']
        gate = plan['checks']
        def consume(path):
            report['inputs'][str(path)] = sha(path)
            return path
        if args.stage == 'known':
            for kind in plan['known']:
                audio, metadata = fixture(kind)
                observed = analyze(audio, 288, 64., bands)
                path = args.out/(kind+'.npz')
                np.savez_compressed(path, audio=audio, **metadata, **observed)
                report['cases'].append(dict(label=kind, sha256=sha(path), observed_rows=len(observed['coefficients']),
                                            statistics=summary(observed)))
            knots = np.array([.5, 1.5])
            low = np.array([-1., -1., -.2, .4, 1.2])
            high = np.array([-1., -.2, .4, 1.2, 1.2])
            cdf = np.array([[0., .1, .4, .65, .9, 1.], [0., .15, .35, .6, .85, 1.]])
            product = np.array([0., .5, .7, 1., 1.5, 2., .6, 1.2])
            uniform = np.array([0., .1, .3, .5, .8, np.nextafter(1., 0.), .999999, .000001])
            path = args.out/'mapping.npz'
            np.savez_compressed(path, knots=knots, low=low, high=high, cdf=cdf, product=product,
                                uniform=uniform, phase=decode(product, uniform, knots, cdf, low, high))
            report['mapping_sha256'] = sha(path)
            report['result'] = 'conditional_time_known_controls_ready'
        else:
            known = load(consume(args.known/'report.json'))
            audit = load(consume(args.known_audit/'report.json'))
            assert known['result'] == 'conditional_time_known_controls_ready'
            assert audit['result'] == 'independent_conditional_time_known_audit_passed'
            assert audit['producer_sha256'] == sha(args.known/'report.json')
            assert known['sources'] == report['sources']
            roots = {}
            entries = {}
            for stage in ('conditional_phase_slope_v1', 'relative_phase_v1', 'coefficient_geometry_v1'):
                roots[stage] = args.workspace/'baselines'/stage
                path = consume(roots[stage]/'manifest.json')
                assert sha(path) == load(repo/f'research/{stage}_summary.json')['manifest_sha256']
                entries[stage] = {v['path']:v['sha256'] for v in load(path)['files']}
            def frozen(stage, name):
                path = consume(roots[stage]/name)
                assert sha(path) == entries[stage][name]
                return path
            phase_report = load(frozen('relative_phase_v1', 'evidence/real1/report.json'))
            slope_report = load(frozen('conditional_phase_slope_v1', 'evidence/real5/report.json'))
            slope_rows = {r['label']:r for r in slope_report['cases']}
            for prior in phase_report['cases']:
                label = prior['label']
                root = prior['root_hz']
                folder = args.out/label
                folder.mkdir()
                with np.load(frozen('relative_phase_v1', f'evidence/real1/{label}/profile.npz')) as raw:
                    model = {k:raw[k] for k in raw.files}
                with np.load(frozen('relative_phase_v1', f'evidence/real1/{label}/training.npz')) as training:
                    source_rows = training['source_rows'].copy()
                with np.load(frozen('coefficient_geometry_v1', f'evidence/real1/{label}/source.npz')) as source:
                    source_audio = source['rebuilt'].copy()
                observed = analyze(source_audio, 288, root, bands)
                q = source_rows.reshape(-1, 288, 2, 2)
                source_error = float(abs(observed['coefficients']-(q[..., 0]+1j*q[..., 1])).max())
                assert source_error < gate['source_rows_FS']
                np.savez_compressed(folder/'source.npz', audio=source_audio, source_rows=source_rows, **observed)
                maps = {name:[] for name in ('knots', 'low', 'high', 'parent', 'density', 'variation')}
                mean_product = []
                maximum_probe_error = 0.
                for h, harmonic in enumerate(slope_rows[label]['harmonics']):
                    path = frozen('conditional_phase_slope_v1', f'evidence/real5/{label}/{h+1:03d}/model.npz')
                    assert sha(path) == harmonic['sha256']
                    with np.load(path) as table:
                        for name in ('knots', 'low', 'high'):
                            maps[name].append(table[name].copy())
                        for stage in ('parent', 'density', 'variation'):
                            cdf = table[stage+'_cdf']
                            actual = decode(table[stage+'_probe_product'], table[stage+'_probe_uniform'],
                                            table['knots'], cdf, table['low'], table['high'])
                            error = float(abs(actual-table[stage+'_probe_phase']).max())
                            assert error < gate['saved_map_probe_radians']
                            maximum_probe_error = max(maximum_probe_error, error)
                            maps[stage].append(cdf.copy())
                    mean_product.append(harmonic['mean_product'])
                maps = {k:np.array(v) for k, v in maps.items()}
                maps['mean_product'] = np.array(mean_product)
                bundle = folder/'bundle.npz'
                np.savez_compressed(bundle, **maps, **{'model_'+k:v for k, v in model.items()})
                row = dict(label=label, root_hz=root, source_rows=len(q), source_rows_maximum_error_FS=source_error,
                           source_sha256=sha(folder/'source.npz'), bundle_sha256=sha(bundle),
                           maximum_saved_map_probe_error_radians=maximum_probe_error,
                           source_statistics=summary(observed), seeds=[])
                for seed in plan['seeds']:
                    capture = generate(model, maps, root, bands, plan['cycles'], seed, plan['block'])
                    seed_row = dict(seed=seed, variants={})
                    if not report['cases'] and seed == plan['seeds'][0]:
                        paired = generate(model, maps, root, bands, plan['cycles'], seed, plan['identity_block'])
                        errors = {key:float(abs(capture[key+'_audio']-paired[key+'_audio']).max()) for key in plan['variants']}
                        assert max(errors.values()) < gate['chunk_identity_FS']
                        seed_row['chunk_identity_maximum_errors_FS'] = errors
                    for key in plan['variants']:
                        value = analyze(capture[key+'_audio'], 288, root, bands)
                        capture.update({key+'_'+k:v for k, v in value.items()})
                        chunks = []
                        for start in range(0, len(value['power'])-len(q)+1, len(q)):
                            end = start+len(q)
                            line = power_statistics(value['power'][start:end], value['cross'][start:end])
                            broad = power_statistics(value['broadband_power'][start:end], value['broadband_cross'][start:end])
                            chunks.append({prefix+'_'+name:stats[name] for prefix, stats in [('line', line), ('broad', broad)]
                                           for name in ('mean', 'CV', 'complex_coherence')})
                        for name in chunks[0]:
                            capture[key+'_chunks_'+name] = np.stack([c[name] for c in chunks])
                        seed_row['variants'][key] = summary(value)
                    path = folder/f'probe_{seed}.npz'
                    np.savez_compressed(path, **capture)
                    seed_row.update(sha256=sha(path), frames=1024*plan['cycles'], observed_rows=len(value['coefficients']),
                                    original_count_chunks=len(chunks), overlapping_apertures_not_independent=True,
                                    outside_P_fraction=capture['outside_P_counts'].sum(axis=1).tolist())
                    # Counts are retained literally; fractions use the explicit frame count.
                    seed_row['outside_P_fraction'] = (capture['outside_P_counts'].sum(axis=1)/(1024*plan['cycles'])).tolist()
                    row['seeds'].append(seed_row)
                    print('GENERATED original-observer five-way probe', label, seed, flush=True)
                report['cases'].append(row)
                save(args.out/'report.json', report)
            report['result'] = 'six_source_conditional_time_probes_ready'
        report['native48k_audio_or_C_adopted'] = False
        save(args.out/'report.json', report)
        print(report['result'], flush=True)
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
