"""Independent quadrature, finite differences and unfitted stereo evidence."""
import numpy as np
from .fit import Model
from .fixtures import complex_ambiguity
from .forward import Aperture


def controls(plan):
    cycle=plan['samples_per_cycle']
    time=np.arange(round(plan['cycles']*cycle))/cycle
    operator=Aperture(len(time),plan)
    # Non-grid real tones exercise both positive and negative frequency images.
    signal=.19*np.cos(2*np.pi*1.43*time+.27)+.11*np.sin(2*np.pi*5.17*time-.4)
    fast=operator.apply(signal).reshape(len(operator.starts),-1)
    # Scalar global-time quadrature has no FFT/start-rotation dependency.
    window=np.sin(np.pi*np.arange(operator.size)/operator.size)**2
    error=0.
    for row in (0,1,len(operator.starts)//2,len(operator.starts)-1):
        start=operator.starts[row]
        for column,order in enumerate(operator.orders):
            direct=2*np.sum(signal[start:start+operator.size]*window*
                np.exp(-2j*np.pi*order*time[start:start+operator.size]))/window.sum()
            error=max(error,float(abs(direct-fast[row,column])))
    model=Model(time,plan)
    rng=np.random.default_rng(18401)
    parameters=np.zeros(model.parameter_count)
    parameters[:2*model.parts]=rng.normal(0,.025,2*model.parts)
    phase_slice=slice(2*model.parts,2*model.parts+model.phase_count)
    parameters[phase_slice]=rng.normal(0,.004,model.phase_count)
    parameters[phase_slice.stop:]=rng.normal(0,.015,model.parts*model.envelope_count)
    prediction,jacobian=model.prediction(parameters,True)
    derivatives=[]
    # Include individual coefficient/phase/envelope columns and a mixed direction.
    for label,index in [('cartesian',3),('phase',phase_slice.start+31),
                        ('envelope',phase_slice.stop+model.envelope_count+2),('mixed',None)]:
        direction=np.zeros(model.parameter_count)
        if index is None:
            direction=rng.normal(size=model.parameter_count)
            direction/=np.linalg.norm(direction)
        else:
            direction[index]=1
        step=1e-6
        measured=(model.prediction(parameters+step*direction)-model.prediction(parameters-step*direction))/(2*step)
        expected=jacobian@direction
        delta=float(np.linalg.norm(measured-expected)/max(np.linalg.norm(expected),1e-30))
        derivatives.append(dict(parameter=label,relative_error=delta))
    ambiguity=complex_ambiguity(time)
    assert ambiguity['maximum_phase_difference_cycles']>.01
    assert ambiguity['maximum_sample_difference']<1e-12
    return dict(forward_maximum_error=error,jacobian=derivatives,complex_envelope_ambiguity=ambiguity,
        parameter_count=model.parameter_count,phase_count=model.phase_count,envelope_count=model.envelope_count,
        passed=bool(error<=plan['rules']['maximum_forward_check_error'] and
            all(row['relative_error']<=plan['rules']['maximum_jacobian_relative_error'] for row in derivatives)))


def warp(audio,time,epsilon,plan):
    phase=time+epsilon
    if np.min(np.diff(phase))<=0:
        raise ValueError('Estimated coordinate is not monotonic')
    target=5+np.arange(round(30*plan['samples_per_cycle']))/plan['samples_per_cycle']
    if target[0]<phase[0] or target[-1]>phase[-1]:
        raise ValueError('Comparison would extrapolate')
    positions=np.interp(target,phase,time)
    return target,np.column_stack([np.interp(positions,time,audio[:,ch]) for ch in range(2)]),positions


def heldout(audio,time,plan):
    cycle=plan['samples_per_cycle']
    size=20*cycle
    window=np.sin(np.pi*np.arange(size)/size)**2
    rows=[]
    for start in range(0,len(time)-size+1,round(.25*cycle)):
        rows.append([2*np.sum(audio[start:start+size]*window[:,None]*
            np.exp(-2j*np.pi*order*time[start:start+size,None]),axis=0)/window.sum()
            for order in plan['heldout_orders']])
    coeff=np.asarray(rows)
    power=np.mean(abs(coeff)**2,axis=0)
    cross=np.mean(coeff[:,:,0]*coeff[:,:,1].conj(),axis=0)
    correlation=cross/np.maximum(np.sqrt(power[:,0]*power[:,1]),1e-30)
    return power,correlation


def assess(audio,time,truth,estimated,parameters,plan):
    interior=(time>=5)&(time<35)
    phase_error=estimated-truth
    phase_error-=np.median(phase_error[interior])
    point=float(np.percentile(abs(phase_error[interior]),95))
    truth_slope=1+np.gradient(truth,time)
    slope=1+np.gradient(estimated,time)
    root=float(np.percentile(abs(slope[interior]-truth_slope[interior])/truth_slope[interior],95))
    target,normalized,positions=warp(audio,time,estimated,plan)
    _,oracle,oracle_positions=warp(audio,time,truth,plan)
    power,corr=heldout(normalized,target,plan)
    oracle_power,oracle_corr=heldout(oracle,target,plan)
    power_error=float(abs(10*np.log10(np.maximum(power,1e-30)/np.maximum(oracle_power,1e-30))).max())
    corr_error=float(abs(corr-oracle_corr).max())
    count=len(plan['source_orders'])
    fitted_amplitude=np.hypot(parameters[:count],parameters[count:2*count])
    rules=plan['rules']
    separate=int(np.sum(fitted_amplitude>=rules['minimum_carrier_amplitude']))
    independent=int(np.sum(np.min(np.sqrt(power),axis=1)>=rules['minimum_carrier_amplitude']))
    qualified=bool(point<=rules['maximum_point_phase_p95_cycles'] and
        root<=rules['maximum_root_relative_p95'] and
        power_error<=rules['maximum_heldout_line_power_error_db'] and
        corr_error<=rules['maximum_heldout_complex_correlation_error'] and
        separate>=rules['minimum_separate_carriers'] and independent>=rules['minimum_separate_carriers'])
    return dict(point_phase_p95_cycles=point,root_relative_p95=root,
        maximum_heldout_power_error_db=power_error,maximum_heldout_complex_correlation_error=corr_error,
        fitted_separate_carriers=separate,heldout_supported_carriers=independent,
        fitted_carrier_amplitudes=fitted_amplitude.tolist(),heldout_powers=power.tolist(),
        oracle_heldout_powers=oracle_power.tolist(),qualified=qualified),positions,oracle_positions
