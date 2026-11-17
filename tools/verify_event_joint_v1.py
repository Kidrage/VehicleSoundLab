"""Actual optional authoring, unchanged legacy behavior and V12 C material playback."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from author_event import author
from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.model import synth
from event_authoring.native import Renderer
from event_authoring.response_basis import calibrate_unit
from event_authoring.contour_joint import observations,fit
from event_designer.workspace import EventWorkspace
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    data=Path('E:/VehicleSoundLab/references/analysis');renderer=Renderer(repo);cases=[]
    for key,job in [('A',load(data/'startup_contour_v1/candidate1/analysis/input.job.json')),
                    ('B',load(data/'B_startup_context_v1/crank-hold-author1/input.job.json'))]:
        job.update(schema='vsl.event-authoring-job/6',envelope_fit='band-contour-v2',name=key+'启动 · 可靠频带联合包络候选')
        folder=out/key;folder.mkdir();save(folder/'job.json',job)
        result=author(folder/'job.json',folder/'analysis');assert result.get('status')!='analysis_only',result
        doc=load(folder/'analysis/profile.json');p=doc['parameters']
        assert p==load(data/'event_joint_v1/probe1'/key/'profile.json')
        if key=='B':assert [(c['low_hz'],c['high_hz']) for c in p['contours']]==[(4500,14000)]
        rows=[]
        for seed in (27431,48271,93931,17389):
            x,report=renderer.render(p,job['kind'],dict(seconds=1.2,hold_seconds=job['seconds'][1]-job['seconds'][0],seed=seed))
            y=synth(p,seed=seed,seconds=1.2,release_at=job['seconds'][1]-job['seconds'][0] if p['gated'] else None)
            y=np.pad(y,(0,len(x)-len(y)));error=float(np.max(abs(x-y)));assert error<3e-7
            sf.write(folder/f'C-{seed}.wav',x,48000,subtype='FLOAT');save(folder/f'C-{seed}.json',report)
            rows.append(dict(seed=seed,independent_model_error=error))
        if key=='B':
            for pitch,decay in ((.8,.7),(1.2,1.5)):
                x,_=renderer.render(p,'crank',dict(seconds=1.2,hold_seconds=.35,pitch=pitch,decay=decay))
                y=synth(p,seconds=1.2,release_at=.35,pitch=pitch,decay=decay);y=np.pad(y,(0,len(x)-len(y)))
                assert np.max(abs(x-y))<3e-7 and not np.any(x[18001:])
        cases.append(dict(key=key,parameters_sha256=sha(folder/'analysis/profile.json'),C=rows,
            contours=len(p['contours']),fit=doc['fit']['contour_fit']))
        print(key,'actual author and C passed',flush=True)
    # Old method remains reproducible; its documented B failure remains a refusal.
    old=load(data/'startup_contour_v1/candidate1/analysis/profile.json')
    save(out/'legacy-A.job.json',old['source_job']);author(out/'legacy-A.job.json',out/'legacy-A')
    assert load(out/'legacy-A/profile.json')['parameters']==old['parameters']
    bjob=load(data/'startup_contour_v1/regression1/B/input.job.json');save(out/'legacy-B.job.json',bjob)
    assert author(out/'legacy-B.job.json',out/'legacy-B')['status']=='analysis_only'
    assert load(out/'legacy-B/refused-fit.json')==load(data/'startup_contour_v1/regression1/B/refused-fit.json')
    # A prior tiny gain cannot silently make an available component unreachable.
    b=load(out/'B/analysis/profile.json');x,_,_=read(Path(b['source_job']['source']),*b['source_job']['seconds'])
    bg,_,_=read(Path(b['source_job']['source']),*b['source_job']['background_seconds']);_,arrays=observe(x,bg)
    variants=[]
    for amount in (1.,1e-20,0.):
        p=deepcopy(b['parameters'])
        for group in ('modes','bands'):
            for component in p[group]:component['amplitude']=amount
        p,r=calibrate_unit(p,arrays,len(x)/48000);assert r['qualified'];variants.append(p)
    assert variants[0]==variants[1]==variants[2]
    # Explicitly requested contour extraction refuses a source with no reliable upper band.
    t=np.arange(24000)/48000;rng=np.random.default_rng(19);background=rng.normal(0,.001,(24000,2))
    foreground=background+.05*np.sin(2*np.pi*187.5*t)[:,None]
    _,_,bands=observations(foreground,background);assert not any(b['selected'] for b in bands)
    _,a=observe(foreground,background)
    p,r,response=fit(b['parameters'],foreground,background,a);assert not r['qualified'] and response is None
    sf.write(out/'no-upper-contrast.wav',np.concatenate((background,foreground)),48000,subtype='FLOAT')
    import base64
    workspace=EventWorkspace(repo,out/'workspace')
    project=workspace.create(dict(filename='known.wav',audio=base64.b64encode((out/'no-upper-contrast.wav').read_bytes()).decode(),kind='crank'))
    # Fixture setup attaches a prior document to an audio project. This internal
    # attachment is not the public package-import path (tested by the browser).
    folder,current=workspace.load(project['id']);current['document']=deepcopy(b);workspace.commit(folder,current,'载入已保存对照')
    saved=workspace.save(dict(id=project['id'],name=b['name'],context=b.get('context',''),viewpoint='cabin'))
    rejected=workspace.analyze(dict(id=project['id'],seconds=[.5,1.],background_seconds=[0,.5],gated=True,
        response_fit='source-response-v1',envelope_fit='band-contour-v2'))
    assert rejected['analysis']['status']=='analysis_only' and rejected['document']==saved['document']
    frozen=Path('E:/VehicleSoundLab/baselines/startup_contour_v1/delivery1/evidence/verification1/exact_sources')
    runtime=[p for group in ('src','modules','voices') for p in (repo/group).rglob('*')
        if p.is_file() and (p.suffix in ('.c','.h') or group=='voices')]
    for p in runtime:assert sha(p)==sha(frozen/p.relative_to(repo)),str(p)
    save(out/'report.json',dict(result='passed',cases=cases,legacy_A_exact=True,legacy_B_refusal_exact=True,
        unit_basis_independent_of_prior_amplitude=True,no_reliable_upper_band_refused=True,
        refused_analysis_preserves_saved_document=True,runtime_and_voices_unchanged=len(runtime),
        author_bridge_sha256=renderer.identity,timbre_accepted=False))
    shutil.copy2(__file__,out/'executed_verification.py')


if __name__=='__main__':main()
