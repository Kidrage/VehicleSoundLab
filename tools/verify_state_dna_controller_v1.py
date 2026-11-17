"""V9 state DNA: native old/new regression, distinct states, owned replay/export."""
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
from vehicle_scenarios.capture import capture as capture_audio,replay
from sound_designer import models
from verify_event_policy_v1 import generate,refused
from startup_response_evidence_v1 import capture,verify,sha


def fixtures(repo,out):
    model,root=models.read(repo/'voices/dna_bank_v1/V10 Exterior.model')
    groups={}
    for name,low,high in (('base',0,0),('idle',2,-2),('power',0,2),('overrun',-1,-3)):
        p=models.controls(dict(gain_db=-8,low_db=low,high_db=high))
        path=out/(name+'.model');models.write(path,models.edit(model,root,p),root)
        groups[name]=[dna.anchor(path.read_text(encoding='ascii'),name+' · authored test')]
    base=dna.create(groups['base'],3000,'V10四状态设计示例 · 非实车状态标定',detail=.65)
    return base,dna.with_states(base,{key:groups[key] for key in dna.STATES},.12)


def sound(bridge,bank,load,seconds=5):
    chunks=[];states=[]
    with Engine(bridge,0,dna_bank=bank) as e:
        e.set(dict(e.controls,mode=0,rpm=3000.,load=load,ignition=1,start_id=1))
        for _ in range(round(seconds*100)):
            chunks.append(e.process(480));states.append(e.dna_state())
            a=np.ctypeslib.as_array(e.stems)[:480*bridge.channels()].reshape(480,-1)
            assert np.count_nonzero(a[:,2:])==0
        return b''.join(chunks),e.state(),states


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    shutil.copy2(__file__,out/'executed_verification.py')
    b=Bridge(repo);old=Bridge(repo,repo/'build-vehicle-source-v8/bin/Release/vsl_source_bridge.dll')
    assert (b.abi(),old.abi())==(9,8)
    binding=capture(repo,out,b.path);cases=[]
    def same(selection,c,changes,frames,label,overrides=None):
        x=generate(old,selection,deepcopy(c),changes,frames,overrides)
        y=generate(b,selection,deepcopy(c),changes,frames,overrides)
        assert x['pcm']==y['pcm'] and np.array_equal(x['native'],y['native']),label
        assert x['states']==y['states'] and x['notices']==y['notices'] and x['stats']==y['stats'],label
        cases.append(dict(label=label,selection=selection,frames=frames,pcm_sha256=hashlib.sha256(y['pcm']).hexdigest(),exact=True))
    for row in b.catalog:
        for enabled in (0,1):
            c=b.initial(row['id'])[0];c.update(mode=1,ignition=0,start_id=0,gear=0,automatic=0,throttle=0.,brake=.7)
            c['events']['enabled']=enabled
            same(row['id'],c,[(10013,dict(ignition=1,start_id=1)),(80017,dict(throttle=.35)),(120019,dict(ignition=0,throttle=0.))],153600,row['key']+'/events='+str(enabled))
        print(json.dumps(dict(default_exact=row['key'])),flush=True)
    for frame,decay in ((7200,1.),(21600,1.),(21733,4.)):
        c=b.initial(1)[0];c.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7);c['events'].update(enabled=1,decay=decay)
        same(1,c,[(frame,dict(ignition=0))],192000,'abort/'+str(frame))
    base,bank=fixtures(repo,out);take.save(out/'four-states.dnabank.json',bank)
    for load in (.5,-.3):
        assert sound(old,base,load)[0]==sound(b,base,load)[0],'Single-state V8 PCM changed'
    state_sounds=[]
    for load,index in ((.5,2),(-.3,3)):
        pcm,state,weights=sound(b,bank,load)
        assert weights[-1]['target'][index]==1 and weights[-1]['weight'][index]>.999
        assert all(abs(sum(x['weight'])-1)<2e-12 and min(x['weight'])>=0 for x in weights)
        assert abs(state['root_hz']-base['anchors'][0]['base_hz'])<1e-6
        # Use a donor that never occurs in this passage. An idle donor would
        # briefly sound during start settling and intentionally leave a fade.
        other='overrun' if load>0 else 'power'
        fallback=sound(b,dna.with_states(base,{other:bank['states'][other]}),load)
        original=sound(b,base,load)
        assert fallback[0]==original[0] and fallback[2][-1]['target']==[1.,0.,0.,0.]
        state_sounds.append(pcm[-48000*8:])
    assert state_sounds[0]!=state_sounds[1]
    with Engine(b,0,dna_bank=bank) as e:
        e.set(dict(e.controls,mode=0,rpm=850.,ignition=1,start_id=1))
        for _ in range(400):e.process(480)
        assert e.dna_state()['target']==[0.,1.,0.,0.] and e.dna_state()['weight'][1]>.999
    # Complete real source banks exercise distinct anchor grids and all 288 orders.
    real=dna.create([dna.read(repo/'voices/exterior_anchors_v1/A Stationary Lower Mid.model')],3782.663227718395,'A驻车多锚点合同核查',detail=.4)
    real=dna.with_states(real,{'power':[dna.read(repo/'voices/exterior_anchors_v1/A Stationary Upper Mid.model'),dna.read(repo/'voices/exterior_anchors_v1/A Stationary High.model')]})
    with Engine(b,0,dna_bank=real) as e:
        e.set(dict(e.controls,mode=0,rpm=5000.,load=.6,ignition=1,start_id=1))
        for _ in range(400):assert np.isfinite(np.frombuffer(e.process(480),dtype='<f4')).all()
        assert e.dna_state()['available_mask']==5 and e.dna_state()['weight'][2]>.999
    # Native ABI invalid configuration checks, independent of the Python validator.
    paths=(C.c_char_p*2)(*(str(out/'base.model').encode('utf-8') for _ in range(2)))
    for counts,seconds in (([0,1,0,0],.12),([1,0,0,0],.12),([1,9,0,0],.12),([1,1,0,0],float('nan')),([1,1,0,0],.01)):
        assert not b.open_state_dna(0,paths,(C.c_uint*4)(*counts),.02,93,12,seconds)
    invalid=[]
    for key,value in (('transition_seconds',float('nan')),('transition_seconds',True),('transition_seconds',.01),('states',{}),('states',{'unknown':bank['anchors']})):
        bad=deepcopy(bank);bad[key]=value;invalid.append(bad)
    bad=deepcopy(bank);bad['states']['power'][0]['sha256']='0'*64;invalid.append(bad)
    bad=deepcopy(bank);bad['states']['power']= [dna.read(repo/'voices/dna_bank_v1/Warm Additive.model')];invalid.append(bad)
    for bad in invalid:refused(lambda:dna.validate(bad))
    refused(lambda:Engine(old,0,dna_bank=bank));refused(lambda:take.create(old,0,old.initial(0)[0],dna_bank=bank))
    # Per-instance parameter ownership survives host data edits and temporary file removal.
    source=deepcopy(bank)
    with Engine(b,0,dna_bank=source) as e:
        source['states']['idle'][0]['model']='modified';assert e.dna_bank==bank
        assert e.dna_state()['available_mask']==15
    overrides={}
    for name in ('773ad53ffd964fa18a7abfaf4aa2821b','462af3cefda441aba34886ecfc96dbae'):
        doc=json.loads((Path('E:/VehicleSoundLab/designs/events')/name/'project.json').read_text(encoding='utf-8'))['document'];overrides[doc['kind']]=doc
    control=b.initial(0,bank)[0];control['events']['enabled']=1
    value,scenario=sport_lifecycle(b,0,overrides,control,dna_bank=bank)
    target=out/'lifecycle';target.mkdir();report,rows,transitions=capture_audio(b,value,target)
    reread=take.read(target/'lifecycle.vsltake.json',b);played=replay(b,reread)
    assert played['pcm_sha256']==report['pcm_sha256'] and played['final_state']==report['final_state'] and played['source_events']==value['source_events']
    assert report['final_state']['lifecycle']==0 and report['native_reconstruction_error']<2e-6
    document=recipe.create(b,0,control,'踏板驾驶',overrides,dna_bank=bank);recipe.validate(b,document);take.save(out/'four-states.recipe.json',document)
    assert document['schema']=='vsl.source-controller-preset/7' and value['schema']=='vsl.source-controller-take/8'
    for field in ('transition_seconds','states'):
        a,c=deepcopy(document),deepcopy(value)
        for doc in (a,c):
            if field=='states':doc['dna_bank']['states'].pop('idle')
            else:doc['dna_bank'][field]=.24
        refused(lambda:recipe.validate(b,a));path=out/(field+'.rejected.json');take.save(path,c);refused(lambda:take.read(path,b))
    result=export(b,value,out/'exports/state-driver')
    assert Path(result['paths'][0]).read_bytes()[44:]==(target/'mix.wav').read_bytes()[44:]
    assert result['source_events']==value['source_events']
    verify(repo,binding)
    result=dict(schema='vsl.state-dna-controller-verification/1',result='passed',abi=9,
        default_V8_exact=cases,single_state_V8_exact=True,state_selection=True,
        fixed_RPM_distinct_states=True,missing_state_base_PCM_exact=True,weights_sum_to_one=True,
        original_288_orders_distinct_anchor_grids=True,invalid_parameter_cases=len(invalid),
        invalid_native_cases=5,old_ABI_rejects_state_banks=True,owned_coefficients=True,
        lifecycle=report,scenario=scenario,variable_block_replay_exact=True,recipe_take_tamper_refused=True,
        dry_export_exact=True,bridge_sha256=b.sha256,old_bridge_sha256=old.sha256,
        voices_sha256=b.voices_sha256,new_timbre_accepted=False,goal_complete=False)
    take.save(out/'report.json',result);print(json.dumps(dict(result='passed',old_cases=len(cases))),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        import sys
        if '--output' in sys.argv:
            output=Path(sys.argv[sys.argv.index('--output')+1]);output.mkdir(parents=True,exist_ok=True)
            (output/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
