"""Extend independent analytic controls with known fifth-grid neighbours."""
import numpy as np
from multicarrier_clock_v1.fixtures import make as integer_fixture


def make(case, seconds):
    audio,t,phase,frequency = integer_fixture(case,seconds)
    kind = case['kind']
    if case.get('fractional',True) and kind not in ('single_carrier','noise_only'):
        for index, order in enumerate((1.4,2.4,3.4,4.4,5.4,7.4,1.8,2.2,2.8,3.2,4.8,5.2,6.8,7.2)):
            gain = .018*(1+.12*np.sin(2*np.pi*.61*t+.2*index))
            if kind=='all_carriers_gap':
                gain *= 1-np.exp(-((t-2.05)/.18)**8)
            angle = 2*np.pi*order*phase+.57*index
            audio[:,0] += gain*np.cos(angle)
            right_angle = angle+.11*order
            if kind=='stereo_delay':
                shifted = t-.0007
                shifted_phase = float(case['root_hz'])*shifted
                for depth,hz in ((.025,.6),(.012,1.9)):
                    shifted_phase += float(case['root_hz'])*depth*(1-np.cos(2*np.pi*hz*shifted))/(2*np.pi*hz)
                right_angle = 2*np.pi*order*shifted_phase+.57*index+.11*order
            audio[:,1] += .73*gain*np.cos(right_angle)
    # Separate fixed physical-Hz high detail, inside the14k source passband.
    # Its timewarp must follow the same measured map, not be regenerated at an
    # arbitrary new frequency or dropped by the old coarse-cycle lowpass.
    if kind not in ('single_carrier','noise_only','all_carriers_gap'):
        for hz,phase_offset in ((10811,.2),(12503,-.8),(13411,1.2)):
            audio[:,0] += .006*np.cos(2*np.pi*hz*t+phase_offset)
            audio[:,1] += .004*np.cos(2*np.pi*hz*(t-.0007)+phase_offset+.2)
        # Known high-order coherent carriers, in addition to the fixed-Hz
        # detail above. This makes phase-induced loss at low roots observable.
        for order in sorted(set(int(hz/max(frequency)) for hz in (12000,13500))):
            if order<=288:
                continue
            angle=2*np.pi*order*phase+.19*order
            audio[:,0]+=.008*np.cos(angle)
            audio[:,1]+=.006*np.cos(angle+.3)
    return audio,t,phase,frequency
