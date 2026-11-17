"""Independent every-native-piece replay and instance audit for exterior startup."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from research_archive_v1 import load,save,sha
from vehicle_controller import take
from vehicle_controller.native import Bridge,Engine


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.output/'executed_audit.py')
    repo=Path(__file__).resolve().parents[1]
    expected=load(args.evidence/'report.json');assert expected['result']=='passed'
    bridge=Bridge(repo);assert bridge.sha256==expected['bridge_sha256'] and bridge.channels()==23
    report=dict(result='running',goal_complete=False,timbre_accepted=False)
    results,captures={},{}
    try:
        for name in ('historical','early','pair25','full'):
            folder=args.evidence/name
            value=take.read(folder/'lifecycle.vsltake.json',bridge)
            native,rate=sf.read(folder/'native.wav',dtype='float32',always_2d=True)
            mix,_=sf.read(folder/'mix.wav',dtype='float32',always_2d=True)
            assert rate==48000 and native.shape==(value['frames'],23)
            pieces,monitor,notices=[],[],[]
            index=block=0;pattern=(1,1024,137,511,17,240,731)
            with Engine(bridge,value['catalog']['id'],value['event_overrides'],value['startup_response'],
                        value.get('event_policy'),value.get('dna_bank')) as engine:
                engine.set(value['initial'])
                process=engine.process
                def intercept(frames,solo=-1):
                    pcm=process(frames,solo)
                    pieces.append(np.ctypeslib.as_array(engine.stems)[:frames*23].reshape(frames,23).copy())
                    return pcm
                engine.process=intercept
                while engine.frame<value['frames']:
                    pcm,index=take.replay_block(engine,value,index,pattern[block%len(pattern)])
                    monitor.append(np.frombuffer(pcm,dtype='<f4').reshape(-1,2).copy())
                    notices.extend(engine.last_events);block+=1
                state=engine.state()
            assert np.array_equal(np.concatenate(pieces),native)
            assert np.array_equal(np.concatenate(monitor),mix)
            assert notices==value['source_events']
            wanted=expected['full']['final_state'] if name=='full' else expected['variants'][name]['measurement']['final_state']
            assert state==wanted
            active,ids,peak={},set(),0
            for row in notices:
                if row['action']==1:
                    assert row['reason']==0 and row['id'] not in ids and row['slot'] not in active
                    assert row['frame']==row['requested_frame']
                    active[row['slot']]=(row['id'],row['type']);ids.add(row['id']);peak=max(peak,len(active))
                else:
                    assert row['action']==2
                    assert row['reason']==0 or (row['reason']==1 and row['type']==1)
                    assert active.pop(row['slot'])==(row['id'],row['type'])
            assert not active and peak==state['event_peak']<=4
            assert all(state[k]==0 for k in ('event_rejected','event_overflow','event_log_lost'))
            captures[name]=dict(native=native,value=value,mix=mix)
            results[name]=dict(native_23channels_exact=True,monitor_exact=True,notices_state_exact=True,
                actual_native_process_calls=len(pieces),host_blocks=block,event_peak=peak,
                frames=value['frames'],peak=float(np.max(abs(mix))),take_sha256=sha(folder/'lifecycle.vsltake.json'))
            print(name,'every native piece,23channels,notices/state passed',flush=True)
        assert all(np.array_equal(captures[name]['native'][:,:19],captures['early']['native'][:,:19])
                   for name in ('historical','pair25'))
        equivalent=deepcopy(captures['pair25']['value'])
        for control in [equivalent['initial']]+[r['control'] for r in equivalent['events']]:control['events']['levels'][2]=0.
        for key in ('created','stream_id'):equivalent[key]=captures['early']['value'][key]
        assert equivalent==captures['early']['value']
        assert not np.array_equal(captures['pair25']['native'][:,19:],captures['early']['native'][:,19:])
        assert all(r['peak']<1 for r in results.values())
        bindings=load(args.evidence.parent/'selection1/runtime.json')
        assert len(bindings)==459 and all(sha(repo/name)==digest for name,digest in bindings.items())
        report.update(result='passed',captures=results,continuous_19channels_exact=True,
            catch_0_25_only_control_level_differs=True,runtime_voice_files_unchanged=459,
            source_only=True,no_clipping_at_fixed_preview_gain=True)
    except Exception as error:
        report.update(result='failed',error=repr(error));raise
    finally:save(args.output/'report.json',report)


if __name__=='__main__':main()
