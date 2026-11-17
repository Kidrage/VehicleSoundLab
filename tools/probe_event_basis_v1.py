"""Diagnose amplitude-dependent response fitting on the fixed A/B event crops."""
import argparse
from copy import deepcopy
from pathlib import Path
import numpy as np
import soundfile as sf
from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.model import synth
from event_authoring.response_fit import calibrate
from event_authoring.temporal_fit import band_curves
from event_authoring.contour_fit import fit as fit_contours
from research_archive_v1 import load,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    data=Path('E:/VehicleSoundLab/references/analysis');rows=[]
    for key,path,old_path,source,seconds,background in (
        ('A',data/'startup_contour_v1/candidate1/analysis/profile.json',data/'startup_shape_v1/candidate2/analysis/profile.json',
         'A_decoded_float.wav',[37.22,38.02],[35,36.2]),
        ('B',data/'startup_contour_v1/regression1/B/refused-fit.json',data/'B_startup_context_v1/crank-hold-author1/profile.json',
         'B_decoded_float.wav',[15.2,15.95],[12.2,13.2])):
        folder=out/key;folder.mkdir();doc=load(path);p=deepcopy(doc.get('parameters',doc));old=load(old_path)['parameters']
        x,rate,provenance=read(Path('E:/VehicleSoundLab/references/clean')/source,*seconds)
        bg,_,_=read(Path('E:/VehicleSoundLab/references/clean')/source,*background)
        _,arrays=observe(x,bg);t,raw=band_curves(x);_,background_power=band_curves(bg)
        target=np.maximum(raw-background_power.mean(axis=1)[:,None],0);scale=np.maximum(target.mean(axis=1),1e-15)
        def measure(profile):
            wave=synth(profile,seconds=len(x)/rate);_,power=band_curves(wave)
            return dict(normalized_curve_rmse=np.sqrt(np.mean(((power-target)/scale[:,None])**2,axis=1)).tolist(),
                        peak=float(np.max(abs(wave))))
        attempts=[dict(name='old-original',parameters=old,metrics=measure(old)),
                  dict(name='previous-contour',parameters=p,metrics=measure(p))]
        for step in range(3):
            reset=deepcopy(p);reset['level']=1.
            for kind in ('modes','bands'):
                for component in reset[kind]:component['amplitude']=1.
            p,response=calibrate(reset,arrays,len(x)/rate)
            entry=dict(name='unit-basis-'+str(step),parameters=deepcopy(p),response=response,metrics=measure(p))
            attempts.append(entry);print(key,entry['name'],response['qualified'],entry['metrics'],flush=True)
            save(folder/(entry['name']+'.json'),entry)
            sf.write(folder/(entry['name']+'.wav'),synth(p,seconds=len(x)/rate),rate,subtype='FLOAT')
            if step<2:p,contour=fit_contours(p,x,bg)
        save(folder/'attempts.json',attempts);rows.append(dict(key=key,source=provenance,attempts=attempts))
    save(out/'report.json',dict(result='diagnosed',cases=rows,runtime_changed=False,timbre_accepted=False))


if __name__=='__main__':main()
