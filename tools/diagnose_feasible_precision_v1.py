"""Inspect saved coarse dual support and lifted residuals, without resolving."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools'/x) for x in ('ipm_deps', 'qp_deps', 'python_deps')]
import numpy as np
import scipy.sparse as sp
from drive_evidence_v1.sources import sha


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def maximum(value): return float(abs(value).max())


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.feasible-coarse-precision/1', result='running', sources={}, cases=[],
    QP_rerun=False, nonlinear_estimator_rerun=False, truth_read=False, real_audio_read=False)
try:
    parent = args.workspace/'references/analysis/feasible_polish_v1/replay1'
    observed = load(parent/'report.json'); sources = {Path(__file__)}
    for name, digest in observed['sources'].items():
        assert sha(repo/name) == sha(parent/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        r['sources'][rel.as_posix()] = sha(path)
    r['parent_report_sha256'] = sha(parent/'report.json')
    for step in (5, 11, 12):
        folder = parent/f'step{step}'; a = np.load(folder/'input.npz')
        q = load(folder/'old_failed_QP.json')['coarse_attempt']
        g, gram, x = a['gradient'], a['gram'], a['initial']
        scale = q['objective_scale']; h = (gram+gram.T)/(2*scale); gn = g/scale
        dense, lower, upper = a['matrix'], a['lower'], a['upper']
        high, low = np.flatnonzero(np.isfinite(upper)), np.flatnonzero(np.isfinite(lower))
        rows = np.asfortranarray(np.r_[dense[high], -dense[low]]); bounds = np.r_[upper[high], -lower[low]]
        z = np.array(q['inequality_dual']); y = np.array(q['dual_solution'])
        slack = bounds-rows@x; contact = np.flatnonzero(slack <= 1e-9)
        keep = np.zeros(len(z), dtype=bool); keep[contact] = True
        # Keep the original CSC multiply for bitwise certificate replay;
        # the separate extended-precision dense expansion is independent.
        normal = h@x+gn; full = normal+sp.csc_matrix(dense).T@y
        assert maximum(full) == q['normalized_dual_stationarity']
        kept_force = rows[keep].T@z[keep]; omitted_force = rows[~keep].T@z[~keep]
        # Extended precision expands the exact stored lifted-coordinate
        # identity; it is not used to alter the original double certificate.
        root = np.linalg.qr(a['weighted'], mode='r')/np.sqrt(scale)
        aux, eq = np.array(q['auxiliary_solution']), np.array(q['equality_dual'])
        ld = np.longdouble
        rr, xx, aa, ee = root.astype(ld), x.astype(ld), aux.astype(ld), eq.astype(ld)
        hh, gg, yy, dd = h.astype(ld), gn.astype(ld), y.astype(ld), dense.astype(ld)
        terms = dict(lifted_stationarity=rr.T@ee+gg+dd.T@yy,
            gram_factor_product=(hh-rr.T@rr)@xx,
            equality_error=rr.T@(rr@xx-aa), auxiliary_error=rr.T@(aa-ee))
        reference = hh@xx+gg+dd.T@yy
        reconstructed = sum(terms.values())
        error = maximum(reference-reconstructed)
        magnitude = abs(hh)@abs(xx)+abs(gg)+abs(dd).T@abs(yy)
        operations = 8*(len(x)+len(z)+len(aux))
        gamma = operations*np.finfo(float).eps/(1-operations*np.finfo(float).eps)
        closure_bound = gamma*maximum(magnitude)
        assert error <= closure_bound
        result = dict(iteration=step, input_sha256=sha(folder/'input.npz'),
            original_coarse_status=q['status'], original_stationarity=maximum(full), objective_scale=scale,
            original_contact_tolerance=1e-9, original_contact_count=len(contact), inequalities=len(z),
            omitted_dual_force=maximum(omitted_force), kept_dual_force=maximum(kept_force),
            retained_native_duals_only_stationarity=maximum(normal+kept_force),
            original_full_duals_stationarity=maximum(full),
            maximum_omitted_multiplier=maximum(z[~keep]),
            minimum_omitted_slack=float(slack[~keep].min()),
            original_maximum_complementarity=q['maximum_complementarity'],
            lifted_residual_component_maxima={name:maximum(value) for name,value in terms.items()},
            extended_precision_stationarity=maximum(reference), algebraic_closure_error=error,
            conservative_double_forward_bound=closure_bound,
            original_certificate_changed=False, vectors_not_additive_scalar_energy=True)
        r['cases'].append(result); print(json.dumps(result), flush=True)
    r.update(result='all3_coarse_dual_support_and_lifted_residuals_decomposed',
        conclusion='Raw1e-9 near-contact selection discards dual forces needed for stationarity; feasibility alone does not repair precision. Native full dual also fails original stationarity. This is not evidence to increase contact tolerance or iterations.',
        next='Derive a primal-dual crossover or backward-accurate correction from the full saved coarse pair, with independent controls and original finite budget. Also inspect observed nonlinear convergence; do not select prefixes by truth.',
        original_dense_started=False, new_nonlinear_fit_permitted=False, full_goal_complete=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(args.out/'report.json', r)
