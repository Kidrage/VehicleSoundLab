"""Fixed A catch crop, optional temporal fit, actual C and independent model."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from author_event import author
from event_authoring.audio import sha
from event_authoring.native import Renderer
from event_authoring.model import synth
from event_designer.package import write_json,export
from inspect_startup_shape_v1 import curves,describe,EDGES


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    root=Path('E:/VehicleSoundLab/references/analysis/startup_shape_v1')
    old=json.loads((root/'diagnosis2/report.json').read_text(encoding='utf-8'))
    job=deepcopy(old['profile']['source_job']);job.update(schema='vsl.event-authoring-job/4',
        response_fit='source-response-v1',envelope_fit='band-attack-v1',name='A接火 · 分频起音候选')
    write_json(out/'input.job.json',job)
    result=author(out/'input.job.json',out/'analysis')
    write_json(out/'author-result.json',result)
    if result.get('status')=='analysis_only':print(json.dumps(result),flush=True);return
    doc=json.loads((out/'analysis/profile.json').read_text(encoding='utf-8'))
    renderer=Renderer(repo);generated=[]
    reference,rate=sf.read(out/'analysis/reference.wav',always_2d=True)
    sf.write(out/'reference-monitor.wav',reference*.25,rate,subtype='FLOAT')
    for seed in (27431,48271,93931,17389):
        values=dict(seconds=1.2,seed=seed);y,report=renderer.render(doc['parameters'],'catch',values)
        independent=synth(doc['parameters'],seed=seed,seconds=1.2)
        np.testing.assert_allclose(y[:len(independent)],independent,rtol=0,atol=3e-7)
        assert not np.any(y[len(independent):])
        folder=out/str(seed);folder.mkdir()
        sf.write(folder/'synthesis.wav',y,rate,subtype='FLOAT');sf.write(folder/'monitor.wav',y*.25,rate,subtype='FLOAT')
        t,power=curves(y[:len(reference)])
        export(folder,doc,dict(seconds=1.2,seed=seed,strength=1.,pitch=1.,decay=1.,texture=1.,hold_seconds=.8),report)
        generated.append(dict(seed=seed,renderer=report,bands=describe(t,power),
            python_C_max_error=float(np.max(abs(y[:len(independent)]-independent)))))
    write_json(out/'report.json',dict(result='passed',source=old['reference'],background=old['background'],
        old_profile_sha256=sha(root/'diagnosis2/report.json'),job=job,profile=doc,
        original_source_bands=old['source_bands'],old_C_bands=old['generated_bands'],
        generated=generated,band_edges=EDGES,timbre_accepted=False,goal_complete=False))
    shutil.copy2(__file__,out/'executed_build.py')
    print(json.dumps(dict(result='passed',output=str(out),fit=doc['fit']['temporal_fit'],
        source_response=doc['fit']['source_response_fit']['bands'],first_generated=generated[0]['bands'])),flush=True)


if __name__=='__main__':main()
