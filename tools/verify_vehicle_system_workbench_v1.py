"""One-file vehicle preset: native lifecycle/events, identity and replay."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import traceback
import numpy as np
from event_designer.workspace import EventWorkspace
from event_authoring.contract import KINDS
from sound_designer.workspace import Workspace
from sound_designer.state_recipes import StateRecipes
from vehicle_controller import recipe, take
from vehicle_controller.native import Bridge, Engine
from vehicle_scenarios.scenario import sport_lifecycle
from vehicle_scenarios.capture import capture, replay
from research_archive_v1 import sha, save, load
from verify_state_recipe_workbench_v1 import fixtures as dna_fixtures, refused, digest_tree


def fixtures(repo, output):
    workspace=Workspace(repo,output/'projects');store=StateRecipes(workspace);ids=dna_fixtures(workspace)
    event_workspace=EventWorkspace(repo,workspace.root/'events');event_ids={}
    for index,kind in enumerate(KINDS):
        profile=dict(gated=int(kind=='crank'),duration_seconds=.3,attack_seconds=.002,release_seconds=.02,
            sweep_seconds=0.,level=.2,modes=[dict(hz=120.+index*40,end_hz=120.+index*40,
            amplitude=.1,phase=0.,decay_seconds=.06)],bands=[])
        doc=dict(schema='vsl.event-profile/2',kind=kind,name='功能夹具 · '+kind,parameters=profile,
            viewpoint='exterior',physical_identity_confirmed=False,context='Artificial functional fixture, not measured engine sound.')
        event_ids[kind]=event_workspace.create(dict(package=doc))['id']
    settings=store.system.metadata()['defaults'];settings['events'].update(enabled=True,projects=event_ids)
    settings['startup'].update(crank_seconds=.3,flare_rpm=1800.)
    settings['policy'].update(afterfire_min_count=3,afterfire_max_count=3,
        afterfire_interval_min_seconds=.12,afterfire_interval_max_seconds=.12,afterfire_delay_seconds=.03)
    settings['layers']['intake_gain']=.1
    config=dict(name='整车参数功能夹具 · 非实车标定',groups=dict(base=[ids['base_low']],idle=[ids['idle']],
        power=[ids['power']],overrun=[ids['overrun']]),reference_rpm=3000.,transition_seconds=.12,
        detail=.65,seed=48271,system=settings)
    save(output/'fixture_ids.json',dict(dna=ids,events=event_ids))
    return workspace,store,config


def binding(repo,out):
    names=['tools/sound_designer/'+n for n in ('state_recipes.py','vehicle_system.py','server.py',
        'web/vehicles.html','web/vehicles.js','web/vehicles.css','web/vehicle_system.js')]
    names+=['tools/vehicle_controller/'+n for n in ('recipe.py','startup.py','event_policy.py','native.py','ui.py')]
    rows={}
    for name in names:
        target=out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,target);rows[name]=sha(target)
    save(out/'source_binding.json',rows)


def run(out):
    out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    shutil.copy2(__file__,out/'executed_verification.py');binding(repo,out)
    workspace,store,config=fixtures(repo,out);view=store.save(dict(id=None,configuration=config))
    path=workspace.root/view['preset'].removeprefix('/files/');value=load(path);bridge=Bridge(repo)
    assert value['schema']=='vsl.source-controller-preset/7'
    recipe.validate(bridge,value)
    assert set(value['event_overrides'])==set(KINDS) and value['startup_response']['flare_rpm']==1800
    assert value['event_policy']['afterfire_min_count']==value['event_policy']['afterfire_max_count']==3
    assert value['control']['intake_gain']==.1 and value['control']['legacy_event_gain']==0
    assert value['control']['events']['enabled']==1 and len(view['system_notes'])==7
    frozen=digest_tree(store.root);bad=[]
    for group,key,x in (('startup','flare_rpm',10000),('policy','afterfire_min_count',4),('layers','intake_gain',float('nan'))):
        q=deepcopy(config);q['system'][group][key]=x;bad.append(q)
    q=deepcopy(config);q['system']['events']['enabled']=1;bad.append(q)
    q=deepcopy(config);q['system']['events']['projects']['catch']=q['system']['events']['projects']['shift'];bad.append(q)
    for q in bad:
        refused(lambda:store.save(dict(id=view['id'],configuration=q)));assert digest_tree(store.root)==frozen
    # Changing an event project leaves the published sound and preset intact.
    event_path=workspace.root/'events'/config['system']['events']['projects']['catch']/'project.json'
    original=event_path.read_bytes();p=load(event_path);p['name']='edited after snapshot';save(event_path,p)
    assert store.view(view['id'])['changed_events']==[event_path.parent.name]
    assert digest_tree(store.root)==frozen;event_path.write_bytes(original)
    # Empty selections must silence the compiled reference events as well.
    empty=deepcopy(config);empty['system']['events']['projects']=dict.fromkeys(KINDS)
    quiet_view=store.save(dict(id=None,configuration=empty));quiet=load(workspace.root/quiet_view['preset'].removeprefix('/files/'))
    assert quiet['control']['events']['levels']==[0.]*7 and quiet['event_overrides']=={}
    with Engine(bridge,0,quiet['event_overrides'],quiet['startup_response'],quiet['event_policy'],quiet['dna_bank']) as engine:
        c=deepcopy(quiet['control']);c.update(ignition=1,start_id=1);engine.set(c)
        for _ in range(200):
            engine.process(480)
            channels=np.ctypeslib.as_array(engine.stems)[:480*23].reshape(480,23)
            assert np.count_nonzero(channels[:,19:])==0
    # All seven named event slots are exercised by the existing C driver.
    passage,scenario=sport_lifecycle(bridge,value['catalog'],value['event_overrides'],value['control'],
        value['startup_response'],value['event_policy'],value['dna_bank'])
    target=out/'lifecycle';target.mkdir();report,_,_=capture(bridge,passage,target)
    starts={kind:sum(n['action']==1 and n['type']==i for n in passage['source_events']) for i,kind in enumerate(KINDS)}
    assert all(starts.values()),starts
    assert starts['afterfire']==3 and report['final_state']['event_peak']<=4 and report['final_state']['lifecycle']==0
    restored=take.read(target/'lifecycle.vsltake.json',bridge);played=replay(bridge,restored)
    assert played['pcm_sha256']==report['pcm_sha256'] and played['source_events']==passage['source_events']
    assert played['final_state']==report['final_state'] and report['native_reconstruction_error']<2e-6
    tamper=deepcopy(value);tamper['event_policy']['afterfire_delay_seconds']=.1
    refused(lambda:recipe.validate(bridge,tamper))
    save(out/'vehicle.preset.json',value)
    for name,expected in load(out/'source_binding.json').items():assert sha(repo/name)==expected,name
    save(out/'report.json',dict(schema='vsl.vehicle-system-workbench-verification/1',result='passed',view=view,
        actual_32s_C_lifecycle=report,event_start_counts=starts,invalid_preserves_snapshot=len(bad),
        empty_event_selection_silences_compiled_candidates=True,event_source_drift_preserves_preset=True,
        variable_block_replay_PCM_events_state_exact=True,identity_tamper_refused=True,
        bridge_sha256=bridge.sha256,new_timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='passed',event_start_counts=starts)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    try:run(args.output)
    except Exception:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
