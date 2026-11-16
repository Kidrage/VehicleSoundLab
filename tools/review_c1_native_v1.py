"""Publish loss localization from saved C1 native results, without fitting/audio promotion."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from c1_native_review_v1.measure import analyze
    from c1_native_review_v1.audit import verify
    from c1_native_review_v1.known import qualify
    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', sources={}, inputs={})
    errors = {}
    def check(name, observed, expected, scale):
        observed, expected = np.asarray(observed), np.asarray(expected)
        assert observed.shape == expected.shape, name
        value = float(np.max(abs(observed-expected)))/max(float(scale), 1e-300)
        errors[name] = value
        if not np.isfinite(value) or value > 2e-11:
            raise ValueError('Independent comparison failed: '+name+' '+str(value))
    try:
        for name in ('tools/review_c1_native_v1.py', 'tools/c1_native_review_v1/__init__.py',
            'tools/c1_native_review_v1/measure.py', 'tools/c1_native_review_v1/audit.py',
            'tools/c1_native_review_v1/known.py', 'tools/research_archive_v1.py'):
            dest = args.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            report['sources'][name] = sha(dest)
        # All observable controls precede reading actual source packets.
        report['known'] = qualify(check)
        study = args.workspace/'references/analysis/c1_native_diagnostics_v1'
        producer, auditor = study/'real1/report.json', study/'real_declared_audit1/report.json'
        source, audit = load(producer), load(auditor)
        assert source['result'] == 'c1_declared_native_real_measured' and len(source['cases']) == 1
        assert audit['verification_passed'] and audit['producer_sha256'] == sha(producer)
        assert not source['eligible_for_later_source_statistics']
        for name, digest in source['sources'].items():
            assert sha(repo/name) == digest, name
        for name, digest in source['inputs'].items():
            assert sha(name) == digest, name
        for path in (producer, auditor): report['inputs'][str(path)] = sha(path)
        case = source['cases'][0]
        assert case['label'] == 'F3 Fifth First Late' and case['count'] == 9884
        folder = producer.parent/case['label']
        packet = folder/'sound.npz'
        assert sha(packet) == case['files'][packet.name]
        report['inputs'][str(packet)] = sha(packet)
        with np.load(packet) as value:
            raw, filtered, grid, fit = (value[name+'_audio'] for name in
                ('raw', 'source_FIR', 'source_16', 'candidate_16'))
        arrays, rows = analyze(raw, filtered, grid, fit)
        report['independent_review'] = verify(arrays, rows, check)
        np.savez_compressed(args.out/'measured.npz', **arrays)
        save(args.out/'bands.json', rows)
        with (args.out/'bands.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(('band_Hz', 'raw_L_plus_R_FS2', 'candidate_L_plus_R_FS2',
                'error_L_plus_R_FS2', 'complex_NRMSE', 'fraction_total_error',
                'radial_error_FS2', 'angular_error_FS2', 'FIR_auto_FS2',
                'roundtrip_auto_FS2', 'grid_fit_auto_FS2',
                'FIR_roundtrip_signed_FS2', 'FIR_fit_signed_FS2', 'roundtrip_fit_signed_FS2'))
            for row in rows:
                cross, auto = np.asarray(row['component_signed_cross_FS2_LR']), np.asarray(row['component_auto_FS2_LR'])
                writer.writerow((str(row['low_Hz'])+'-'+str(min(row['high_exclusive_Hz'], 24000)),
                    *[sum(row[key]) for key in ('reference_FS2_LR', 'candidate_FS2_LR', 'error_FS2_LR')],
                    row['combined_complex_NRMSE'], row['fraction_of_total_observed_error'],
                    sum(row['radial_error_FS2_LR']), sum(row['angular_error_FS2_LR']),
                    *auto.sum(axis=1), cross[0, 1].sum(), cross[0, 2].sum(), cross[1, 2].sum()))
        error = arrays['bin_error_power'].sum(axis=1)
        order = np.argsort(error)[::-1][:20]
        report.update(label=case['label'], native_start_seconds=case['native_start'], native_frames=len(raw),
            native_sample_rate=48000, windows=len(arrays['starts']),
            maximum_error_bins=[dict(Hz=float(arrays['frequency'][k]), error_FS2=float(error[k])) for k in order],
            observed_total_reference_FS2=float(arrays['raw_bin_power'].sum()),
            observed_total_error_FS2=float(error.sum()), bands=rows,
            original_wave_and_stereo_comparisons=case['comparisons'],
            source_solver_qualified=True, source_fidelity_qualified=False,
            eligible_for_later_source_statistics=False,
            native_grid_interpretation=case['native_grid_interpretation'],
            error_components=['source_FIR-minus-raw', 'source_grid_roundtrip-minus-source_FIR',
                'fitted_grid_roundtrip-minus-source_grid_roundtrip'],
            direct_continuous_OSC_measured=False, acoustic_or_audibility_or_causal_attribution=False,
            no_new_fit_C_preset_hearing_or_runtime_change=True,
            original_gates_and_failures_unchanged=True)
        x = np.arange(len(rows))
        labels = [row['band'] for row in rows]
        rawp = np.array([sum(row['reference_FS2_LR']) for row in rows])
        errp = np.array([sum(row['error_FS2_LR']) for row in rows])
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.9), constrained_layout=True)
        axes[0].bar(x-.18, rawp, .36, label='Raw reference')
        axes[0].bar(x+.18, errp, .36, label='Complex error')
        axes[0].set_yscale('log'); axes[0].set_ylabel('Observed L+R mean power (FS squared)')
        axes[0].set_title('Absolute power: weak upper bands remain visible'); axes[0].legend()
        axes[1].bar(x, errp/errp.sum()*100, color='#308578')
        axes[1].set_ylabel('Fraction of total observed spectral error (%)')
        axes[1].set_title('Error location does not establish audible cause')
        for ax in axes:
            ax.set_xticks(x, labels, rotation=45); ax.set_xlabel('Physical band (Hz / kHz labels)')
            ax.grid(axis='y', alpha=.2)
        fig.suptitle('F3 Fifth First Late | same 9,884 native frames | no gain compensation')
        for ext in ('png', 'svg'): fig.savefig(args.out/('native_loss.'+ext), dpi=150)
        plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.9), constrained_layout=True)
        freq = arrays['frequency']
        axes[0].semilogy(freq, arrays['raw_bin_power'].sum(axis=1), label='Raw reference', alpha=.8)
        axes[0].semilogy(freq, error, label='Candidate error', color='#b75f35')
        axes[0].set_xlim(1500, 4000); axes[0].set_xlabel('Native frequency (Hz)')
        axes[0].set_ylabel('Observed mean power per bin (FS squared)')
        axes[0].set_title('Largest error bins cluster around 2-3 kHz'); axes[0].legend()
        radial = np.array([sum(row['radial_error_FS2_LR']) for row in rows])
        angular = np.array([sum(row['angular_error_FS2_LR']) for row in rows])
        axes[1].bar(x, radial/errp, label='Magnitude geometry')
        axes[1].bar(x, angular/errp, bottom=radial/errp, label='Angle geometry')
        axes[1].set_xticks(x, labels, rotation=45); axes[1].set_ylim(0, 1.12)
        axes[1].set_ylabel('Fraction of each band complex error')
        axes[1].set_title('Geometric identity; no physical-source separation'); axes[1].legend(fontsize=9)
        for ax in axes: ax.grid(alpha=.2)
        fig.suptitle('Saved-grid C1 reconstruction | sustained autonomous synthesis not evaluated')
        for ext in ('png', 'svg'): fig.savefig(args.out/('native_error_geometry.'+ext), dpi=150)
        plt.close(fig)
        report['files'] = {path.name:sha(path) for path in sorted(args.out.iterdir()) if path.is_file()}
        report.update(result='c1_native_loss_review_measured_and_independently_verified',
            verification_passed=True, comparison_gate=2e-11, comparisons=len(errors),
            maximum_errors=errors, maximum_comparison_error=max(errors.values()))
        save(args.out/'report.json', report)
        print('C1_NATIVE_REVIEW', report['result'], 'checks', len(errors), 'max', max(errors.values()), flush=True)
    except BaseException as error:
        report.update(result='failed', error=repr(error), maximum_errors=errors)
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
