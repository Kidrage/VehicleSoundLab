"""Bounded adaptive-knot study on the same approved A/B startup selections."""
import argparse
from copy import deepcopy
from pathlib import Path
import numpy as np
import soundfile as sf
from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.contour_joint import observations,shape_errors
from event_authoring.contour_knots import fit_shape
from event_authoring.response_basis import calibrate_unit
from event_authoring.native import Renderer
from research_archive_v1 import load,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    root=Path('E:/VehicleSoundLab/references/analysis');renderer=Renderer(repo);cases=[]
    for key in ('A','B'):
        folder=out/key;folder.mkdir();doc=load(root/f'event_joint_v1/verification2/{key}/analysis/profile.json')
        job=doc['source_job'];x,rate,_=read(Path(job['source']),*job['seconds']);bg,_,_=read(Path(job['source']),*job['background_seconds'])
        _,arrays=observe(x,bg);duration=len(x)/rate;t,target,rows=observations(x,bg)
        indices=[k+2 for k,r in enumerate(rows) if r['selected']]
        p=deepcopy(doc['parameters']);baseline=shape_errors(p,target,duration,indices);attempts=[]
        for step in range(2):
            p,shape=fit_shape(p,target,duration,rows);p,response=calibrate_unit(p,arrays,duration)
            errors=shape_errors(p,target,duration,indices)
            save(folder/f'profile-{step}.json',p)
            for seed in (27431,48271,93931,17389):
                audio,report=renderer.render(p,job['kind'],dict(seconds=1.2,hold_seconds=duration,seed=seed))
                sf.write(folder/f'C-{step}-{seed}.wav',audio,rate,subtype='FLOAT')
            attempts.append(dict(step=step,baseline_shape_rmse=baseline,shape_rmse=errors,shape=shape,response=response,
                temporal_nonregression=all(a<=b+1e-10 for a,b in zip(errors,baseline))))
            print(key,step,response['qualified'],baseline,errors,flush=True)
        cases.append(dict(key=key,attempts=attempts))
    save(out/'report.json',dict(cases=cases,runtime_changed=False,timbre_accepted=False))


if __name__=='__main__':main()
