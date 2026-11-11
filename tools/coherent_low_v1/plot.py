"""Standalone measurement figure; the scores are not realism percentages."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def draw(output):
    evidence = json.loads((output / 'phase-evidence.json').read_text(encoding='utf-8'))
    x = np.array(evidence['harmonics'])
    coherent = np.mean(evidence['coherent_power_fraction_LR'], axis=1)
    null = np.mean(evidence['random_cycle_phase_null_95_percentile_LR'], axis=1)
    prediction = np.mean(evidence['contiguous_half_prediction_gain_LR'], axis=1)
    figure, axes = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True, layout='constrained')
    bars = axes[0].bar(x, coherent, color='#247887', label='Coherent power fraction')
    bars[4].set_hatch('///')
    bars[4].set_facecolor('#b1b6bb')
    axes[0].plot(x, null, 'o--', color='#a95c36', label='Random cycle phase: 95th percentile')
    axes[0].set(ylabel='Fraction', ylim=(0, 1.08), title='One exterior excerpt: 57 relative acoustic cycles')
    axes[0].legend(frameon=False, fontsize=9)
    axes[0].annotate('Tracking line: not independent evidence', xy=(5, coherent[4]), xytext=(2.1, 1.015), fontsize=8, arrowprops={'arrowstyle':'-', 'color':'#555'})
    axes[1].bar(x, prediction, color=['#247887' if value > 0 else '#a95c36' for value in prediction])
    axes[1].axhline(0, color='#777', linewidth=.8)
    axes[1].set(ylabel='Prediction gain vs zero', xlabel='Relative acoustic harmonic (not identified engine order)', xticks=x,
                title='Contiguous holdout: mean from first half predicts second half')
    figure.savefig(output / 'phase-evidence.png', dpi=160)
    plt.close(figure)
