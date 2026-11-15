"""Independent finite-tone/Bessel/Hann formulas and scalar conditional CDF."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'out'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.special import jv
    from scipy.signal import stft
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out/'executed_audit.py')
    report = dict(result='running', cases=[], maximum_projection_error_FS=0., maximum_scalar_mapping_error_radians=0.)
    try:
        source = load(args.study/'report.json')
        assert source['result'] == 'conditional_time_known_controls_ready'
        for name, digest in source['sources'].items():
            assert sha(repo/name) == sha(args.study/'exact_sources'/name) == digest
        plan = load(args.study/'exact_sources/research/conditional_phase_time_v1_plan.json')
        def kernel(turn):
            angle = np.remainder(turn+.5, 1)-.5
            def geometric(x):
                xx = np.remainder(x+.5, 1)-.5
                return 4096*np.exp(1j*np.pi*4095*xx)*np.sinc(4096*xx)/np.sinc(xx)
            return (.5*geometric(angle)-.25*geometric(angle+1/4096)-.25*geometric(angle-1/4096))/2048
        for row in source['cases']:
            path = args.study/(row['label']+'.npz')
            assert sha(path) == row['sha256']
            with np.load(path) as z:
                audio = z['audio']
                starts = np.arange(0, len(audio)-4096+1, 256)
                observed = z['coefficients']
                expected = np.zeros_like(observed)
                harmonics = np.arange(1, 289)
                for j, order in enumerate(z['orders']):
                    for channel in (0, 1):
                        amplitude = z['amplitudes'][j, channel]*np.exp(1j*z['phases'][j, channel])
                        tones = [(float(order), amplitude)]
                        kind = row['label']
                        sign = 1 if channel == 0 or kind in ('common_AM', 'common_PM') else -1
                        if j == 1 and kind in ('common_AM', 'differential_AM'):
                            tones += [(order-1/7, amplitude*sign*.15), (order+1/7, amplitude*sign*.15)]
                        if j == 1 and kind in ('common_PM', 'relative_PM'):
                            tones = [(order+m/7, amplitude*jv(m, sign*.4)) for m in range(-12, 13)]
                        if j == 1 and kind == 'sideband':
                            tones += [(64+1/7, .013*np.exp(.3j))] if channel == 0 else [(64-1/7, .017*np.exp(-.2j))]
                        if kind == 'silence':
                            tones = []
                        for frequency, coefficient in tones:
                            positive = (frequency-harmonics)/1024
                            negative = (-frequency-harmonics)/1024
                            expected[..., channel] += coefficient*np.exp(2j*np.pi*np.remainder(starts[:, None]*positive, 1))*kernel(positive)
                            expected[..., channel] += coefficient.conjugate()*np.exp(2j*np.pi*np.remainder(starts[:, None]*negative, 1))*kernel(negative)
                error = float(abs(observed-expected).max())
                assert error < plan['checks']['known_projection_FS'], (row['label'], error)
                # A separate STFT path covers all saved projection rows, both channels.
                frequency, _, independent = stft(audio.T, fs=65536, window='hann', nperseg=4096,
                    noverlap=3840, boundary=None, padded=False)
                value = np.moveaxis(independent[:, 4*harmonics, :], (0, 1, 2), (2, 1, 0))*2
                value *= np.exp(-2j*np.pi*np.remainder(starts[:, None]*harmonics/1024, 1))[..., None]
                assert abs(value-observed).max() < plan['checks']['known_projection_FS']
                # STFT uses sum(window) normalization. A periodic Hann has
                # sum=N/2, energy=3N/8, so integrated real one-sided power is
                # 4/3*|STFT|^2 (2/3 only at DC/Nyquist).
                scale = np.full(len(frequency), 4/3)
                scale[[0, -1]] = 2/3
                broadband = []
                cross = []
                for lo, hi in plan['bands_Hz']:
                    mask = (frequency >= lo)&(frequency < hi)
                    broadband.append(np.sum(abs(independent[:, mask])**2*scale[mask, None], axis=1).T)
                    cross.append(np.sum(independent[0, mask]*independent[1, mask].conj()*scale[mask, None], axis=0))
                broadband = np.concatenate(broadband, axis=1)
                cross = np.stack(cross, axis=1)
                denominator = max(float(abs(broadband).max()), 1e-30)
                assert abs(broadband-z['broadband_power']).max()/denominator < plan['checks']['independent_stats_relative']
                assert abs(cross-z['broadband_cross']).max()/denominator < plan['checks']['independent_stats_relative']
                report['maximum_projection_error_FS'] = max(report['maximum_projection_error_FS'], error)
                if row['label'] == 'silence':
                    assert not audio.any() and not observed.any()
                    assert not z['line_power_defined'].any() and not z['line_coherence_defined'].any()
                report['cases'].append(dict(label=row['label'],rows=len(observed),maximum_projection_error_FS=error))
        assert sha(args.study/'mapping.npz') == source['mapping_sha256']
        with np.load(args.study/'mapping.npz') as z:
            output = []
            for product, uniform in zip(z['product'], z['uniform']):
                cumulative = [float(np.interp(product, z['knots'], z['cdf'][:, j])) for j in range(z['cdf'].shape[1])]
                cell = min(next((j for j in range(len(z['low'])) if uniform < cumulative[j+1]), len(z['low'])-1), len(z['low'])-1)
                u = (uniform-cumulative[cell])/(cumulative[cell+1]-cumulative[cell])
                output.append(z['low'][cell]+u*(z['high'][cell]-z['low'][cell]))
            error = float(abs(np.array(output)-z['phase']).max())
            assert error < 2e-12
            report['maximum_scalar_mapping_error_radians'] = error
        report.update(result='independent_conditional_time_known_audit_passed',
                      producer_sha256=sha(args.study/'report.json'), auditor_sha256=sha(__file__))
        save(args.out/'report.json', report)
        print(report['result'])
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
