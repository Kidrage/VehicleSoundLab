"""Known constant-magnitude oscillators through the actual accepted time map."""
import numpy as np
from exterior_clock_v1.warp import render_positions
from .statistics import magnitudes,describe


def make(ridge,plan):
    rate=plan['sample_rate'];seconds=ridge['seconds'];frequency=ridge['window128']/5
    times=np.arange(round(seconds[0]*rate),round(seconds[-1]*rate)+1)/rate
    root=np.interp(times,seconds,frequency)
    cycles=np.r_[0,np.cumsum((root[1:]+root[:-1])/(2*rate))]
    count=int(cycles[-1]*1024)
    positions=np.interp(np.arange(count)/1024,cycles,times)
    source_times=np.arange(plan['known_clock_source_frames'])/rate
    nominal=np.interp(source_times,seconds,frequency)
    h=np.arange(1,plan['known_clock_harmonics']+1)
    amplitude=.015/(1+(h/12)**1.1)
    phase=.3*np.sin(h)+.07*h*h
    complex_weights=amplitude[:,None]*np.exp(1j*np.column_stack((phase,phase+.2*np.cos(h))))
    complex_weights[:,1]*=.8+.1*np.sin(h)
    rows=[];outputs=[]
    for error in plan['known_clock_relative_errors']:
        true=nominal*(1+error*np.sin(2*np.pi*plan['known_clock_error_hz']*source_times))
        phase_cycles=np.r_[0,np.cumsum((true[1:]+true[:-1])/(2*rate))]
        source=np.zeros((len(source_times),2))
        for order,weight in zip(h,complex_weights):
            source+=np.real(np.exp(2j*np.pi*order*phase_cycles)[:,None]*weight)
        normalized=render_positions(source,0.,positions,14000.)
        starts,z=magnitudes(normalized,len(h))
        error_db=20*np.log10(np.maximum(abs(z),1e-20)/abs(complex_weights)[None,:])
        row=dict(clock_fractional_error=error,
            source_fixed_magnitudes=True,output_frames=len(normalized),
            harmonic_magnitude_rms_error_db_LR=np.sqrt(np.mean(error_db**2,axis=(0,1))).tolist(),
            high_harmonic_magnitude_rms_error_db_LR=np.sqrt(np.mean(error_db[:,102:171]**2,axis=(0,1))).tolist(),
            observations=describe(normalized,plan['phase_observation_orders']))
        if error==0:
            expected=np.zeros_like(normalized)
            coordinate=phase_cycles[round(seconds[0]*rate)]+np.arange(count)/1024
            for order,weight in zip(h,complex_weights):
                expected+=np.real(np.exp(2j*np.pi*order*coordinate)[:,None]*weight)
            relative=float(np.sqrt(np.mean((normalized-expected)**2)/np.mean(expected**2)))
            row['waveform_relative_error']=relative
            assert relative<plan['tolerances']['known_exact_clock_waveform_error_relative'],relative
            assert max(row['harmonic_magnitude_rms_error_db_LR'])<plan['tolerances']['known_exact_clock_magnitude_error_db']
        rows.append(row);outputs.append(normalized)
    return rows,outputs,positions
