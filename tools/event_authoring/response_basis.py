"""Opt-in amplitude-independent fitting of the existing event components."""
from copy import deepcopy
from .response_fit import calibrate


def calibrate_unit(profile,arrays,duration):
    # Authoring only: each listed component is an available basis element.
    # Do not carry a prior tiny fitted coefficient into its new gain bound.
    p=deepcopy(profile);p['level']=1.
    for category in ('modes','bands'):
        for component in p[category]:component['amplitude']=1.
    fitted,report=calibrate(p,arrays,duration)
    report.update(basis_policy='Unit amplitudes for each existing listed mode/SOS, then original finite-response objective, cross-power, gain bounds, contract scaling and six spectral gates. No added frequencies or runtime components.')
    return fitted,report
