"""Conditional subspace recovery, static coordinate invariance and counterexamples."""
import numpy as np
from .sideband_controls import fixtures
from .sideband_subspaces import observe
from .sidebands import observe as full_observe


def controls(rate=48000):
    t=np.arange(rate)/rate-.5;rows=[];rotation_error=0.;joint_error=0.;wrong_costs=[]
    for case in fixtures(rate):
        central=np.array([case['expected'][0]])
        waves,fits=observe(case['audio'],case['frequency'],case['chirp'],central,t)
        rotated,_=observe(case['audio'],case['frequency'],case['chirp'],central,t,rotation=.37)
        full,_=full_observe(case['audio'],case['frequency'],case['chirp'],t)
        joint_error=max(joint_error,float(abs(waves['joint']-full).max()))
        rotation_error=max(rotation_error,max(float(abs(waves[k]-rotated[k]).max()) for k in waves))
        target='amplitude' if case['id'] in ('am','independent_pair_equal_to_am') else ('quadrature' if case['id']=='quadrature' else 'joint')
        relative=float(np.linalg.norm(waves[target]-case['audio'])/np.linalg.norm(case['audio']))
        passed=relative<=1e-10 if case['exact_span'] else True
        if case['id']=='am':wrong_costs.append(fits['quadrature']['cost'])
        if case['id']=='quadrature':wrong_costs.append(fits['amplitude']['cost'])
        rows.append(dict(id=case['id'],passed=bool(passed),target_space=target,exact_span=case['exact_span'],
            target_relative_error=relative,costs={k:v['cost'] for k,v in fits.items()}))
    case=next(fixtures(rate));_,wrong=observe(case['audio'],case['frequency']+.5,case['chirp'],np.array([case['expected'][0]]),t)
    return dict(passed=all(r['passed'] for r in rows) and joint_error<=1e-10 and rotation_error<=1e-10 and all(c>0 for c in wrong_costs),
        cases=rows,joint_equivalence_error=joint_error,static_coordinate_rotation_error=rotation_error,
        wrong_subspace_costs=wrong_costs,half_native_bin_wrong_coordinate_costs={k:v['cost'] for k,v in wrong.items()},
        phase_estimator_run=False,physical_classifier_qualified=False)
