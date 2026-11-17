"""Try gain-only event response fitting without changing C, defaults or authoring policy."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from event_authoring.audio import read,sha
    from event_authoring.measure import observe,spectrum
    from event_authoring.response_fit import calibrate,EDGES
    from event_authoring.native import Renderer
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab');a.output.mkdir(parents=True,exist_ok=False)
    renderer=Renderer(repo);reports=[]
    for kind in ('crank','catch'):
        folder=a.output/kind;folder.mkdir()
        path=data/'references/analysis/event_authoring_v1'/(kind+'2')/'profile.json'
        document=json.loads(path.read_text(encoding='utf-8'));job=document['source_job']
        x,sr,origin=read(job['source'],*job['seconds']);bg,_,bg_origin=read(job['source'],*job['background_seconds'])
        assert origin==document['provenance'] and bg_origin==document['background']
        observation,arrays=observe(x,bg);duration=len(x)/sr
        fitted,policy=calibrate(document['parameters'],arrays,duration)
        candidate=deepcopy(document);candidate.update(parameters=fitted,response_fit=policy,
            status='gain-only response candidate; listening unaccepted')
        rows=[]
        for seed in (27431,1,20261116,19088743):
            y,render=renderer.render(fitted,kind,dict(seconds=duration,hold_seconds=duration,seed=seed))
            f,power=spectrum(y[:,None]);bands=[]
            for (lo,hi),target in zip(EDGES,policy['bands']):
                actual=float(power[(f>=lo)&(f<hi)].sum()*(f[1]-f[0]))
                bands.append(dict(hz=[lo,hi],error_db=float(10*np.log10(max(actual,1e-30)/max(target['target_power'],1e-30)))))
            rows.append(dict(seed=seed,bands=bands,render=render))
            sf.write(folder/('seed-'+str(seed)+'.wav'),y*.25,sr,subtype='FLOAT')
        (folder/'profile.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'fit.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2),encoding='utf-8')
        reports.append(dict(kind=kind,qualified=policy['qualified'],fit=policy,seeds=rows))
        print(json.dumps(dict(kind=kind,qualified=policy['qualified'],evaluations=policy['evaluations'],
            fit_db=[round(r['error_db'],2) for r in policy['bands']],
            seed27431_C_db=[round(r['error_db'],2) for r in rows[0]['bands']]),ensure_ascii=False),flush=True)
    exact=a.output/'exact_sources';exact.mkdir()
    for path in (Path(__file__),repo/'tools/event_authoring/response_fit.py'):shutil.copy2(path,exact/path.name)
    (a.output/'report.json').write_text(json.dumps(dict(cases=reports,goal_complete=False,timbre_accepted=False,
        C_changed=False,voice_bank_changed=False,renderer_sha256=renderer.identity),ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
