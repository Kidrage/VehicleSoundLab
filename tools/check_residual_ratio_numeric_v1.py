"""Known tiny-residual conditioning and exact quotient controls; no real audio read."""
import argparse
import os
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'out'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import numpy as np
from local_voice_batch_v1.ratio_exact import exact_rho, compare
from local_voice_batch_v1.ratio_trace import trace
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, cases=[], primitives=[])
try:
    for name in ('tools/check_residual_ratio_numeric_v1.py', 'research/residual_ratio_numeric_v1_plan.json',
                 'tools/local_voice_batch_v1/ratio_exact.py', 'tools/local_voice_batch_v1/ratio_trace.py',
                 'tools/sound_dna/statistics.py', 'tools/research_archive_v1.py'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    plan = load(repo/'research/residual_ratio_numeric_v1_plan.json')
    fixtures = dict(zero=np.zeros((64, 4)), below_floor=np.tile(np.arange(64)[:, None]*1e-20, (1, 4)),
                    positive_clip=np.tile(1.001**np.arange(64)[:, None], (1, 4)),
                    negative_clip=np.tile((-1.001)**np.arange(64)[:, None], (1, 4)))
    for name, fixture in fixtures.items():
        exact, info = exact_rho(fixture)
        actual = np.clip(np.sum(fixture[1:]*fixture[:-1])/max(np.sum(fixture[:-1]**2), 1e-30), -.95, .95)
        assert abs(actual-exact) < plan['literal_moment_error_gate']
        assert (exact == 0) if name == 'zero' else True
        if name.endswith('clip'):
            assert exact == (.95 if name.startswith('positive') else -.95)
        if name == 'below_floor':
            assert info['used_floor']
        r['primitives'].append(dict(name=name, literal_error=abs(actual-exact), **info))
    n, h = plan['known_rows']['frames'], plan['known_rows']['harmonics']
    rng = np.random.default_rng(plan['known_rows']['seed'])
    mean = np.linspace(.1, .2, 4*h)
    latent = rng.standard_normal((n, 3))
    loading = rng.standard_normal((3, 4*h))*.02
    innovation = rng.standard_normal((n, 4*h))
    for j in range(1, n):
        innovation[j] = .6*innovation[j-1]+.8*innovation[j]
    for components in plan['known_rows']['components']:
        for scale in plan['known_rows']['residual_scales']:
            rows = mean+latent@loading+scale*innovation
            model, statistics, residual, alternative = trace(rows, h, components)
            checks, exacts = [], []
            for order in range(h):
                exact, moments = exact_rho(residual[:, order])
                error = abs(exact-model['residual_rho'][order])
                assert error < plan['literal_moment_error_gate']
                bound = compare(residual[:, order], alternative[:, order])
                tampered = model['residual_rho'][order]+(-plan['tamper_delta'] if exact >= 0 else plan['tamper_delta'])
                assert abs(tampered-exact) > plan['literal_moment_error_gate']
                checks.append(dict(order=order+1, literal_error=error, tamper_rejected=True, **moments, **bound))
                exacts.append(exact)
            name = f'components{components}_scale{scale:g}'
            np.savez_compressed(a.out/(name+'.npz'), rows=rows, actual_residual=residual,
                                alternative_residual=alternative, literal_rho=model['residual_rho'], exact_rho=exacts)
            r['cases'].append(dict(name=name, statistics=statistics, harmonics=checks,
                                   original_alternative_gate_passed=all(v['exact_quotient_difference'] < 1e-9 for v in checks)))
    r.update(result='known_exact_moment_and_perturbation_controls_passed', cases_checked=8,
             primitive_checks=4, per_harmonic_checks=64, tamper_rejections=64,
             real_source_read=False, original_source_audit_relabelled=False,
             interpretation='Finite known cases plus exact algebraic containment for supplied arrays; no universal SVD/FFT forward-error or real timbre claim.')
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(dict(result=r['result'], original_projection_gates=[(v['name'], v['original_alternative_gate_passed']) for v in r['cases']]))
