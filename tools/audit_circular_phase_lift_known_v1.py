"""Independent remainder/scalar-synthesis audit of half-angle branch controls."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.fft import rfft
    from circular_phase_lift_v1.lift import lift_block
    repo = Path(__file__).resolve().parents[1]
    producer = load(args.study/'report.json')
    plan = load(repo/'research/circular_phase_lift_v1_plan.json')
    assert producer['result'] == 'circular_phase_lift_known_ready'
    assert set(producer['cases']) == set(plan['known_controls'])
    for name, digest in producer['sources'].items():
        assert sha(repo/name) == sha(args.study/'exact_sources'/name) == digest
    args.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.out/'executed_audit.py')
    gate = plan['known_gates']['phase_or_wave_absolute']
    report = dict(result='running', cases=[], maximum_scalar_lift_error=0.,
                  maximum_scalar_wave_error=0., maximum_circular_error=0.,
                  maximum_analytic_spectral_leak_power=0.)

    def scalar_lift(raw):
        result = np.empty_like(raw)
        winds = np.zeros(raw.shape, np.int64)
        for column in range(raw.shape[1]):
            winding = 0
            result[0, column] = raw[0, column]
            for i in range(1, len(raw)):
                difference = float(raw[i, column]-raw[i-1, column])
                residual = math.remainder(difference, 2*math.pi)
                winding += int(round((difference-residual)/(2*math.pi)))
                result[i, column] = raw[i, column] - 2*math.pi*winding
                winds[i, column] = winding
        return result, winds

    def scalar_audio(common, delta, amplitude, carrier):
        output = np.empty((len(delta), 2))
        for i in range(len(delta)):
            for channel, sign in [(0, 1), (1, -1)]:
                output[i, channel] = math.fsum(
                    float(amplitude[i, h, channel])*math.cos(float(carrier[i, h])+
                        float(common[i, h])+sign*float(delta[i, h])/2)
                    for h in range(delta.shape[1]))
        return output

    try:
        data = {}
        for name, digest in producer['files'].items():
            assert sha(args.study/name) == digest
            with np.load(args.study/name, allow_pickle=False) as raw:
                data[Path(name).stem] = {key:raw[key] for key in raw.files}
        for label, value in data.items():
            expected, winds = scalar_lift(value['raw'])
            error = float(abs(value['lifted']-expected).max())
            assert error < gate
            report['maximum_scalar_lift_error'] = max(report['maximum_scalar_lift_error'], error)
            actual, state, info = lift_block(value['raw'])
            assert np.array_equal(actual, value['lifted']) and np.array_equal(info['winding'], winds)
            assert np.array_equal(state.winding, winds[-1])
            circular = float(abs(np.exp(1j*actual)-np.exp(1j*value['raw'])).max())
            assert circular < gate
            report['maximum_circular_error'] = max(report['maximum_circular_error'], circular)
        for label in ('positive_branch', 'negative_branch'):
            value = data[label]
            expected = scalar_audio(value['common'], value['truth'], value['amplitude'], value['carrier'])
            error = float(abs(value['audio']-expected).max())
            assert error < gate and abs(value['lifted']-value['truth']).max() < gate
            report['maximum_scalar_wave_error'] = max(report['maximum_scalar_wave_error'], error)
            spectrum = rfft(value['audio'], axis=0)/len(expected)
            bins = [{14, 34, 51}, {10, 28, 43}]
            if label == 'negative_branch':
                bins.reverse()
            for channel in (0, 1):
                leak = math.fsum(abs(spectrum[k, channel])**2 for k in range(len(spectrum)) if k not in bins[channel])
                assert leak < plan['known_gates']['analytic_spectral_leak_power']
                report['maximum_analytic_spectral_leak_power'] = max(report['maximum_analytic_spectral_leak_power'], leak)
                for k in (0, 1, 7, 23, 57, 100, 256, 1024, 2048):
                    explicit = complex(math.fsum(value['audio'][i, channel]*math.cos(-2*math.pi*k*i/len(expected)) for i in range(len(expected))),
                                       math.fsum(value['audio'][i, channel]*math.sin(-2*math.pi*k*i/len(expected)) for i in range(len(expected))))/len(expected)
                    assert abs(explicit-spectrum[k, channel]) < gate
            report['cases'].append(label)
        no_cross = data['no_crossing_exact']
        assert np.array_equal(no_cross['raw'], no_cross['lifted'])
        report['cases'].append('no_crossing_exact')
        value = data['positive_branch']
        raw_wave = scalar_audio(value['common'], value['raw'], value['amplitude'], value['carrier'])
        gauge_wave = scalar_audio(value['common']+math.pi*value['winding'], value['lifted'], value['amplitude'], value['carrier'])
        assert abs(raw_wave-gauge_wave).max() < gate
        report['cases'].append('gauge_compensation')
        difference = float(np.sqrt(np.mean((raw_wave-value['audio'])**2)))
        assert difference > .1
        assert abs(difference-producer['cases']['held_common_changes_wave']['wave_difference_RMS']) < gate
        report['cases'].append('held_common_changes_wave')
        for i in range(0, len(raw_wave), 17):
            for h in range(value['raw'].shape[1]):
                product = []
                for name in ('raw', 'lifted'):
                    z = []
                    for channel, sign in [(0, 1), (1, -1)]:
                        amplitude = value['amplitude'][i, h, channel]*(1+.2*math.sin(i*[.003, .005][channel]))
                        angle = value['common'][i, h]+sign*value[name][i, h]/2
                        z.append(amplitude*complex(math.cos(angle), math.sin(angle)))
                        assert abs(abs(z[-1])**2-amplitude**2) < gate
                    product.append(z[0]*z[1].conjugate())
                assert abs(product[0]-product[1]) < gate
        report['cases'].append('instantaneous_stereo_invariants')
        fast = data['fast_motion_ambiguity']
        assert abs(np.exp(1j*fast['truth'])-np.exp(1j*fast['alternative'])).max() < gate
        assert abs(fast['lifted']-fast['alternative']).max() < gate
        assert abs(fast['lifted']-fast['truth']).max() > 100
        _, _, ties = lift_block(np.array([[0.], [math.pi], [0.], [-math.pi]]))
        assert np.array_equal(ties['half_turn_ambiguous'].ravel(), [False, True, True, True])
        report['cases'].append('fast_motion_ambiguity')
        for path in data.values():
            for block in (37, 1024):
                state = None
                parts = []
                for start in range(0, len(path['raw']), block):
                    part, state, _ = lift_block(path['raw'][start:start+block], state)
                    parts.append(part)
                assert np.array_equal(np.concatenate(parts), path['lifted'])
                expected, winds = scalar_lift(path['raw'])
                assert np.array_equal(state.winding, winds[-1])
        report['cases'].append('block_continuity')
        assert set(report['cases']) == set(plan['known_controls'])
        report.update(result='independent_circular_phase_lift_known_passed',
                      producer_sha256=sha(args.study/'report.json'), auditor_sha256=sha(__file__),
                      physical_velocity_identified=False, recordings_read=False,
                      semantic_change_at_held_common_verified=True)
        save(args.out/'report.json', report)
        print(report)
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
