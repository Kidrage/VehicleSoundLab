"""Publish the rejected inverse and numerical-rank evidence without new audio."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/python_deps')]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha
from phase_score_budget_v1.rank import inspect


def load(path): return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.phase-score-budget-review/1', result='running', sources={},
    real_audio_read=False, model_exported=False, runtime_changed=False, full_qualification=False)
try:
    root = args.workspace/'references/analysis/phase_score_budget_v1'
    audit = load(root/'audit1/report.json'); rank = load(root/'rank1/report.json')
    assert audit['result'] == 'original_failure_and_allfive_rank_stages_independently_reproduced'
    paths = {Path(__file__)}
    for name, digest in audit['sources'].items():
        assert sha(repo/name) == sha(root/'audit1/exact_sources'/name) == digest
        paths.add(repo/name)
    for path in paths:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    # Supplemental predeclared fixed-rotation rank control. Does not change
    # the executed rank1 operator or claim its original controls contained it.
    matrix = np.eye(8)[:, :5]; c, s = np.cos(.37), np.sin(.37)
    rotated = np.r_[c*matrix[:4]-s*matrix[4:], s*matrix[:4]+c*matrix[4:]]
    rotated_result = inspect(rotated, [1, 3])
    rotation_ranks = [rotated_result[k] for k in ('nuisance_rank', 'conditional_phase_rank', 'full_rank')]
    assert rotation_ranks == [3, 2, 5]
    report['supplemental_fixed_rotation_rank_control'] = rotation_ranks
    arrays = np.load(root/'rank1/rank.npz'); energies = []
    figure, axes = plt.subplots(2, 1, figsize=(10.5, 7), layout='constrained')
    labels = dict(raw_samples='Raw samples', native='Native Hann bins', native_radial='Native + radial H',
        marginal='Marginal decorrelation', marginal_radial='Marginal + radial H')
    for stage in rank['stages']:
        name = stage['stage']; cutoff = stage['cutoff']
        full = arrays[name+'_full_singular']
        energy_error = abs(float(full@full)-stage['matrix_frobenius']**2)/stage['matrix_frobenius']**2
        assert energy_error <= 1e-12
        energies.append(dict(stage=name, spectral_Frobenius_Gram_mass_relative_error=energy_error))
        for axis, key in zip(axes, ('nuisance_singular', 'full_singular')):
            singular = arrays[name+'_'+key]
            axis.semilogy(np.arange(1, len(singular)+1), np.maximum(singular/cutoff, np.finfo(float).tiny),
                label=labels[name], linewidth=1.1)
    for axis in axes:
        axis.axhline(1, color='black', linestyle='--', linewidth=.8)
        axis.set(xlabel='Singular-value index', ylabel='Singular value / declared machine cutoff')
        axis.grid(alpha=.2); axis.legend(fontsize=8, loc='upper right')
    axes[0].set_title('All 648 angle/amplitude nuisance columns: full-rank inverse is rejected')
    axes[1].set_title('Full 732-column Jacobian: conditional block ranks cannot certify the joint model')
    figure.suptitle('Frozen fitted state: weak directions exist before the observation aperture')
    figure.savefig(args.out/'phase_score_rank.png', dpi=150); plt.close(figure)
    report.update(result='failed_profile_and_rank_evidence_published',
        reports_sha256={n: sha(root/n/'report.json') for n in ('diagnosis1', 'rank1', 'audit1')},
        spectral_Gram_mass_checks=energies, plot_sha256=sha(args.out/'phase_score_rank.png'),
        phase_response_calculated=False,
        limits=['Fixed numerical rank cutoff and current parameter units only, not physical identifiability',
            'Conditional phase rank84 is after truncating numerical nuisance span; joint ranks remain lower than naive sum',
            'No new phase correction, bounded inverse, uncertainty estimate, DNA, audio or listening result'])
    print(json.dumps(dict(result=report['result'], plot_sha256=report['plot_sha256'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
