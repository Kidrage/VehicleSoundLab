"""Known-first C1 declared terminal/native diagnostics; never launches a fit."""
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
    p.add_argument('--mode', choices=('known', 'real'), required=True)
    p.add_argument('--known-study', type=Path)
    p.add_argument('--known-audit', type=Path)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_native_diagnostics_v1.input import terminal, IDENTITY
    from c1_native_diagnostics_v1.native import references, sampled
    from clock_native_bridge_v1.observation import observe, compare_all, convergence
    from clock_native_bridge_v1.inverse import roundtrip
    from extraction_sound_v1.measure import measure
    from extraction_sound_v1.compare import compare
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', schema=IDENTITY, mode=a.mode, sources={}, inputs={}, cases=[],
        no_fit_or_runtime_or_hearing_change=True, eligible_for_later_source_statistics=False)

    def read(path):
        path = Path(path)
        r['inputs'][str(path)] = sha(path)
        return load(path)

    try:
        bridge = a.workspace/'references/analysis/clock_native_bridge_v1'
        previous, previous_audit = read(bridge/'known1/report.json'), read(bridge/'known_audit1/report.json')
        assert previous['all_known_qualified'] and previous_audit['verification_passed']
        assert previous_audit['producer_sha256'] == sha(bridge/'known1/report.json')
        for name, digest in previous['sources'].items():
            assert sha(repo/name) == sha(bridge/'known1/exact_sources'/name) == digest
        names = set(previous['sources']) | {
            'tools/run_c1_native_diagnostics_v1.py', 'tools/audit_c1_native_diagnostics_v1.py',
            'tools/observer_frequency_v1/reduced_oracle.py', 'tools/locked_source_tail_v1/known.py',
            'research/c1_native_diagnostics_v1_plan.json'}
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/c1_native_diagnostics_v1').glob('*.py'))
        for name in sorted(names):
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        gates = dict(previous['gates'])
        r.update(gates=gates, inherited_known_bridge_cases=len(previous['cases']),
            inherited_weak_band_convergence_failures=[c['label'] for c in previous['cases']
                if not c['native16_32_all_six_bands_converged']])
        if a.mode == 'known':
            parent = a.workspace/'references/analysis/c1_source_adapter_v1/known1'
            proof = a.workspace/'references/analysis/c1_registered_source_v1/known1'
            cases = [(parent/name, proof) for name in
                ('affine_unequal', 'nonlinear_delay', 'nonlinear_silent_right', 'nonlinear_zero')]
        else:
            if a.known_study is None or a.known_audit is None:
                raise ValueError('New adapter known study and independent audit required')
            known, ka = read(a.known_study/'report.json'), read(a.known_audit/'report.json')
            if (not known.get('all_known_qualified') or not ka.get('verification_passed')
                    or not ka.get('all_known_qualified') or known['sources'] != r['sources']
                    or ka['producer_sha256'] != sha(a.known_study/'report.json')):
                raise ValueError('Exactly qualified new C1 adapter sources required')
            registration = read(a.workspace/'references/analysis/c1_fit_registration_v1/registration1/report.json')
            claim = Path(registration['pair']['spec']['storage_claim'])
            cases = [(claim/'run1', claim/'run1_audit')]
        for case, proof in cases:
            z, binding = terminal(case, proof, workspace=a.workspace, known=a.mode == 'known')
            r['inputs'].update(binding['inputs'])
            out = a.out/binding['label']
            out.mkdir()
            clock, source = references(z, known=a.mode == 'known')
            source.update(source_grid_audio=z['audio'], fitted_grid_audio=z['wave'],
                fitted=z['fitted'], fit_positions=z['positions'], orders=z['orders'])
            values = dict(raw=source['raw'], source_FIR=source['source_FIR'])
            for name in ('source', 'candidate'):
                for up in (16, 32):
                    rendered = sampled(z, source, clock, name, up)
                    key = name+'_'+str(up)
                    np.savez_compressed(out/(key+'.npz'), **rendered)
                    values[key] = rendered['native']
                    print('C1_NATIVE', binding['label'], key, len(rendered['native']), flush=True)
            np.savez_compressed(out/'source.npz', **source)
            measured, arrays = observe(values)
            np.savez_compressed(out/'sound.npz', **arrays)
            pairs = [(name, reference) for name in ('source_16', 'source_32', 'candidate_16', 'candidate_32')
                for reference in ('raw', 'source_FIR')]
            pairs += [('source_16', 'source_32'), ('candidate_16', 'candidate_32'),
                ('candidate_16', 'source_16'), ('candidate_32', 'source_32'), ('source_FIR', 'raw')]
            comparisons = compare_all(values, measured, pairs)
            virtual = []
            for name, part in (('target', slice(2048, -2048)), ('genuine_full', slice(None))):
                ref = measure(z['audio'][part], 65536, orders=z['orders'], root=64)
                fit = measure(z['wave'][part], 65536, orders=z['orders'], root=64)
                np.savez_compressed(out/('virtual_'+name+'.npz'), reference_audio=z['audio'][part],
                    candidate_audio=z['wave'][part], **{'reference_'+k:v for k,v in ref.items()},
                    **{'candidate_'+k:v for k,v in fit.items()})
                virtual.append(dict(region=name, frames=len(z['audio'][part]), signed_changes=compare(fit, ref),
                    rate=65536, root=64, coordinate_is_virtual_not_RPM_or_physical_Hz=True))
            source_error = comparisons['source_16_vs_source_FIR']['wave_NRMSE']
            fit_error = comparisons['candidate_16_vs_source_FIR']['wave_NRMSE']
            passed = (source_error is not None and fit_error is not None
                and source_error <= .003 and fit_error <= .003) if a.mode == 'known' else None
            if a.mode == 'known' and binding['label'] == 'nonlinear_zero':
                passed = all(not np.count_nonzero(v) for v in values.values())
            row = dict(label=binding['label'], source=binding, native_start=float(source['native_start']),
                count=int(source['count']), virtual=virtual, comparisons=comparisons,
                inverse_roundtrip=roundtrip(clock, z['phase_grid_indices']), known_wave_qualified=passed,
                source_native16_32_converged=convergence(comparisons['source_16_vs_source_32'], gates),
                candidate_native16_32_converged=convergence(comparisons['candidate_16_vs_candidate_32'], gates),
                native_grid_interpretation='sampled-grid sinc128, not direct continuous fitted OSC',
                files={p.name:sha(p) for p in out.glob('*.npz')})
            r['cases'].append(row)
            save(a.out/'report.json', r)
        r.update(result='c1_declared_native_'+a.mode+'_measured',
            all_known_qualified=all(c['known_wave_qualified'] for c in r['cases']) if a.mode == 'known' else None,
            original_failures_preserved=True, no_raw_fullband_or_source_separation_or_naturalness_claim=True)
        save(a.out/'report.json', r)
        print('C1_NATIVE_COMPLETE', a.mode, r['all_known_qualified'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
