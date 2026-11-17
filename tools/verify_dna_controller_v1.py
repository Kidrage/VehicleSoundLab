"""V8 authored workbench DNA -> native controller -> portable recipe/replay."""
import argparse
from copy import deepcopy
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import traceback
import numpy as np

from vehicle_controller.native import Bridge,Engine
from vehicle_controller import dna_bank as dna,recipe,take
from vehicle_controller.render import export
from vehicle_scenarios.scenario import sport_lifecycle
from vehicle_scenarios.capture import replay,capture as capture_audio
from sound_designer.workspace import Workspace
from sound_designer import models
from verify_event_policy_v1 import generate,refused
from startup_response_evidence_v1 import capture,verify,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    shutil.copy2(__file__,out/'executed_verification.py')
    bridge=Bridge(repo);old=Bridge(repo,repo/'build-vehicle-source-v7/bin/Release/vsl_source_bridge.dll')
    assert (bridge.abi(),old.abi())==(8,7)
    binding=capture(repo,out,bridge.path)
    extra={str(p.relative_to(repo)):sha(p) for p in (repo/'tools/sound_designer').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    take.save(out/'workbench-binding.json',extra)
    cases=[]
    def compare(selection,c,changes,frames,label,overrides=None):
        before=generate(old,selection,deepcopy(c),changes,frames,overrides)
        after=generate(bridge,selection,deepcopy(c),changes,frames,overrides)
        assert before['pcm']==after['pcm'] and np.array_equal(before['native'],after['native']),label
        assert before['states']==after['states'] and before['notices']==after['notices'] and before['stats']==after['stats'],label
        cases.append(dict(selection=selection,label=label,frames=frames,pcm_sha256=hashlib.sha256(after['pcm']).hexdigest(),exact=True))
    for row in bridge.catalog:
        for enabled in (0,1):
            c=bridge.initial(row['id'])[0];c.update(mode=1,ignition=0,start_id=0,gear=0,automatic=0,throttle=0.,brake=.7)
            c['events']['enabled']=enabled
            compare(row['id'],c,[(10013,dict(ignition=1,start_id=1)),(80017,dict(throttle=.35)),
                (120019,dict(ignition=0,throttle=0.))],153600,'normal/events='+str(enabled))
        print(json.dumps(dict(default_exact=row['key'])),flush=True)
    for frame,decay in ((7200,1.),(21600,1.),(21733,4.)):
        c=bridge.initial(1)[0];c.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7)
        c['events'].update(enabled=1,decay=decay)
        compare(1,c,[(frame,dict(ignition=0))],192000,'abort/'+str(frame))
    local=json.loads(Path('E:/VehicleSoundLab/designs/events/028a56d636574ab1bb902a1d3479ac7e/project.json').read_text(encoding='utf-8'))['document']
    c=bridge.initial(0)[0];c.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=.85,brake=0.);c['events']['enabled']=1
    compare(0,c,[(192000,dict(throttle=0.)),(240000,dict(throttle=.85)),(312000,dict(throttle=0.))],432000,'local-E/two-lifts',{'afterfire':local})

    workspace=Workspace(repo,out/'projects');banks=[];voices=[]
    for preset in ('v10','warm','hollow'):
        project=workspace.create(dict(preset=preset));ctl=dict(project['params'],detail=.61,high_db=1.,local=.7)
        result=workspace.driver_dna(dict(id=project['id'],name=preset+' authored',params=ctl,reference_rpm=3000))
        path=workspace.root/result['bank'].removeprefix('/files/');bank=dna.read(path)
        folder,p=workspace.load(project['id']);m,base=models.read(folder/'base.model');expected=models.edit(m,base,ctl)
        delivered,_=models.read(path.parent/'voice.model')
        assert all(np.array_equal(expected[k],delivered[k]) for k in m)
        assert bank['detail']==.61 and bank['anchors'][0]['sha256']==sha(path.parent/'voice.model')
        assert bank['root_per_rpm']==base/3000 and not list(path.parent.glob('*.wav'))
        with Engine(bridge,0,dna_bank=bank) as engine:
            assert engine.features==0 and engine.controls['detail']==.61 and engine.controls['events']['enabled']==0
            for key in ('legacy_event_gain','low_mix','coherent_low_gain','resonant_gain','residual_gain','idle_mix','idle_motion','idle_detail',
                        'startup_gain','catch_gain','intake_gain','mechanical_gain','air_gain','road_gain','wind_gain'):
                assert engine.controls[key]==0,key
            engine.set(dict(engine.controls,mode=0,rpm=3000.,ignition=1,start_id=1))
            chunks=[];native=[]
            for _ in range(400):
                chunks.append(engine.process(480));native.append(np.ctypeslib.as_array(engine.stems)[:480*bridge.channels()].copy().reshape(480,-1))
            audio=b''.join(chunks);stems=np.concatenate(native);assert np.any(stems[:,:2])
            assert np.count_nonzero(stems[:,2:])==0,'Unrelated optional layers leaked'
            assert abs(engine.state()['root_hz']-base)<1e-6 and engine.state()['coverage']==0
            voices.append(hashlib.sha256(audio).hexdigest())
        banks.append(bank);take.save(out/(preset+'.dnabank.json'),bank)
    assert len(set(voices))==3
    bank=banks[0]
    # Source-independent import: erase only this test's generated model delivery.
    owned=out/'detached.dnabank.json';take.save(owned,bank);detached=dna.read(owned)
    detached['name']='Detached model';assert dna.digest(detached)!=dna.digest(bank)
    bankcopy=deepcopy(bank)
    with Engine(bridge,0,dna_bank=bankcopy) as e:
        bankcopy['anchors'][0]['model']='mutated';assert e.dna_bank==bank

    invalid=[]
    for key,value in (('seed',0),('seed',2**64),('seed',True),('root_per_rpm',float('nan')),('root_per_rpm',.11),
                      ('align_orders',33),('detail',1.01),('detail',True),('name',''),('anchors',[]),('anchors',bank['anchors']*9)):
        invalid.append(dict(bank,**{key:value}))
    for key,value in (('sha256','0'*64),('base_hz',99),('harmonics',True),('model',bank['anchors'][0]['model']+' junk')):
        bad=deepcopy(bank);bad['anchors'][0][key]=value;invalid.append(bad)
    bad=deepcopy(bank);bad['anchors']*=2;invalid.append(bad)
    for value in invalid:refused(lambda:dna.validate(value))
    refused(lambda:Engine(old,0,dna_bank=bank))
    raw=out/'raw.model';raw.write_bytes(bank['anchors'][0]['model'].encode('ascii'));paths=(C.c_char_p*1)(str(raw).encode('utf-8'))
    for selection,count,ratio,seed,align in ((-1,1,.02,1,0),(0,0,.02,1,0),(0,9,.02,1,0),(0,1,float('nan'),1,0),(0,1,.11,1,0),(0,1,.02,0,0),(0,1,.02,1,33)):
        assert not bridge.open_dna(selection,paths,count,ratio,seed,align)
    assert not bridge.open_dna(0,None,1,.02,1,0)
    raw.write_bytes(b'invalid');assert not bridge.open_dna(0,paths,1,.02,1,0);raw.unlink()
    # Two parameter anchors exercise the shared atlas and out-of-range reporting.
    first=deepcopy(banks[1]['anchors'][0]);tokens=first['model'].split();tokens[7]=str(first['base_hz']*1.2)
    second=dna.anchor(' '.join(tokens)+'\n','Second synthetic fixture anchor')
    multi=dna.create([first,second],3000,'Two-anchor fixture')
    with Engine(bridge,0,dna_bank=multi) as e:
        e.set(dict(e.controls,mode=0,rpm=3300.,ignition=1,start_id=1))
        for _ in range(400):e.process(480)
        assert e.state()['coverage']==0
        e.set(dict(e.controls,rpm=8000.))
        for _ in range(400):e.process(480)
        assert e.state()['coverage']==1
    take.save(out/'two-anchors.dnabank.json',multi)
    # A parameter-only voice drives the full lifecycle, controls and exports.
    control=bridge.initial(0,bank)[0];control['events']['enabled']=1
    value,scenario=sport_lifecycle(bridge,0,control=control,dna_bank=bank)
    target=out/'lifecycle';target.mkdir();rendered,rows,transitions=capture_audio(bridge,value,target)
    reread=take.read(target/'lifecycle.vsltake.json',bridge);played=replay(bridge,reread)
    assert played['pcm_sha256']==rendered['pcm_sha256'] and played['source_events']==value['source_events']
    assert played['final_state']==rendered['final_state']
    document=recipe.create(bridge,0,control,'踏板驾驶',{},dna_bank=bank);recipe.validate(bridge,document)
    take.save(out/'authored.recipe.json',document)
    for field in ('missing','sha256','map','detail','model'):
        a,b=deepcopy(document),deepcopy(value)
        for doc in (a,b):
            if field=='missing':del doc['dna_bank']
            elif field=='map':doc['dna_bank']['root_per_rpm']*=.9
            elif field=='detail':doc['dna_bank']['detail']=.3
            elif field=='sha256':doc['source_effective_sha256']='0'*64
            else:doc['dna_bank']['anchors'][0]['model']+=' junk'
        refused(lambda:recipe.validate(bridge,a));path=out/(field+'.rejected.json');take.save(path,b);refused(lambda:take.read(path,bridge))
    # Complete identity changes even with an otherwise valid alternate bank.
    assert recipe.create(bridge,0,control,'踏板驾驶',{},dna_bank=banks[1])['source_effective_sha256']!=document['source_effective_sha256']
    oldvalue=take.create(old,0,old.initial(0)[0]);oldvalue['frames']=480;take.save(out/'legacy.vsltake.json',oldvalue)
    assert take.read(out/'legacy.vsltake.json',old)==oldvalue;refused(lambda:take.read(out/'legacy.vsltake.json',bridge))
    paths=export(bridge,value,out/'exports/driver')['paths']
    assert Path(paths[0]).read_bytes()[44:]==(target/'mix.wav').read_bytes()[44:]
    verify(repo,binding)
    assert all(sha(repo/path)==expected for path,expected in extra.items())
    report=dict(schema='vsl.dna-controller-verification/1',result='passed',abi=8,default_V7_exact=cases,
        authored_voices_pcm=voices,workbench_edited_coefficients_exact=True,no_inherited_optional_layers=True,
        parameter_only_recipe=True,invalid_contract_cases=len(invalid),native_invalid_constructor_cases=9,
        copied_ownership=True,multi_anchor_coverage=True,lifecycle=rendered,scenario=scenario,
        variable_block_replay_exact=True,recipe_take_tamper_refused=True,legacy_V7_uses_original_binary=True,
        export_mix_exact=True,bridge_sha256=bridge.sha256,old_bridge_sha256=old.sha256,voices_sha256=bridge.voices_sha256,
        new_timbre_accepted=False,goal_complete=False)
    take.save(out/'report.json',report);print(json.dumps(dict(result='passed',cases=len(cases),voices=len(voices))),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        import sys
        if '--output' in sys.argv:
            output=Path(sys.argv[sys.argv.index('--output')+1]);output.mkdir(parents=True,exist_ok=True)
            (output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
