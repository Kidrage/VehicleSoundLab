"""Complex-source reconstruction of the four declared new known fixtures."""
import math
import numpy as np
from native_chirp_audit_v1.wave import near


def check(case,plan,audio,rows):
    if case=='crossing_pair':
        parameters=[(100.,16.,0.,.1,.1),(148.,-16.,0.,.1,.9)]
    else:
        parameters=[(f,f*.05*moving,f*.015*moving*(case=='cubic_control'),amp,phase)
            for f,moving,amp,phase in zip(plan['base_hz'],plan['moving'],plan['amplitude_L'],plan['phase_radians'])]
        if case=='missing_component_neighbor':parameters.append((199.7,0.,0.,.06,.4))
    t=np.arange(len(audio))/48000
    expected=np.zeros_like(audio)
    for k,(f,q,c,amp,phase) in enumerate(parameters):
        z=amp*np.exp(1j*(math.tau*f*t+math.pi*q*t*t+math.pi*c*t**3/3+phase))
        if case=='occluded_component' and k==5:z[60000:72000]=0
        if case=='missing_component_neighbor' and k==5:z[:]=0
        expected[:,0]+=z.real
        expected[:,1]+=(z*plan['right_gain']*np.exp(1j*plan['right_phase_radians'])).real
    error=near(audio,expected,2e-12)
    assert len(rows)==12
    for window,row in enumerate(rows):
        center=(window+.5)*.25
        assert len(row['lines'])==len(parameters) and row['success'] and row['diagnostic_only']
        for k,(line,(f,q,c,amp,phase)) in enumerate(zip(row['lines'],parameters)):
            near([line['frequency_hz'],line['chirp_hz_per_second'],line['curvature_hz_per_second2']],
                [f+q*center+c*center**2/2,q+c*center,c])
            theta=math.tau*(f*center+q*center**2/2+c*center**3/6)+phase
            near(line['phase_at_midpoint_LR'],[theta,theta+plan['right_phase_radians']])
            near(line['amplitude_LR'],[amp,amp*plan['right_gain']])
            visible=not(k==5 and (case=='missing_component_neighbor' or case=='occluded_component' and window==5))
            assert line['index']==k and line['visible']==line['eligible']==visible
    return error
