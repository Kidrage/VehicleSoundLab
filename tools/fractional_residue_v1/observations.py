"""Compare finite-aperture phase to independent instantaneous phase truth."""
import numpy as np
from fractional_clock_v1.phase import project


def phase_residue(positions, time, truth_phase, cycle):
    residual = np.interp(positions,time,truth_phase)-np.arange(len(positions))/cycle
    residual -= np.median(residual)
    return residual


def residue_summary(positions, time, truth_phase, truth_frequency, cycle):
    residual=phase_residue(positions,time,truth_phase,cycle)
    equivalent_time=residual/np.interp(positions,time,truth_frequency)
    inferred=1/(cycle*np.diff(positions))
    frequency=np.interp((positions[1:]+positions[:-1])/2,time,truth_frequency)
    return dict(phase_residue_rms_cycles=float(np.sqrt(np.mean(residual**2))),
        phase_residue_p95_cycles=float(np.percentile(abs(residual),95)),
        time_residue_rms_us=float(np.sqrt(np.mean(equivalent_time**2))*1e6),
        time_residue_p95_us=float(np.percentile(abs(equivalent_time),95)*1e6),
        root_relative_p95=float(np.percentile(abs(inferred-frequency)/frequency,95)))


def line_power(audio,cycle,order):
    _,values,_=project(audio,cycle,[order],20,.25)
    return np.mean(abs(values[:,0])**2,axis=0)/2


def aperture(audio, positions, time, truth_phase, coordinate, phase_plan):
    cycle = coordinate['samples_per_coarse_cycle']
    orders = np.asarray(phase_plan['fit_orders'])
    starts, values, size = project(audio,cycle,orders,phase_plan['projection_cycles'],phase_plan['hop_coarse_cycles'])
    centers = starts+size/2
    at = np.interp(centers,np.arange(len(positions)),positions)
    residual = np.interp(at,time,truth_phase)-centers/cycle
    relative = values[:,:,0]*np.exp(-2j*np.pi*residual[:,None]*orders[None,:])
    # Remove a constant complex coefficient for each line. The remaining
    # angle is finite-aperture bias plus known interference, not RPM error.
    offsets = np.angle(relative.mean(axis=0))
    bias = np.angle(relative*np.exp(-1j*offsets[None,:]))/(2*np.pi*orders[None,:])
    return dict(source_seconds=at, point_residual_cycles=residual,
        aperture_bias_cycles=bias, orders=orders,
        rows=[dict(order=int(order),point_vs_aperture_p95_cycles=float(np.percentile(abs(bias[:,column]),95)),
            point_vs_aperture_maximum_cycles=float(abs(bias[:,column]).max()),
            relative_coherence=float(abs(relative[:,column].mean())/max(np.mean(abs(relative[:,column])),1e-30)))
            for column,order in enumerate(orders)])
