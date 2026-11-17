"""Opt-in adaptive/fixed knot choice, with the original spectral/entry gates."""
from copy import deepcopy
from itertools import combinations
import numpy as np
from .contour_joint import fit as reference_fit,observations,shape_errors
from .contour_knots import fit_shape
from .response_basis import calibrate_unit
from .contract import validate


def fit(profile,x,background,arrays):
    reference,prior,response=reference_fit(profile,x,background,arrays)
    report=deepcopy(prior);report.update(method='band-contour-v3',reference_fit=prior)
    if not prior['qualified']:return reference,report,response
    duration=len(x)/48000;_,target,rows=observations(x,background)
    indices=[k+2 for k,r in enumerate(rows) if r['selected']]
    entry=prior['baseline_shape_rmse'];baseline=shape_errors(reference,target,duration,indices)
    weights=1/np.maximum(baseline,.05)
    def score(errors):return float(np.mean((np.array(errors)*weights)**2))
    attempts=[dict(name='fixed-reference',adaptive_indices=[],shape_rmse=baseline,
        qualified=True,temporal_nonregression=True,response=response,score=score(baseline))]
    candidates=[(score(baseline),0,deepcopy(reference),response)]
    # At most three non-empty subsets for the two eligible upper groups.
    for count in range(1,len(indices)+1):
        for adaptive in combinations(indices,count):
            p=deepcopy(reference)
            for step in range(2):
                p,shape=fit_shape(p,target,duration,rows,adaptive,weights)
                p,calibrated=calibrate_unit(p,arrays,duration)
                errors=shape_errors(p,target,duration,indices)
                temporal=all(a<=b+1e-10 for a,b in zip(errors,entry))
                qualified=bool(calibrated['qualified'] and temporal)
                index=len(attempts)
                attempts.append(dict(name='adaptive-'+','.join(map(str,adaptive))+'-'+str(step),
                    adaptive_indices=list(adaptive),shape=shape,shape_rmse=errors,response=calibrated,
                    temporal_nonregression=temporal,qualified=qualified,score=score(errors)))
                if qualified:candidates.append((score(errors),index,deepcopy(p),calibrated))
    _,choice,p,response=min(candidates,key=lambda row:(row[0],row[1]))
    report.update(selected_attempt=choice,attempts=attempts,qualified=True,
        fixed_reference_shape_rmse=baseline,adaptive_selected=choice!=0,
        policy='Retain qualified v2 fixed reference; for each nonempty subset of reliable upper groups, greedily place<=8 linear amplitude knots>=10ms apart, two amplitude-shape/spectral alternations. Fit/score normalized curves weighted by inverse max(v2 band RMSE,.05). Select lowest qualified score; original six spectral gates and per-band nonregression vs original band-attack entry unchanged. No extra runtime component or parameter capacity.',
        limitations='Time-shape tradeoffs against v2 remain possible and are reported per band. Only two upper groups, one fit seed and one crop; no mechanical timbre or source-separation claim. Coarse energy controls do not contain PCM, audio-rate envelopes or full fine structure.')
    return validate(p),report,response
