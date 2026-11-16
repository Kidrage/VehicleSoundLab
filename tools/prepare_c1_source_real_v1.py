"""One never-full-waveform-fitted C1/22k source, explicit legacy calibration."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_source_adapter_v1.contract import prepare, FIELDS
    from c1_source_adapter_v1.objective import build
    from c1_source_prepare_v1.source import sample
    from c1_source_prepare_v1.provenance import Proofs
    from clock_c1_v1.geometry import from_context, evaluate
    repo = Path(__file__).resolve().parents[1]; a.out.mkdir(parents=True, exist_ok=False)
    label = 'F3 Fifth First Late'
    r = dict(result='running', label=label, cases=[], inputs={}, sources={},
        new_source_identity='vsl.c1-22k-source-preparation/1', no_inverse_fit=True)
    proof = Proofs(a.workspace, repo, r)
    try:
        original, context_report = proof.prerequisites()
        guard = proof.protect(label); save(a.out/'protected_before.json', guard)
        row = next(v for v in original['cases'] if v['label'] == label)
        path = proof.bind(a.workspace/'references/analysis/waveform_file_real_v1/prepare1'/row['file'])
        assert sha(path) == row['sha256']
        with np.load(path) as f: old = {k:f[k] for k in f.files}
        context_path = proof.bind(row['context_file'])
        cr = next(v for v in context_report['cases'] if v['label'] == label)
        assert sha(context_path) == cr['sha256'] and cr['qualified']
        with np.load(context_path) as f: context = {k:f[k] for k in f.files}
        assert np.array_equal(context['native'], old['native']) and np.array_equal(context['positions'], old['source_coordinates'])
        assert np.array_equal(context['sample_indices'], np.arange(len(old['audio'])))
        old['metric_target'] = old['target'].copy()
        legacy = {k:old[k] for k in FIELDS}
        clock = from_context(context); coordinates = evaluate(clock, context['sample_indices'])
        sampled = sample(old['native'], float(old['source_start']), coordinates)
        packet, metadata = prepare(legacy, dict(x=clock['x'], y=clock['y']), clock,
            sampled['audio'], sampled['taps'], 22000.)
        system, _, _ = build(packet)
        rng = np.random.default_rng(94116); q = old['probe_q'].copy()
        rows = rng.normal(0, .1, system.shape[0]); forward = system@q; m = system.metric
        packet.update(native=old['native'], source_start=old['source_start'], aperture=old['aperture'],
            clock_times=old['clock_times'], root_hz=old['root_hz'],
            source_filtered=sampled['filtered'], source_query=sampled['query'], source_crop=sampled['crop'],
            source_radius=sampled['radius'], source_beta=sampled['beta'],
            probe_q=q, probe_rows=rows, probe_forward=forward, probe_adjoint=system.rmatvec(rows),
            probe_normal=system.rmatvec(forward), probe_rhs=system.rhs(packet['audio']),
            coverage=m.frame.coverage, time_coverage=m.time_coverage, target_slots=m.target_window_slots)
        assert (len(packet['audio']), len(packet['target']), len(packet['positions']), len(packet['orders'])) == (18430, 14334, 73, 288)
        assert np.array_equal(packet['orders'], np.arange(1, 289))
        output = a.out/(label+'.npz'); np.savez_compressed(output, **packet)
        r['cases'].append(dict(label=label, file=output.name, sha256=sha(output), metadata=metadata,
            original_preparation=str(path), original_context=str(context_path),
            frames=18430, target_frames=14334, nodes=73, original_nodes=57, orders=288,
            no_full_waveform_fit_in_canonical_namespaces=True, source_fidelity_not_evaluated=True,
            eligible_for_later_source_statistics=False))
        names = set(r['sources']) | {'tools/prepare_c1_source_real_v1.py', 'tools/audit_c1_source_preparation_v1.py',
            'research/c1_source_preparation_v1_plan.json'}
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/c1_source_prepare_v1').glob('*.py'))
        for name in sorted(names):
            if name in r['sources']: assert sha(repo/name) == r['sources'][name]
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        after = proof.protect(label); assert after == guard; save(a.out/'protected_after.json', after)
        r.update(result='c1_source_one_real_prepared', full_probe_shape=list(system.shape),
            explicit_legacy_metric_target_unchanged=True, protected_before_after_exact=True,
            source_fidelity_not_evaluated=True, eligible_for_later_source_statistics=False,
            no_firstEarly_firstMid_refit_or_remaining4batch=True, no_runtime_C_model_or_hearing_change=True)
        save(a.out/'report.json', r); print('C1_SOURCE_REAL_PREPARED', label, metadata['bandwidth'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
