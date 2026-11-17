"""Fixed A/B trial of reliable-band contours, with no runtime or default changes."""
import argparse
from copy import deepcopy
from pathlib import Path
from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.fit import fit
from event_authoring.temporal_fit import fit as temporal
from event_authoring.response_fit import search
from event_authoring.contour_joint import fit as joint
from event_authoring.native import Renderer
from research_archive_v1 import load,save
import soundfile as sf


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    data=Path('E:/VehicleSoundLab/references/analysis');renderer=Renderer(repo);cases=[]
    for key,job in [('A',load(data/'startup_contour_v1/candidate1/analysis/input.job.json')),
                    ('B',load(data/'B_startup_context_v1/crank-hold-author1/input.job.json'))]:
        folder=out/key;folder.mkdir();x,rate,source=read(Path(job['source']),*job['seconds'])
        bg,_,background=read(Path(job['source']),*job['background_seconds']);obs,arrays=observe(x,bg)
        p,_=fit(obs,arrays,len(x)/rate,job['gated']);p,_=temporal(p,x,bg);p,initial=search(p,arrays,len(x)/rate)
        assert initial['qualified'];p,report,response=joint(p,x,bg,arrays)
        save(folder/'profile.json',p);save(folder/'fit.json',report)
        for seed in (27431,48271,93931,17389):
            audio,metadata=renderer.render(p,job['kind'],dict(seconds=1.2,hold_seconds=len(x)/rate,seed=seed))
            sf.write(folder/f'C-{seed}.wav',audio,rate,subtype='FLOAT');save(folder/f'C-{seed}.json',metadata)
        cases.append(dict(key=key,source=source,background=background,initial_response=initial,fit=report))
        print(key,report['qualified'],[a['shape_rmse'] for a in report['attempts']],flush=True)
    save(out/'report.json',dict(cases=cases,runtime_changed=False,timbre_accepted=False))


if __name__=='__main__':main()
