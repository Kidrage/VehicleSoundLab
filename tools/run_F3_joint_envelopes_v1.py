"""Known-first three-second full-band stereo observations in original time."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args();repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from native_regions_v1.spectrum import measure
    from joint_envelopes_v1.controls import cases
    from joint_envelopes_v1.features import describe
    from drive_evidence_v1.sources import read
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, known=[], real=[])
    try:
        names = ['tools/run_F3_joint_envelopes_v1.py', 'tools/native_regions_v1/spectrum.py',
                 'tools/drive_evidence_v1/sources.py', 'tools/research_archive_v1.py',
                 'research/F3_joint_envelopes_v1_plan.json']
        names += [p.relative_to(repo).as_posix() for p in (repo/'tools/joint_envelopes_v1').glob('*.py')]
        for name in names:
            dst = a.out/'exact_sources'/name
            dst.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(repo/name, dst)
            r['sources'][name] = sha(dst)
        plan = load(repo/'research/F3_joint_envelopes_v1_plan.json');spec = plan['measurement']
        protected = a.workspace/'baselines/catalog_local_F3_v1/evidence'
        r['protected_before'] = dict(load(protected/'C_files_sha256.json'), **load(protected/'voice_files_sha256.json'))
        for name, h in r['protected_before'].items():assert sha(repo/name) == h

        def execute(label, audio, envelope=None, receipt=None):
            n, hop, size = [spec[k] for k in ['window_samples', 'hop_samples', 'fft_samples']]
            starts = np.arange(0, len(audio)-n+1, hop)
            region = np.zeros((len(starts), size//2+1), np.uint8)
            P = measure(audio, region, spec)['P_total']
            values = describe(P, starts, plan)
            values.update(audio=audio, P=P, window_starts=starts)
            if envelope is not None:values['known_envelopes'] = envelope
            folder = a.out/label;folder.mkdir()
            np.savez_compressed(folder/'arrays.npz', **values)
            if receipt:save(folder/'source_receipt.json', receipt)
            row = dict(label=label, frames=len(audio), windows=len(starts),
                       arrays_sha256=sha(folder/'arrays.npz'), floored_values=int(values['floored'].sum()),
                       trend_slope_dB_per_second=values['trend_coefficients'][1].reshape(-1, 2).tolist(),
                       affine_residual_std_dB=np.sqrt(np.diag(values['affine_residual_covariance'])).reshape(-1, 2).tolist())
            if envelope is not None:
                window = .5-.5*np.cos(2*np.pi*np.arange(n)/n);w2 = window*window
                expected = np.zeros((len(starts), 4, 2, 2), complex)
                known = plan['known']
                for b, amp in enumerate(known['amplitude_L']):
                    for i, first in enumerate(starts):
                        e = envelope[first:first+n, b]
                        expected[i, b, 0, 0] = amp*amp/2*np.average(e[:, 0]**2, weights=w2)
                        expected[i, b, 1, 1] = (amp*known['amplitude_R_ratio'])**2/2*np.average(e[:, 1]**2, weights=w2)
                        expected[i, b, 0, 1] = amp*amp*known['amplitude_R_ratio']/2*np.average(e[:, 0]*e[:, 1], weights=w2)*np.exp(-1j*known['phase_R'][b])
                        expected[i, b, 1, 0] = expected[i, b, 0, 1].conjugate()
                error = float(abs(P[:, 4:]-expected).max())
                assert error <= plan['gates']['analytic_HF_matrix_absolute_FS2'], (label, error)
                row['analytic_HF_matrix_max_error_FS2'] = error
            print('PASS full-band envelopes', label, flush=True)
            return row

        for name, audio, envelope in cases(plan):
            r['known'].append(execute('known_'+name, audio, envelope));save(a.out/'report.json', r)
        r['known_passed_before_source'] = True
        catalog_path = a.workspace/'references/segments_v1.json'
        r['inputs'][str(catalog_path)] = sha(catalog_path)
        catalog = load(catalog_path)
        for segment in plan['source_segments']:
            audio, receipt = read(a.workspace, segment, plan['use'])
            for key in ['master', 'raw']:
                path = a.workspace/catalog['sources']['F3'][key]
                r['inputs'][str(path)] = sha(path)
            r['real'].append(execute(segment, audio, receipt=receipt));save(a.out/'report.json', r)
        for name, h in r['protected_before'].items():assert sha(repo/name) == h
        r.update(result='native_joint_full_band_envelopes_observed',
                 physical_separation=False, stochastic_law_qualified=False,
                 audio_resampled_or_normalized=False, runtime_changed=False)
    except Exception as exc:
        r.update(result='failed', error=repr(exc));raise
    finally:save(a.out/'report.json', r)


if __name__ == '__main__':main()
