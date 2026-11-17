"""Optional method regression and an independent approved B gated-material trial."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import numpy as np
from author_event import author
from event_authoring.native import Renderer
from event_authoring.model import synth
from event_designer.workspace import EventWorkspace
from research_archive_v1 import load,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab/references/analysis')
    old=load(data/'startup_shape_v1/candidate2/analysis/profile.json')
    save(out/'legacy.job.json',old['source_job']);author(out/'legacy.job.json',out/'legacy')
    assert load(out/'legacy/profile.json')['parameters']==old['parameters']
    b=load(data/'B_startup_context_v1/crank-hold-author1/input.job.json')
    b.update(schema='vsl.event-authoring-job/5',envelope_fit='band-contour-v1')
    save(out/'B.job.json',b);result=author(out/'B.job.json',out/'B')
    bcheck=dict(extraction=result)
    if result.get('status')!='analysis_only':
        p=load(out/'B/profile.json')['parameters'];assert p['gated'] and len(p['contours'])==2
        renderer=Renderer(repo);rows=[]
        for pitch,decay in ((1,1),(.8,.7),(1.2,1.5)):
            x,report=renderer.render(p,'crank',dict(seconds=1.2,hold_seconds=.35,pitch=pitch,decay=decay))
            y=synth(p,seconds=1.2,release_at=.35,pitch=pitch,decay=decay)
            y=np.pad(y,(0,len(x)-len(y)));error=float(np.max(abs(x-y)))
            assert error<3e-7 and not np.any(x[round((.35+p['release_seconds'])*48000)+1:])
            rows.append(dict(pitch=pitch,decay=decay,max_error=error))
        bcheck.update(actual_C=rows,gated_release_checked=True)
    # A saved parameter document survives invalid input and short unsupported analysis.
    workspace=EventWorkspace(repo,out/'workspace')
    project=workspace.create(dict(package=load(data/'startup_contour_v1/candidate1/analysis/profile.json')))
    before=deepcopy(project['document']);bad=deepcopy(before['parameters']);bad['contours'][0]['seconds'][1]=0
    try:workspace.save(dict(id=project['id'],parameters=bad))
    except ValueError:pass
    else:raise AssertionError('Invalid contour saved')
    assert workspace.view(project['id'])['document']==before
    # Short-window rejection is explicit, rather than a silent contour fallback.
    from event_authoring.contour_fit import fit
    try:fit(before['parameters'],np.ones((3000,2))*.01,np.ones((3000,2))*.001)
    except ValueError as error:assert '16' in str(error)
    else:raise AssertionError('Too-short event accepted for contour fitting')
    save(out/'report.json',dict(result='passed',old_band_attack_parameters_exact=True,
        B_gated_material_trial=bcheck,invalid_profile_preserves_saved_document=True,
        short_contour_input_explicitly_refused=True,timbre_accepted=False))
    print(json.dumps(dict(result='passed',B_compiled=result.get('status')!='analysis_only')),flush=True)


if __name__=='__main__':main()
