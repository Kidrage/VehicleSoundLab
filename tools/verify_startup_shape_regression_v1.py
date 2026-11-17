"""Known-envelope law and final authoring bytes, including sustained gating."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
from author_event import author
from event_authoring.model import synth
from event_authoring.temporal_fit import fit
from event_designer.package import write_json


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    root=Path('E:/VehicleSoundLab/references/analysis/startup_shape_v1')
    original=json.loads((root/'candidate2/analysis/profile.json').read_text(encoding='utf-8'))
    result=author(root/'candidate2/input.job.json',out/'real')
    assert result.get('status')!='analysis_only'
    current=json.loads((out/'real/profile.json').read_text(encoding='utf-8'))
    assert current['parameters']==original['parameters']
    assert current['fit']==original['fit']
    known=[]
    for gated in (0,1):
        truth=dict(gated=gated,duration_seconds=10. if gated else .8,attack_seconds=.01,
            release_seconds=.025,sweep_seconds=0.,level=.2,
            modes=[dict(hz=f,end_hz=f,phase=.2,amplitude=.2,attack_seconds=a,decay_seconds=1.1)
                for f,a in zip((150.,600.,2400.,8000.),(.08,.35,.004,.006))],
            bands=[dict(hz=f,q=.7,amplitude=0.,attack_seconds=.01,decay_seconds=.2)
                for f in (150.,600.,2400.,8000.)])
        x=synth(truth,seconds=.8)[:,None]
        initial=deepcopy(truth)
        for m in initial['modes']:m.pop('attack_seconds')
        fitted,report=fit(initial,x,np.zeros((57600,1)))
        attack=fitted['modes'][1]['attack_seconds'];assert abs(attack-.35)<.012,report
        if gated:assert fitted['modes'][1]['decay_seconds']==truth['modes'][1]['decay_seconds']
        else:assert abs(fitted['modes'][1]['decay_seconds']-1.1)<.1,report
        known.append(dict(gated=gated,known_mid_attack=.35,fitted_mid_attack=attack,report=report))
    write_json(out/'report.json',dict(result='passed',final_real_parameters_and_fit_exact=True,
        gated_crop_does_not_add_natural_release=True,known_slow_attacks=known,timbre_accepted=False))
    print(json.dumps(dict(result='passed',attacks=[r['fitted_mid_attack'] for r in known])),flush=True)


if __name__=='__main__':main()
