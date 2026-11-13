"""Compare saved blocking fractions under C/F memory layout, without solving."""
import argparse
import json
from pathlib import Path
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
args = p.parse_args()
sys.path[:0] = [str(args.workspace/'tools'/x) for x in ('ipm_deps', 'qp_deps', 'python_deps')]
import numpy as np
import scipy.sparse as sp
from interior_qp_v1.backend import inequalities

root = args.workspace/'references/analysis/feasible_polish_v1/replay1'
report = dict(schema='vsl.feasible-layout-diagnosis/1', QP_rerun=False, comparisons=[])
for step in (5, 11, 12):
    folder = root/f'step{step}'
    saved = np.load(folder/'input.npz')
    sparse, bounds, _, _ = inequalities(sp.csc_matrix(saved['matrix']), saved['lower'], saved['upper'])
    original = sparse.toarray()
    q = json.loads((folder/'new_QP.json').read_text(encoding='utf-8'))
    for row in q['active_set_polish']['history']:
        x = np.array(row['start']); direction = np.array(row['equality_minimum'])-x
        alphas = {}
        for label, matrix in (('original', original), ('C', np.array(original, order='C')), ('F', np.array(original, order='F'))):
            projected = matrix@direction; slack = bounds-matrix@x
            eligible = np.ones(len(bounds), dtype=bool); eligible[row['working_before']] = False
            eligible &= projected > 0
            fractions = np.full(len(bounds), np.inf)
            fractions[eligible] = np.maximum(0., slack[eligible])/projected[eligible]
            blocker = int(np.argmin(fractions))
            alphas[label] = dict(fraction=min(1., float(fractions[blocker])), blocker=blocker)
        report['comparisons'].append(dict(step=step, iteration=row['iteration'], saved=row['fraction'], layouts=alphas,
            original_matches=alphas['original']['fraction'] == row['fraction'],
            F_matches=alphas['F']['fraction'] == row['fraction'],
            C_matches=alphas['C']['fraction'] == row['fraction']))
assert all(row['original_matches'] and row['F_matches'] for row in report['comparisons'])
report.update(result='original_F_layout_recreates_all57_fractions_exactly',
    C_layout_bitwise_mismatch_count=sum(not row['C_matches'] for row in report['comparisons']),
    original_audit1_failure_retained=True, thresholds_changed=False)
args.out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='comparisons'}))
