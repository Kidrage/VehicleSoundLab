"""Known-first independent source-query transfer comparison; never fit a voice."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--known-check', action='store_true')
    p.add_argument('--known', type=Path)
    p.add_argument('--known-audit', type=Path)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from exterior_clock_v1.warp import render_positions
    from source_resampling_v1.query import prepare, interpolate
    from source_resampling_v1.fixtures import fixtures, evaluate
    from source_resampling_v1.measure import summarize
    from native_error_budget_v1.assessment import locked_rows
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], sources={}, inputs={})
    def read(path):
        path = Path(path); r['inputs'][str(path)] = sha(path)
        return load(path)
    try:
        names = {'tools/run_source_resampling_v1.py', 'tools/audit_source_resampling_v1.py',
            'research/source_resampling_v1_plan.json', 'tools/research_archive_v1.py',
            'tools/exterior_clock_v1/warp.py', 'tools/native_error_budget_v1/assessment.py'}
        for folder in ('source_resampling_v1', 'extraction_sound_v1'):
            names.update(path.relative_to(repo).as_posix() for path in (repo/'tools'/folder).glob('*.py'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        if a.known_check:
            for label, frequency, coefficient, positions, n in fixtures():
                audio = evaluate(n/48000, frequency, coefficient)
                filtered, query, taps, crop = prepare(audio, 0., positions, 14000.)
                truth = evaluate(positions, frequency, coefficient, taps)
                raw_truth = evaluate(positions, frequency, coefficient)
                variants = dict(legacy=render_positions(audio, 0., positions, 14000.))
                variants.update({'sinc'+str(radius): interpolate(filtered, query, radius) for radius in (64, 128, 256)})
                scale = float(abs(coefficient).sum())
                errors, tails = {}, {}
                for name, value in variants.items():
                    maximum = float(np.max(abs(value-truth)))
                    relative = maximum/scale if scale else maximum
                    errors[name] = relative
                    if name != 'legacy': assert relative <= 2e-6, (label, name, relative)
                    _, error_power, _, _ = locked_rows(value-truth, np.ones(2049), 1.)
                    tails[name] = error_power[np.arange(2049)*16 > 18432].sum(axis=0).tolist()
                    if label == 'zero': assert np.count_nonzero(value) == 0
                    if label == 'silent_right': assert np.count_nonzero(value[:, 1]) == 0
                    if label == 'mono': assert np.array_equal(value[:, 0], value[:, 1])
                path = a.out/(label+'.npz')
                np.savez_compressed(path, audio=audio, positions=positions, filtered=filtered,
                    query=query, taps=taps, crop=np.array(crop), frequencies=frequency,
                    coefficients=coefficient, filtered_truth=truth, raw_truth=raw_truth, **variants)
                r['cases'].append(dict(label=label, file=path.name, sha256=sha(path),
                    source_coefficient_L1=scale, maximum_error_relative_source_L1=errors,
                    interpolation_error_above18432_Welch_FS2_LR=tails,
                    source_FIR_effect_max_FS=float(np.max(abs(raw_truth-truth)))))
                save(a.out/'report.json', r); print('SOURCE_QUERY_KNOWN', label, errors, flush=True)
            rejects = []
            audio = np.zeros((38400, 2)); positions = np.linspace(.25, .45, 8193)
            for label, x, q, cutoff in (
                ('left_context', audio, positions-.2, 14000.),
                ('right_context', audio, positions+.3, 14000.),
                ('complex_audio', audio.astype(complex), positions, 14000.),
                ('nonfinite_audio', audio*np.nan, positions, 14000.),
                ('nonfinite_query', audio, positions*np.nan, 14000.),
                ('nonmonotonic_query', audio, positions[::-1], 14000.),
                ('cutoff_outside_contract', audio, positions, 16000.)):
                try: prepare(x, 0., q, cutoff)
                except ValueError: rejects.append(label)
                else: raise AssertionError('Invalid source accepted: '+label)
            try: interpolate(audio, positions*48000, 32)
            except ValueError: rejects.append('undeclared_radius')
            else: raise AssertionError('Invalid radius accepted')
            r.update(result='source_resampling_known_measured', all_known_qualified=True,
                maximum_error_gate_relative_source_L1=2e-6, invalid_rejections=rejects)
        else:
            if a.known is None or a.known_audit is None:
                raise ValueError('Independent known qualification required')
            known, audit = read(a.known/'report.json'), read(a.known_audit/'report.json')
            assert known['all_known_qualified'] and audit['all_known_qualified']
            assert audit['producer_sha256'] == sha(a.known/'report.json')
            for name, digest in known['sources'].items(): assert sha(repo/name) == digest
            root = a.workspace/'references/analysis/waveform_file_real_v1'
            source = read(root/'prepare1/report.json'); proof = read(root/'prepare_audit1/report.json')
            assert proof['all_qualified'] and proof['producer_sha256'] == sha(root/'prepare1/report.json')
            for name, digest in source['inputs'].items():
                assert sha(name) == digest; r['inputs'][name] = digest
            assert len(source['cases']) == 6
            for case in source['cases']:
                path = root/'prepare1'/case['file']; assert sha(path) == case['sha256']
                r['inputs'][str(path)] = sha(path)
                with np.load(path) as f: z = {key: f[key] for key in f.files}
                assert np.array_equal(z['orders'], np.arange(1, 289))
                context_path = Path(case['context_file'])
                context = read(context_path.parent/'report.json')
                row = next(c for c in context['cases'] if c['label'] == case['label'])
                assert row['qualified'] and sha(context_path) == row['sha256']
                r['inputs'][str(context_path)] = sha(context_path)
                cutoff, start = float(row['info']['cutoff_hz']), float(z['source_start'])
                filtered, query, taps, crop = prepare(z['native'], start, z['source_coordinates'], cutoff)
                variants = dict(legacy=render_positions(z['native'], start, z['source_coordinates'], cutoff))
                reproduction = float(np.max(abs(variants['legacy']-z['audio'])))
                assert reproduction <= 2e-12, (case['label'], reproduction)
                variants.update({'sinc'+str(radius): interpolate(filtered, query, radius) for radius in (64, 128, 256)})
                info, arrays = summarize(variants, z['weights'], float(z['amplitude']))
                output = a.out/(case['label']+'.npz')
                np.savez_compressed(output, filtered=filtered, query=query, taps=taps, crop=np.array(crop),
                    source_coordinates=z['source_coordinates'], positions=z['positions'],
                    original_positions=z['original_positions'], orders=z['orders'], scale=z['scale'],
                    weights=z['weights'], amplitude=z['amplitude'], source_start=z['source_start'],
                    **variants, **arrays)
                r['cases'].append(dict(label=case['label'], file=output.name, sha256=sha(output),
                    original_preparation=str(path), context_file=str(context_path),
                    cutoff_hz=cutoff, source_start=start, frames=len(query),
                    legacy_original_reproduction_max_FS=reproduction, measurements=info,
                    geometry_scales_orders_unchanged=True, no_fit_or_source_admission=True))
                save(a.out/'report.json', r)
                print('SOURCE_QUERY_ACTUAL', case['label'], 'legacy reproduce', reproduction,
                    'oldtail', sum(info['legacy']['highest_split_Welch_FS2_LR'][-1]),
                    'newtail', sum(info['sinc128']['highest_split_Welch_FS2_LR'][-1]), flush=True)
            r.update(result='source_resampling_six_actual_measured', same_original_six_cases=True,
                original_source_fidelity_qualified=False, original_source_fidelity_gates_unchanged=True,
                eligible_for_later_source_statistics=False)
        r.update(no_original_data_or_fits_or_C_or_hearings_modified=True,
            source_kernel_diagnosis_not_sustained_engine_or_source_separation=True)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__':
    main()
