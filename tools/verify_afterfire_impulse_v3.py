"""Check the coefficient-only pressure preset with the unchanged production C."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from vehicle_controller.native import Bridge,Engine
from vehicle_controller.afterfire import defaults
from vehicle_controller import take
from event_authoring.export import c_profile
from verify_coast_afterfire_v20 import render
from tune_afterfire_impulse_v3 import metrics,render_events


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    b=Bridge(repo)
    assert b.sha256=='7fdda41236a97e6ec6c0833b8d0d7e608e095786ef6e525a4110d9782d5535f6'
    old=json.loads((repo/'presets/events/reference_afterfire_G_v2.json').read_text(encoding='utf-8'))
    c,f=b.initial(0);c,overrides,policy=defaults(b,0,c,f);new=overrides['afterfire']
    assert 'V3' in new['name']
    assert c_profile(new['parameters']) in (repo/'presets/events/reference_afterfire_G_v3.h').read_text(encoding='utf-8')
    before=render_events(b,old,c,policy);after=render_events(b,new,c,policy)
    rms=lambda x:float(np.sqrt(np.mean(x.astype(float)**2)))
    level_delta=20*np.log10(rms(after)/rms(before));assert abs(level_delta)<.001
    sf.write(a.output/'Previous-single-events.wav',before,48000,subtype='FLOAT')
    sf.write(a.output/'Pressure-single-events.wav',after,48000,subtype='FLOAT')
    # One-button burst, current policy, stored controls and exact variable-block replay.
    c.update(ignition=0,start_id=0,backfire=0)
    c['events'].update(manual_type=3,manual_sequence=1)
    manual=take.create(b,0,c,overrides,event_policy=policy);manual['frames']=2*48000
    m,ms,states,notices,_=render(b,manual)
    m2,s2,_,n2,_=render(b,manual,217)
    assert np.array_equal(m,m2) and np.array_equal(ms,s2) and notices==n2
    assert not np.any(ms[:,:19])
    started=[n for n in notices if n['action']==1];assert 6<=len(started)<=10
    assert not any(s['event_overflow'] for s in states)
    manual['source_events']=notices;take.save(a.output/'Pressure-burst.vsltake.json',manual)
    stored=take.read(a.output/'Pressure-burst.vsltake.json',b)
    with Engine(b,0,stored['event_overrides'],stored['startup_response'],stored['event_policy']) as e:
        e.set(stored['initial']);index=0;pieces=[]
        while e.frame<stored['frames']:
            pcm,index=take.replay_block(e,stored,index,min(313,stored['frames']-e.frame));pieces.append(pcm)
    assert b''.join(pieces)==m.tobytes()
    sf.write(a.output/'Pressure-burst.wav',m,48000,subtype='FLOAT')
    prior=deepcopy(manual);prior['event_overrides']={'afterfire':old};pm,_,_,_,_=render(b,prior)
    sf.write(a.output/'Previous-burst.wav',pm,48000,subtype='FLOAT')
    # Dense scheduling stays within the exact same four slots and 16-command queue.
    dense=deepcopy(manual);dense['event_policy'].update(afterfire_min_count=12,afterfire_max_count=12,
        afterfire_interval_min_seconds=.02,afterfire_interval_max_seconds=.02,afterfire_repeat_gain=1.3)
    dm,_,ds,_,_=render(b,dense)
    assert np.isfinite(dm).all() and max(s['event_peak'] for s in ds)<=4 and not any(s['event_overflow'] for s in ds)
    # Read the exact delivered V20 take, then replace only its event coefficients.
    baseline=take.read(Path('E:/VehicleSoundLab/references/analysis/coast_afterfire_v20/verification2/V20.vsltake.json'),b)
    updated=deepcopy(baseline);updated['event_overrides']={'afterfire':new}
    print('Checking unchanged 36 s continuous sources and driver',flush=True)
    old_mix,old_stems,old_states,old_notices,_=render(b,baseline)
    new_mix,new_stems,new_states,new_notices,_=render(b,updated)
    assert np.array_equal(old_stems[:,:19],new_stems[:,:19])
    for x,y in zip(old_states,new_states):
        for key in ('rpm','speed_mps','load','gain','lifecycle','operating','gear'):assert x[key]==y[key]
    assert np.array_equal(old_mix[:19*48000],new_mix[:19*48000])
    astarts=[(n['frame'],n['slot']) for n in new_notices if n['action']==1]
    bstarts=[(n['frame'],n['slot']) for n in old_notices if n['action']==1]
    assert astarts==bstarts
    assert np.isfinite(new_mix).all() and np.max(abs(new_mix))<1
    sf.write(a.output/'Pressure-coast.wav',new_mix[17*48000:25*48000],48000,subtype='FLOAT')
    sf.write(a.output/'Previous-coast.wav',old_mix[17*48000:25*48000],48000,subtype='FLOAT')
    report=dict(schema='vsl.afterfire-impulse-v3-verification/1',bridge_sha256=b.sha256,
        profile_sha256=hashlib.sha256((repo/'presets/events/reference_afterfire_G_v3.json').read_bytes()).hexdigest(),
        unchanged_kernel=True,modes=3,bands=2,voices=4,extra_filters=0,
        matched_single_event_group_rms_delta_db=level_delta,previous_metrics=metrics(before[:4800]),
        pressure_metrics=metrics(after[:4800]),first_19_seconds_exact=True,continuous_19_channels_exact=True,
        driver_and_master_gain_exact=True,trigger_times_and_slots_exact=True,manual_count=len(started),
        partition_217_480_exact=True,replay_313_exact=True,normal_peak_voices=max(s['event_peak'] for s in states),
        dense_peak_voices=max(s['event_peak'] for s in ds),queue_overflow=0,
        single_events_peak=float(np.max(abs(after))),burst_peak=float(np.max(abs(m))),
        full_flow_peak=float(np.max(abs(new_mix))),timbre_acceptance_pending=True)
    (a.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
