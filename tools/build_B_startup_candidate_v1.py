"""Create an editable B-only startup texture and actual C envelope comparison."""
import argparse
import base64
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_authoring.audio import sha, read
from event_authoring.model import synth
from event_authoring.native import Renderer
from event_authoring.measure import spectrum
from event_designer.workspace import EventWorkspace
from research_archive_v1 import load, save
from startup_timbre_v1.projects import edit


def energy_times(wave):
    x=np.asarray(wave,dtype=float)
    if x.ndim==1:x=x[:,None]
    power=np.mean(x*x,axis=1);energy=np.cumsum(power)
    return dict(t10_t50_t90_seconds=[float(np.searchsorted(energy,q*energy[-1])/48000) for q in (.1,.5,.9)],
        quarter_mean_powers=[float(np.mean(a)) for a in np.array_split(power,4)],
        rms=float(np.sqrt(power.mean())))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workspace',type=Path,default=Path('E:/VehicleSoundLab/designs/events'))
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    work=data/'references/analysis/B_startup_context_v1';source=data/'references/clean/B_decoded_float.wav'
    original,sr,origin=read(source,12.,20.)
    assert origin['sha256']==load(repo/'references/segments_v1.json')['sources']['B']['master_sha256']
    assert any(r['id']=='B' and r['approved'] for r in load(data/'references/approval_manifest.json'))
    raw=a.output/'B_12_to_20_original.wav';sf.write(raw,original,sr,subtype='FLOAT')
    sf.write(a.output/'B_12_to_20_monitor.wav',original*.25,sr,subtype='FLOAT')
    workspace=EventWorkspace(repo,a.workspace)
    imported=dict(filename=raw.name,audio=base64.b64encode(raw.read_bytes()).decode(),viewpoint='cabin')
    cases=[];renderer=Renderer(repo)
    edges=((0,60),(60,300),(300,1200),(1200,4500),(4500,14000),(14000,24001))
    for name in ('crank-author1','crank-hold-author1'):
        document=load(work/name/'profile.json');job=document['source_job'];profile=document['parameters']
        x,_,_=read(source,*job['seconds']);bg,_,_=read(source,*job['background_seconds'])
        f,power=spectrum(x);fb,bp=spectrum(bg);excess=np.maximum(0,power-np.interp(f,fb,bp));df=f[1]-f[0]
        targets=[float(excess[(f>=lo)&(f<hi)].sum()*df) for lo,hi in edges]
        rows=[]
        for seed in (27431,1,20261117,19088743):
            values=dict(seconds=.95,hold_seconds=.75,seed=seed)
            wave,report=renderer.render(profile,'crank',values)
            reference=synth(profile,seed=seed,seconds=.95,release_at=.75 if profile['gated'] else None)
            expected=np.pad(reference,(0,len(wave)-len(reference)))
            error=float(np.max(abs(wave-expected)));assert error<1e-6
            frequency,generated=spectrum(wave[:len(x),None]);step=frequency[1]-frequency[0]
            bands=[dict(hz=[lo,hi],target_power=target,
                generated_power=float(generated[(frequency>=lo)&(frequency<hi)].sum()*step),
                error_db=float(10*np.log10(max(float(generated[(frequency>=lo)&(frequency<hi)].sum()*step),1e-30)/max(target,1e-30))))
                for (lo,hi),target in zip(edges,targets)]
            sf.write(a.output/f'{name}-seed{seed}-C.wav',wave,sr,subtype='FLOAT')
            rows.append(dict(seed=seed,C_vs_independent_python_max_error=error,bands=bands,
                temporal=energy_times(wave[:len(x)]),render=report))
        sf.write(a.output/(name+'-monitor.wav'),sf.read(a.output/f'{name}-seed27431-C.wav')[0]*.25,sr,subtype='FLOAT')
        cases.append(dict(name=name,profile=document,reference_temporal=energy_times(x),seeds=rows))
    held=cases[1]['profile']['parameters']
    released,release_report=renderer.render(held,'crank',dict(seconds=.95,hold_seconds=.35))
    expected=synth(held,seconds=.95,release_at=.35);expected=np.pad(expected,(0,len(released)-len(expected)))
    assert np.max(abs(released-expected))<1e-6 and not np.any(released[18000:])
    sf.write(a.output/'crank-interrupted-C.wav',released,sr,subtype='FLOAT')
    sf.write(a.output/'crank-interrupted-monitor.wav',released*.25,sr,subtype='FLOAT')
    # Analyze the SAME PCM through the user-facing workspace, not a hand-built document.
    project=workspace.create(dict(imported,kind='crank'))
    project=workspace.probe_context(dict(id=project['id'],seconds=[3.2,3.95],background_seconds=[.2,1.2],
        following_background_seconds=[6,7],context=cases[1]['profile']['context']))
    project=workspace.analyze(dict(id=project['id'],name='B Tecnica · 启动早期持续纹理候选',viewpoint='cabin',
        seconds=[3.2,3.95],background_seconds=[.2,1.2],gated=True,response_fit='source-response-v1',
        context=cases[1]['profile']['context']))
    assert project['document']['parameters']==held and project['reference_matches_model']
    project=workspace.render(edit(project));folder=workspace.root/project['id'];version=folder/project['last_version']
    shutil.copytree(version,a.output/'editable-crank')
    reimport=workspace.create(dict(package=load(version/'parameters.json')))
    reimport=workspace.render(edit(reimport))
    assert np.array_equal(sf.read(version/'synthesis.wav')[0],sf.read(workspace.root/reimport['id']/reimport['last_version']/'synthesis.wav')[0])
    # Retain the declared post-start reference and the refusal; do not replace it
    # with the quieter pre-start interval to make this catch candidate compile.
    diagnostic=workspace.create(dict(imported,kind='catch'))
    diagnostic=workspace.analyze(dict(id=diagnostic['id'],name='B Tecnica · 启动建立诊断（未通过）',
        seconds=[4,4.8],background_seconds=[6,7],gated=False,response_fit='source-response-v1',
        context=load(work/'catch-author1/input.job.json')['context']))
    assert diagnostic['analysis']['status']=='analysis_only' and not diagnostic['document'] and not diagnostic.get('last_version')
    assert abs(diagnostic['analysis']['event_to_background_db']-2.0867222544363497)<1e-10
    save(a.output/'report.json',dict(schema='vsl.B-startup-candidate/1',result='passed',source=origin,
        cases=cases,renderer_sha256=renderer.identity,interrupted_release=release_report,
        interrupted_silent_after_seconds=.375,editable_project_id=project['id'],editable_project=project,
        source_free_reimport_project_id=reimport['id'],source_free_reimport_PCM_exact=True,
        catch_diagnostic_project_id=diagnostic['id'],catch_refused=True,catch=diagnostic,
        direct_job_and_workbench_parameters_exact=True,monitor_gain=.25,
        physical_starter_or_combustion_separated=False,timbre_accepted=False,global_bank_changed=False,
        full_vehicle_recipe_changed=False,goal_complete=False))
    exact=a.output/'exact_sources'
    for name in ['tools/build_B_startup_candidate_v1.py','tools/inspect_event_timeline_v1.py',
        'research/B_startup_context_v1_setup.json','research/B_startup_context_v1_initial_fine.json',
        *[p.relative_to(repo).as_posix() for p in (repo/'tools/event_authoring').glob('*.py')],
        *[p.relative_to(repo).as_posix() for p in (repo/'tools/event_designer').glob('*.py')],
        *[p.relative_to(repo).as_posix() for p in (repo/'examples/event_authoring').glob('B_initial*.json')]]:
        dest=exact/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    print(dict(result='passed',project_id=project['id'],catch_diagnostic=diagnostic['id'],
        max_C_error=max(r['C_vs_independent_python_max_error'] for c in cases for r in c['seeds'])),flush=True)


if __name__=='__main__':main()
