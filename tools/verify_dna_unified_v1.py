"""Actual C output: role isolation, complete recipe and exact lifecycle replay."""
from copy import deepcopy
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from vehicle_controller.native import Bridge,Engine
from vehicle_controller import recipe,take,dna_character
from vehicle_scenarios.start_idle import start_idle_lifecycle

def buffers(e,n):
    return np.ctypeslib.as_array(e.stems)[:n*e.bridge.channels()].copy().reshape(n,-1)

def source_variant(b,variant):
    pieces=[];mix=[];states=[]
    with Engine(b,0) as e:
        c=deepcopy(e.controls);c.update(mode=0,ignition=1,start_id=1,rpm=850.,load=0.,legacy_event_gain=0.)
        if variant in ('line_off','air_off'):c['dna']['line' if variant=='line_off' else 'air']=0.
        e.set(c)
        for i in range(630):
            if i==150:c.update(rpm=4000.,load=.8)
            if i==270:c.update(rpm=9500.,load=.8)
            if i==390:c.update(rpm=3000.,load=-.8)
            if i==510:c['ignition']=0
            if i in (150,270,390,510):e.set(c)
            mix.append(np.frombuffer(e.process(480),'<f4').copy().reshape(-1,2));pieces.append(buffers(e,480))
            if i%10==9:states.append(e.state())
    return np.concatenate(mix),np.concatenate(pieces),states

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    b=Bridge(Path(__file__).resolve().parents[1]);result=dict(schema='vsl.unified-dna-verification/1',abi=b.abi(),bridge_sha256=b.sha256,timbre_accepted=False)
    offset={};at=0
    for s in b.stems:offset[s['name']]=slice(at,at+s['channels']);at+=s['channels']
    mix,base,states=source_variant(b,'base');_,nol,_=source_variant(b,'line_off');_,noa,_=source_variant(b,'air_off')
    assert np.count_nonzero(nol[:,offset['dna']])==0
    assert np.count_nonzero(noa[:,offset['detail']])==0
    assert np.array_equal(base[:,offset['detail']],nol[:,offset['detail']])
    assert np.array_equal(base[:,offset['dna']],noa[:,offset['dna']])
    independent=[k for k in offset if k not in ('dna','detail')]
    for k in independent:assert np.array_equal(base[:,offset[k]],nol[:,offset[k]]) and np.array_equal(base[:,offset[k]],noa[:,offset[k]])
    reconstructed=np.zeros_like(mix,dtype=np.float64)
    for s in b.stems:
        part=base[:,offset[s['name']]]
        if s['channels']==2:reconstructed+=part
        else:reconstructed+=part*(1. if s['name']=='legacy_event' else 2**-.5)
    error=float(np.max(np.abs(reconstructed-mix)));assert error<2e-6,error
    # Each steady region must retain both roles, including high RPM. These are
    # engineering coordinates and audibility checks, not source RPM validation.
    windows={label:(int(x*48000),int(y*48000)) for label,x,y in
             [('idle',.9,1.4),('power',2.2,2.6),('high',3.4,3.8),('overrun',4.6,5.)]}
    result['role_rms']={}
    for label,(lo,hi) in windows.items():
        row={k:float(np.sqrt(np.mean(base[lo:hi,offset[k]].astype(float)**2))) for k in ('dna','detail')}
        assert min(row.values())>1e-6,(label,row);result['role_rms'][label]=row
    result.update(role_isolation=True,other_stems_unchanged=True,monitor_sum_max_error=error)
    c=b.initial(0)[0];c['dna'].update(line=.85,air=1.12,motion=.42)
    c['dna']['air_state']=[.8,1.,1.1,.85,.7,1.2]
    preset=recipe.create(b,0,c,'踏板驾驶',{});path=a.output/'Unified-DNA.vslpreset.json';take.save(path,preset)
    restored=json.loads(path.read_text(encoding='utf-8'));recipe.validate(b,restored);assert restored['control']==c
    planned,_=start_idle_lifecycle(b,0,c,{},b.startup_defaults,b.event_policy_defaults)
    # Real parameter automation within the shared lifecycle, preserving driving controls.
    events=planned['events'];extra=[]
    for second,key,value in ((12,'air',.9),(25,'line',.75)):
        frame=second*48000;previous=deepcopy(planned['initial'])
        for event in events:
            if event['frame']>frame:break
            previous=deepcopy(event['control'])
        previous['dna'][key]=value
        extra.append(dict(frame=frame,control=previous))
        for event in events:
            if event['frame']>frame:event['control']['dna'][key]=value
    planned['events']=sorted(events+extra,key=lambda x:x['frame']);take.save(a.output/'Full-flow.vsltake.json',planned)
    planned=take.read(a.output/'Full-flow.vsltake.json',b)
    def render(chunk):
        output=[];index=0;telemetry=[]
        with Engine(b,0) as e:
            e.set(planned['initial'])
            while e.frame<planned['frames']:
                pcm,index=take.replay_block(e,planned,index,chunk);output.append(pcm)
                if e.frame//48000!=(e.frame-len(pcm)//8)//48000:telemetry.append(e.state())
        return b''.join(output),telemetry
    first,telemetry=render(480);second,_=render(217);assert first==second
    audio=np.frombuffer(first,'<f4').reshape(-1,2);assert np.isfinite(audio).all()
    wavfile.write(a.output/'Full-flow.wav',48000,audio)
    result.update(preset_roundtrip=True,take_exact_across_chunks=True,frames=len(audio),
        pcm_sha256=hashlib.sha256(first).hexdigest(),peak=float(np.max(np.abs(audio))),telemetry=telemetry,
        excluded='No physical source separation, acoustic state calibration, MCPS or human timbre approval inferred.')
    assert telemetry[-1]['lifecycle']==0
    (a.output/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='telemetry'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
