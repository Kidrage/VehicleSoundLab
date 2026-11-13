"""ALLoriginal recorded/samePSD phase portions, with the finite-record counterexample."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load, save, sha
from idle_closure_evidence_v1.observe import observe, arc_membership, known, closure, FREQUENCIES, ORIGINS
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, parent_manifests={}, observations=[])
try:
    plan_path = repo/'research/idle_closure_evidence_v1_plan.json'; plan = load(plan_path)
    for path in [Path(__file__), plan_path, repo/'tools/research_archive_v1.py',
        repo/'tools/idle_closure_evidence_v1/observe.py', repo/'tools/idle_conditioned_detail_v1/features.py',
        repo/'tools/idle_phase_difference_v1/features.py', repo/'tools/idle_positive_power_v1/model.py']:
        name = path.relative_to(repo); dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][name.as_posix()] = sha(path)
    r['known'] = known(); save(a.out/'known.json', r['known']); print(dict(stage='known_passed'), flush=True)
    tables = {}
    for name in plan['parents']:
        path = a.workspace/'baselines'/name/'manifest.json'; r['parent_manifests'][name] = sha(path)
        tables[name] = {v['path']: v['sha256'] for v in load(path)['files']}

    def parent(name, file):
        path = a.workspace/'baselines'/name/file; digest = sha(path); assert digest == tables[name][file]
        r['inputs'][str(path)] = digest; return path

    profile_path = parent('fixed_source_profiles_v1', 'evidence/trial1/F2_tailpipe/profile.json')
    profile = load(profile_path); assert np.array_equal(np.asarray(profile['modal']['frequencies_hz'])[[1, 2, 4]], FREQUENCIES)
    assert np.array_equal(np.asarray(profile['modal']['initial_phase_LR'])[[1, 2, 4], 0], ORIGINS)
    law_path = parent('idle_positive_power_v1', 'evidence/observe1/report.json')
    law = load(law_path)['observations'][0]['models']['expanded']
    rows = {}; closures = {}; source_q = {}
    for seed in [None, 149921, 277139, 381611]:
        group = 'source' if seed is None else 'phase'+str(seed)
        for part in ['train', 'check']:
            suffix = '' if seed is None else '_phase_'+str(seed)
            path = parent('idle_conditioned_detail_v1', f'evidence/observe1/{part}{suffix}.npz')
            with np.load(path) as data: z = data['phasors'][12000:-12000]
            stats, arrays = observe(z); label = group+'_'+part; output = a.out/(label+'.npz')
            q = predict(law, matrix(z, hop=1, trim=0))
            np.savez_compressed(output, phasors=z, q=q, **arrays)
            row = dict(label=label, group=group, seed=seed, part=part, input_path=str(path),
                file=output.name, sha256=sha(output), **stats)
            r['observations'].append(row); rows[label] = row; closures[label] = arrays['closure']
            if seed is None:
                source_q[part] = q
                with np.load(parent('idle_phase_transfer_v1', 'evidence/observe1/source_'+part+'.npz')) as prior:
                    assert np.array_equal(q, prior['q'])
                    assert np.allclose(q.mean(axis=0), prior['mean'], atol=1e-13)
                    assert np.allclose(np.cov(q, rowvar=False, bias=True), prior['covariance'], atol=1e-13)
        train = rows[group+'_train']; check = closures[group+'_check']
        inside = arc_membership(check, train)
        r.setdefault('source_arc_check_coverage', {})[group] = None if inside is None else float(inside.mean())
        print(dict(stage='group', group=group, resultant=[rows[group+'_'+p]['resultant'] for p in ['train', 'check']]), flush=True)
    # ALL180000fixed centers; no selection using prior curves or best phase origin.
    t = (np.arange(180000)*48+23.5)/48000
    delta = FREQUENCIES[2]-FREQUENCIES[1]-FREQUENCIES[0]; phi = ORIGINS[2]-ORIGINS[1]-ORIGINS[0]
    runtime_w = np.exp(1j*(phi+2*np.pi*delta*t)); inside = arc_membership(runtime_w, rows['source_train'])
    path = a.out/'runtime_arc.npz'; np.savez_compressed(path, time_seconds=t, closure=runtime_w,
        inside_train_arc=np.array([], dtype=bool) if inside is None else inside)
    r.update(result='all8_closure_portions_and_shortrecord_counterexample_observed', plan=plan,
        law_path=str(law_path), runtime_arc_file=path.name, runtime_arc_sha256=sha(path),
        runtime_arc_coverage=None if inside is None else float(inside.mean()),
        runtime_first12s_arc_coverage=None if inside is None else float(inside[:12000].mean()),
        source_window_seconds=[6.25, 8.75, 9.25, 11.75],
        source_q_previous_exact=True, longterm_stationary_coupling_identified=False,
        runtime_changed=False, audio_generated=False)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(dict(result=r['result'], runtime_arc=r.get('runtime_arc_coverage'), check_arc=r.get('source_arc_check_coverage')), flush=True)
