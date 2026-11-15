"""Independent direct local basis, full wave and supported FFT of saved null witness."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'full', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', maximum_errors={})

    def check(name, x, y, gate=2e-9):
        x, y = np.asarray(x), np.asarray(y)
        err = float(np.max(abs(x-y)))
        assert x.shape == y.shape and err < gate, (name, err)
        r['maximum_errors'][name] = err

    try:
        report = load(a.study/'report.json')
        assert report['result'] == 'observer_supported_data_null_diagnosed'
        assert sha(a.study/'witness.npz') == report['witness_sha256']
        for name, digest in report['inputs'].items():
            assert sha(name) == digest
        with np.load(a.study/'witness.npz') as z, np.load(a.full/'capture.npz') as f:
            center = 24
            n = np.arange(5889, 6400)
            h = np.arange(1, 289)
            angle = 2*np.pi*((n[:, None]*h[None]) % 1024)/1024
            basis = np.column_stack((np.cos(angle)*f['scale'][:, 0], -np.sin(angle)*f['scale'][:, 0]))
            basis *= (1-abs(n-6144)/256)[:, None]
            check('local_carrier_basis', basis, z['local'])
            check('orthonormal65null_basis', z['null_basis'].T@z['null_basis'], np.eye(65))
            check('all65null_waves', basis@z['null_basis'], np.zeros((511, 65)))
            check('unit_direction', np.linalg.norm(z['direction']), 1.)
            check('direction_in_null_span', z['null_basis']@(z['null_basis'].T@z['direction']), z['direction'])
            nodes = z['direction_nodes']
            assert not np.any(nodes[:center]) and not np.any(nodes[center+1:]) and not np.any(nodes[:, :, 1])
            check('local_direction_nodes', nodes[center, :, 0], z['direction'][:288]+1j*z['direction'][288:])
            wave = np.zeros((12289, 2))
            wave[n, 0] = basis@z['direction']
            check('full_witness_wave', wave, z['wave'])
            D = np.zeros((47, 49))
            for j in range(47):
                D[j, j:j+3] = [1., -2., 1.]
            q = f['fitted']/f['scale'][None]
            gradient = (.001*D.T@D + 1e-6*np.eye(49))@q.reshape(49, -1)
            local = gradient.reshape(q.shape)[24, :, 0]
            local = np.r_[local.real, local.imag]
            check('local_penalty_gradient', local, z['local_regularizer_gradient'])
            derivative = float(2*local@z['direction'])
            check('negative_penalty_derivative', derivative, report['saved_fit_penalty_directional_derivative'])
            assert derivative < 0
            window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
            one_side = np.r_[1., np.full(2047, np.sqrt(2.)), 1.]
            def rows(audio):
                return np.array([np.fft.rfft(audio[s:s+4096]*window[:, None], axis=0)
                    for s in range(0, 8193, 256)])*one_side[None, :, None]/(64*np.sqrt(6.))*np.sqrt(12289/(256*33))
            reference = rows(f['audio'])
            bands = np.searchsorted([3000, 6000, 8000, 10000, 14000], np.arange(2049)*16, side='right')
            power = np.array([np.sum(abs(reference[:, bands==b])**2)/f['audio'].size for b in range(6)])
            global_power = float(np.mean(f['audio']**2))
            weights = 1/np.sqrt(np.maximum(power[bands], global_power*1e-8))
            check('independent_fullcase_weights', weights/f['weights'], np.ones(2049))
            # Roundoff differs across dot-product and scalar OSC summation paths;
            # independently bound both witnesses, do not compare their tiny norms relatively.
            data_norm = float(np.sqrt(np.sum(wave**2)/global_power + np.sum(abs(rows(wave)*weights[None, :, None])**2)))
            assert data_norm < 2e-8 and report['witness_weighted_data_norm'] < 2e-8
            assert (report['normalized_real_unknowns'], report['waveform_data_rank_upper_bound'],
                report['data_null_dimension_lower_bound']) == (56448, 24578, 31870)
            r.update(result='independent_observer_supported_null_passed',
                independent_witness_data_norm=data_norm, penalty_directional_derivative=derivative,
                producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__),
                no_fit_or_correction=True, physical_source_or_sole_failure_cause_not_claimed=True)
        save(a.out/'report.json', r)
        print(r['result'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
