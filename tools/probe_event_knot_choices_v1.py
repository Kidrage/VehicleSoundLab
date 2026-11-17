"""Bounded A mixed fixed/adaptive contour layouts; do not replace the baseline."""
import argparse
from copy import deepcopy
from pathlib import Path
import numpy as np
from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.contour_joint import observations,shape_errors
from event_authoring.contour_knots import fit_shape
from event_authoring.response_basis import calibrate_unit
from research_archive_v1 import load,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    root=Path('E:/VehicleSoundLab/references/analysis');doc=load(root/'event_joint_v1/verification2/A/analysis/profile.json')
    job=doc['source_job'];x,rate,_=read(Path(job['source']),*job['seconds']);bg,_,_=read(Path(job['source']),*job['background_seconds'])
    _,arrays=observe(x,bg);duration=len(x)/rate;t,target,rows=observations(x,bg)
    baseline=shape_errors(doc['parameters'],target,duration,[2,3]);attempts=[]
    for indices in ([2],[3]):
        p=deepcopy(doc['parameters'])
        for step in range(2):
            p,shape=fit_shape(p,target,duration,rows,indices,1/np.maximum(baseline,.05));p,response=calibrate_unit(p,arrays,duration)
            errors=shape_errors(p,target,duration,[2,3]);name='adapt-'+str(indices[0])+'-'+str(step)
            save(out/(name+'.json'),p);attempts.append(dict(name=name,shape=shape,response=response,shape_rmse=errors))
            print(name,response['qualified'],baseline,errors,flush=True)
    save(out/'report.json',dict(baseline=baseline,attempts=attempts))


if __name__=='__main__':main()
