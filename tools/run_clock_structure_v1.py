"""Known-first clock geometry and controlled transfer, with frozen real input."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'tail-study', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--mode', required=True, choices=('known', 'real'))
    p.add_argument('--known-study', type=Path)
    p.add_argument('--known-audit', type=Path)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from clock_structure_v1.known import qualify
    from clock_structure_v1.geometry import reconstruct
    from clock_structure_v1.spectra import measure
    from locked_source_diagnostics_v1.native_identity import verify
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', mode=a.mode, sources={}, inputs={})
    def read(path):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        return load(path)
    try:
        prior_stage = 'known1' if a.mode == 'known' else 'real1'
        prior_audit = 'known_audit1' if a.mode == 'known' else 'audit1'
        prior = read(a.tail_study/prior_stage/'report.json')
        proof = read(a.tail_study/prior_audit/'report.json')
        assert prior['result'] == 'locked_source_tail_'+a.mode+'_measured'
        assert proof['verification_passed'] and proof['producer_sha256'] == sha(a.tail_study/prior_stage/'report.json')
        names = set(prior['sources']) | {'tools/run_clock_structure_v1.py', 'tools/audit_clock_structure_v1.py',
            'research/clock_structure_v1_plan.json'}
        names.update(path.relative_to(repo).as_posix() for path in (repo/'tools/clock_structure_v1').glob('*.py'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        for name, expected in prior['sources'].items():
            assert sha(repo/name) == sha(a.tail_study/prior_stage/'exact_sources'/name) == expected
        r.update(tail_study=str(a.tail_study), original_source_fidelity_qualified=False,
            eligible_for_later_source_statistics=False, no_actual_clock_or_target_replacement=True,
            no_refit_or_sustained_C_or_hearing_promotion=True)
        if a.mode == 'known':
            capture = a.tail_study/'known1/capture.npz'
            r['inputs'][str(capture)] = sha(capture)
            assert sha(capture) == prior['capture_sha256']
            with np.load(capture) as f:
                coeff, freqs, taps = f['coefficients'], f['frequencies'], f['taps']
                weights, amplitude = f['weights'], f['amplitude']
            arrays, values, known = qualify(prior['frames'], coeff, freqs, taps)
            spectral, info = measure(values, weights, float(amplitude), 'exact_smooth')
            arrays.update(spectral, weights=weights, amplitude=amplitude)
            arrays.update({'signal__'+name: value for name, value in values.items()})
            r.update(known=known, observations=info)
        else:
            assert a.known_study is not None and a.known_audit is not None
            known = read(a.known_study/'report.json'); ka = read(a.known_audit/'report.json')
            assert known['result'] == 'clock_structure_known_measured' and known['known']['all_known_qualified']
            assert ka['result'] == 'independent_clock_structure_known_verified' and ka['verification_passed']
            assert ka['producer_sha256'] == sha(a.known_study/'report.json')
            for name, expected in known['sources'].items():
                assert sha(repo/name) == sha(a.known_study/'exact_sources'/name) == expected
            source_study = Path(prior['source_study'])
            source = read(source_study/'report.json')
            z, _ = verify(source, source_study, repo, r['inputs'])
            archive = a.workspace/'baselines/recorded_phase_context_v1'
            context_study = archive/'evidence/real1'
            cr = read(context_study/'report.json'); ca = read(archive/'evidence/real_audit1/report.json')
            assert cr['result'] == 'recorded_phase_context_real_measured'
            assert ca['result'] == 'independent_recorded_phase_context_real_verified' and ca['all_qualified']
            assert ca['producer_sha256'] == sha(context_study/'report.json')
            row = next(c for c in cr['cases'] if c['label'] == prior['label'])
            context_file = context_study/row['file']
            assert sha(context_file) == row['sha256']
            r['inputs'][str(context_file)] = sha(context_file)
            for name, expected in cr['sources'].items():
                assert sha(repo/name) == sha(context_study/'exact_sources'/name) == expected
            with np.load(context_file) as f:
                context = {key: f[key] for key in f.files}
            assert np.array_equal(context['positions'], z['source_coordinates'])
            assert np.array_equal(context['native'], z['native'])
            assert np.array_equal(context['original_audio'], z['metric_target'])
            arrays, info = reconstruct(context)
            r.update(geometry=info, context_file=str(context_file), context_study=str(context_study),
                context_audit=str(archive/'evidence/real_audit1'), label=prior['label'],
                known_study=str(a.known_study), known_audit=str(a.known_audit),
                old_source_highest_NRMSE=prior['original_metrics']['target_supported_band_complex_NRMSE'][-1],
                no_new_actual_audio_generated=True)
        np.savez_compressed(a.out/'capture.npz', **arrays)
        r.update(result='clock_structure_'+a.mode+'_measured', capture_sha256=sha(a.out/'capture.npz'))
        save(a.out/'report.json', r)
        print('CLOCK_STRUCTURE_COMPLETE', a.mode, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
