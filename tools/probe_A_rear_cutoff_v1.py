"""Check whether final contour shapes change the source-noise cutoff choice."""
from copy import deepcopy
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from event_authoring.measure import observe
from event_authoring.contour_all_bands import observations
from event_authoring.contour_joint import shape_errors
from event_authoring.response_basis import calibrate_unit
from event_authoring.native import Renderer
from research_archive_v1 import load,save


def main():
    root=Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1')
    out=root/'cutoff-diagnosis1';out.mkdir(exist_ok=False)
    shutil.copy2(__file__,out/'executed_probe.py')
    x,_=sf.read(root/'selection1/later-original.wav',always_2d=True)
    b,_=sf.read(root/'selection1/background-original.wav',always_2d=True)
    _,arrays=observe(x,b);_,target,rows=observations(x,b)
    renderer=Renderer(Path(__file__).resolve().parents[1])
    doc=load(root/'catch3/profile.json');results=[]
    for cutoff in (0.,4000.,6000.,8000.,10000.,14000.):
        p=deepcopy(doc['parameters']);p['noise_lowpass_hz']=cutoff
        p,r=calibrate_unit(p,arrays,1.2)
        errors=shape_errors(p,target,1.2,[0,1,2,3])
        save(out/(str(int(cutoff))+'.json'),p)
        seeds=[]
        for seed in (27431,48271,93931,17389):
            c,_=renderer.render(p,'catch',dict(seconds=2.,seed=seed))
            f,power=__import__('event_authoring.measure',fromlist=['spectrum']).spectrum(c[:57600,None])
            measured=power[f<60].sum()*(f[1]-f[0])
            seeds.append(dict(seed=seed,low_db=float(10*np.log10(measured/r['bands'][0]['target_power']))))
        row=dict(cutoff=cutoff,response=r,shape=errors,seeds=seeds)
        results.append(row)
        print(cutoff,[(round(z['error_db'],3)) for z in r['bands']],errors,seeds,flush=True)
    save(out/'report.json',dict(results=results))


if __name__=='__main__':main()
