"""Independent known rapid phase, never an initializer or estimator argument."""
import numpy as np


def assessment_phase(time):
    phase = .045*np.exp(-((time-19)/1.2)**2)-.03*np.exp(-((time-21)/.9)**2)
    return phase-phase[0]


def observed(plan):
    time = np.arange(round(plan['cycles']*plan['samples_per_cycle']))/plan['samples_per_cycle']
    # The independent source generator uses its own analytic phase; callers
    # receive samples only. Evaluation requests the phase after estimation.
    phase = assessment_phase(time); audio = np.zeros((len(time), 2))
    for k, order in enumerate(plan['source_orders']):
        amplitude = .045 if order in (2, 3, 5, 7) else .022*(1+.15*np.cos(.31*k))
        envelope = 1+.06*np.sin(2*np.pi*(.024+.0002*k)*time+.19*k)
        angle = 2*np.pi*order*(time+phase)+.37*order+.013*order**2
        audio += amplitude*envelope[:, None]*np.column_stack((np.cos(angle), .82*np.cos(angle+.17+.021*order)))
    return time, audio
