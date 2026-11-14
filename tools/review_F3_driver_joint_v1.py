"""Publish one-driver joint budgets; comparisons are descriptive, not a preset."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'audit', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    m, audit = load(a.study / 'report.json'), load(a.audit / 'report.json')
    assert audit['result'] == 'independent_driver_joint_audit_passed'
    assert audit['producer_report_sha256'] == sha(a.study / 'report.json')
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out / 'executed_review.py')
    frozen = a.workspace / 'baselines/F3_joint_envelopes_v1/evidence/measure1'
    trace = lambda P: P.diagonal(axis1=-2, axis2=-1).real.sum(axis=-1)
    pc1 = lambda C: float(np.linalg.eigvalsh(C)[-1] / np.trace(C))
    observations, inputs = [], {}
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), layout='constrained')
    labels = ['3-6k', '6-8k', '8-10k', '10-14k']
    for i, selection in enumerate([10, 11]):
        rows = [r for r in m['cases'] if r['selection'] == selection]
        source_path = frozen / rows[0]['source_context'] / 'arrays.npz'
        assert sha(source_path) == m['inputs'][str(source_path)]
        inputs[str(source_path)] = sha(source_path)
        source = np.load(source_path)
        source_cov = source['affine_residual_covariance'][8:, 8:]
        source_power = trace(source['P']).mean(axis=0)
        source_color = 10 * np.log10(source_power[4:] / source_power[1:3].sum())
        native_pc1 = pc1(source_cov)
        x = np.arange(3)
        axes[i, 0].axhline(native_pc1, color='black', linestyle='--', label='Native source')
        axes[i, 0].bar(x - .17, [r['RAW_HF_PC1_fraction'] for r in rows], .34, label='Raw DNA')
        axes[i, 0].bar(x + .17, [r['HF_PC1_fraction'] for r in rows], .34, label='Canonical C')
        axes[i, 0].set(title=f'Context {i+1}: HF covariance PC1 share', ylabel='Fraction',
                       xticks=x, xticklabels=[str(r['seed']) for r in rows], xlabel='Seed', ylim=(0, 1))
        axes[i, 0].legend(fontsize=8)
        for row in rows:
            path = a.study / row['label'] / 'arrays.npz'
            assert sha(path) == row['arrays_sha256']
            inputs[str(path)] = sha(path)
            d = np.load(path)
            power = trace(d['P_canonical']).mean(axis=0)
            color = 10 * np.log10(power[4:] / power[1:3].sum())
            delta = source_cov - d['affine_residual_covariance'][8:, 8:]
            eig = np.linalg.eigvalsh(delta)
            assert abs(eig[0] - row['HF_covariance_difference_min_eigenvalue']) < 1e-10
            axes[i, 1].plot(labels, color - source_color, marker='o', label=str(row['seed']))
            axes[i, 2].plot(np.arange(1, 9), eig, marker='o', label=str(row['seed']))
            observations.append(dict(label=row['label'], selection=selection, seed=row['seed'],
                native_HF_PC1_fraction=native_pc1, raw_HF_PC1_fraction=row['RAW_HF_PC1_fraction'],
                canonical_HF_PC1_fraction=row['HF_PC1_fraction'],
                normalized_HF_color_C_minus_source_dB=(color-source_color).tolist(),
                HF_covariance_difference_eigenvalues_dB2=eig.tolist(),
                envelope_minmax=row['envelope_minmax'], envelope_log_range_dB=row['envelope_log_range_dB'],
                raw_enveloped_DNA_difference_FS=row['raw_enveloped_DNA_difference_FS'],
                synchronized_reconstruction=False))
        axes[i, 1].axhline(0, color='black', linewidth=.7)
        axes[i, 1].set(title='HF colour relative to 120-1200 Hz\nC minus native source', ylabel='dB')
        axes[i, 1].legend(title='Seed', fontsize=8)
        axes[i, 2].axhline(0, color='black', linewidth=.7)
        axes[i, 2].set(title='Literal eigenvalues: native minus C\nHF affine-residual covariance', xlabel='Sorted eigenvalue', ylabel='dB squared')
        axes[i, 2].legend(title='Seed', fontsize=8)
    for ax in axes.flat:
        ax.grid(alpha=.2)
    fig.suptitle('Two separate local banks through the original single BENCH driver (FREE_REV)\nNative and C trajectories differ: descriptive comparisons, not an additive deficit or a physical RPM/load law.')
    fig.savefig(a.out / 'local_driver_joint_budget.png', dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout='constrained')
    separate = []
    for ax, row in zip(axes, [r for r in m['cases'] if r['selection'] == 9]):
        path = a.study / row['label'] / 'arrays.npz'
        assert sha(path) == row['arrays_sha256']
        inputs[str(path)] = sha(path)
        d = np.load(path)
        total = trace(d['P_canonical']).mean(axis=0)
        fractions = [trace(d[key]).mean(axis=0)[4:] / total[4:]
                     for key in ['P_dna', 'P_other', 'signed_cross']]
        for j, (label, values) in enumerate(zip(['DNA', 'Other dry buses', 'Signed cross'], fractions)):
            ax.bar(np.arange(4) + (j-1)*.25, 100*values, .25, label=label)
        ax.axhline(0, color='black', linewidth=.7)
        ax.set(title=f"Separate pre-upshift recipe, seed {row['seed']}",
               xticks=np.arange(4), xticklabels=labels, ylabel='Fraction of canonical band power / %')
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
        separate.append(dict(label=row['label'], mean_HF_DNA_fraction=fractions[0].tolist(),
            mean_HF_other_fraction=fractions[1].tolist(), mean_HF_signed_cross_fraction=fractions[2].tolist(),
            raw_HF_PC1_fraction=row['RAW_HF_PC1_fraction'], canonical_HF_PC1_fraction=row['HF_PC1_fraction']))
    fig.suptitle('Existing stereo detail already contributes substantial HF power; keep the signed cross term\nThis single-anchor context is separate from both local banks; no detail transplant or room model.')
    fig.savefig(a.out / 'separate_detail_joint_budget.png', dpi=150)
    plt.close(fig)
    result = dict(schema='vsl.driver-joint-budget-observations/1', local=observations,
                  separate_preupshift=separate, synchronized_reconstruction=False,
                  additional_modulation_qualified=False, runtime_preset=False)
    save(a.out / 'observations.json', result)
    save(a.out / 'report.json', dict(result='one_driver_joint_budget_observations_published',
        producer_report_sha256=sha(a.study / 'report.json'), audit_report_sha256=sha(a.audit / 'report.json'),
        inputs=inputs, observations_sha256=sha(a.out / 'observations.json'),
        images={n: sha(a.out / n) for n in ['local_driver_joint_budget.png', 'separate_detail_joint_budget.png']},
        heard=False, runtime_or_model_changed=False))
    print(dict(result='one_driver_joint_budget_observations_published', local_cases=len(observations), separate_cases=len(separate)))


if __name__ == '__main__':
    main()
