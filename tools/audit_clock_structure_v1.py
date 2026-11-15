"""Independent clock diagnosis; imports no new producer geometry/fixtures/meter."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from clock_structure_v1.audit import geometry, observed, interpolate
    from locked_source_tail_v1.audit_kernel import analytic
    from locked_source_tail_v1.audit_measure import verify as verify_spectra
    from locked_source_diagnostics_v1.native_identity import verify
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', inputs={})
    try:
        info = load(a.study/'report.json'); mode = info['mode']
        assert info['result'] == 'clock_structure_'+mode+'_measured'
        for name, expected in info['sources'].items():
            assert sha(repo/name) == sha(a.study/'exact_sources'/name) == expected
        for name, expected in info['inputs'].items():
            assert sha(name) == expected
        shutil.copytree(a.study/'exact_sources', a.out/'exact_sources')
        r.update(producer_sha256=sha(a.study/'report.json'), capture_sha256=sha(a.study/'capture.npz'))
        assert r['capture_sha256'] == info['capture_sha256']
        with np.load(a.study/'capture.npz') as f:
            saved = {key: f[key] for key in f.files}
        if mode == 'known':
            nodes = np.array([1024.25, 4096.5, 8192.125, 12288.75, 16384.3])
            jumps = np.array([1e-8, -6e-9, 4e-9, -7e-9, 3e-9])
            assert np.array_equal(nodes, saved['nodes']) and np.array_equal(jumps, saved['prescribed_jumps'])
            cases = []
            for case in info['known']['cases']:
                name = case['name']; prefix = name+'__'
                data = {key[len(prefix):]: value for key, value in saved.items() if key.startswith(prefix)}
                cases.append(dict(name=name, **geometry(data, case)))
                if name == 'smooth_PL':
                    continue
                u, x = data['query'], data['graph_x']
                origin = 160.36 if name.endswith('large_origin') else .36
                y = origin+x/65536
                expected = origin+u/65536
                if name.startswith('C0'):
                    for node, jump in zip(nodes, jumps):
                        y += jump*np.maximum(x-node, 0)
                        expected += jump*np.maximum(u-node, 0)
                    assert np.array_equal(data['graph_special'], np.isin(x, nodes))
                assert np.max(abs(y-data['graph_y'])) < 2e-12
                assert np.max(abs(expected-data['graph'])) < 2e-12
            r['known_geometry'] = cases
            clocks = {key[7:]: value for key, value in saved.items() if key.startswith('clock__')}
            u = saved['C0__query']; smooth = .36+u/65536
            for node, jump in zip(nodes, jumps):
                d = u-node; smooth += jump*(d+np.sqrt(d*d+256**2))/2
            target = clocks['manufactured_C0']
            smooth += (target[0]-smooth[0])+(u-u[0])/(u[-1]-u[0])*((target[-1]-smooth[-1])-(target[0]-smooth[0]))
            assert np.max(abs(smooth-clocks['exact_smooth'])) < 2e-12
            assert np.array_equal(clocks['sampled_smooth_PL'], saved['smooth_PL__graph'])
            values = {key[8:]: value for key, value in saved.items() if key.startswith('signal__')}
            coeff, freq, taps = saved['coefficients'], saved['frequencies'], saved['taps']
            scale = float(np.sum(abs(coeff)))
            for name, seconds in clocks.items():
                expected = analytic(seconds, freq, coeff, taps)
                assert np.max(abs(expected-values[name]))/scale < 2e-12
            assert np.array_equal(saved['mono'][:, 0], saved['mono'][:, 1]) and not np.count_nonzero(saved['zero'])
            assert np.max(abs(saved['weak']-values['affine']*1e-6)) < 2e-12
            assert info['known']['rejections'] == ['nonfinite', 'complex', 'nonmonotone_x', 'nonmonotone_y', 'unsupported', 'nonunit_query', 'invalid_mask']
            r['spectra'] = verify_spectra(values, saved, info['observations'], saved['weights'], float(saved['amplitude']))
            assert info['known']['all_known_qualified']
        else:
            tail = Path(info['tail_study']); previous = load(tail/'real1/report.json')
            source_study = Path(previous['source_study']); source = load(source_study/'report.json')
            z, _ = verify(source, source_study, repo, r['inputs'])
            cr = load(Path(info['context_study'])/'report.json')
            ca = load(Path(info['context_audit'])/'report.json')
            assert ca['all_qualified'] and ca['producer_sha256'] == sha(Path(info['context_study'])/'report.json')
            row = next(c for c in cr['cases'] if c['label'] == info['label'])
            assert sha(info['context_file']) == row['sha256']
            with np.load(info['context_file']) as f:
                context = {key: f[key] for key in f.files}
            assert np.array_equal(context['positions'], z['source_coordinates'])
            assert np.array_equal(saved['actual'], context['positions'])
            assert np.array_equal(saved['query'], context['sample_indices'])
            assert np.array_equal(saved['graph_x'], context['observed_phase']*1024)
            assert np.array_equal(saved['graph_y'], context['coarse_positions'][(context['observed_indices']-context['coarse_indices'][0]).astype(int)])
            assert np.array_equal(saved['graph_special'], np.isin(context['observed_indices'], context['observed_centers']))
            r['independent_observation_reconstruction'] = observed(context)
            r['geometry'] = geometry(saved, info['geometry'])
            assert not info['original_source_fidelity_qualified'] and not info['eligible_for_later_source_statistics']
            assert info['old_source_highest_NRMSE'] > .02
            ka = load(Path(info['known_audit'])/'report.json')
            assert ka['verification_passed'] and ka['producer_sha256'] == sha(Path(info['known_study'])/'report.json')
        r.update(result='independent_clock_structure_'+mode+'_verified', verification_passed=True,
            no_new_producer_algorithm_imports=True, no_actual_target_clock_or_gate_change=True,
            no_source_naturalness_or_sustained_C_qualification=True)
        save(a.out/'report.json', r)
        print('INDEPENDENT_CLOCK_STRUCTURE_COMPLETE', mode, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
