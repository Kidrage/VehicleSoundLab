"""V10 pre-start selector regression against preserved V9, not a sound approval."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_designer.package import write_json
from startup_response_evidence_v1 import capture as bind, verify
from vehicle_controller import recipe, take
from vehicle_controller.native import Bridge
from verify_event_policy_v1 import generate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args=p.parse_args();out=args.output;out.mkdir(parents=True, exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    current=Bridge(repo);old=Bridge(repo, repo/'build-vehicle-source-v9/bin/Release/vsl_source_bridge.dll')
    assert current.abi()==old.abi()==9
    assert old.sha256=='ccd3cef7340662a1f2986afa02b2e6af23bbac6dc333823a1a16c144323974e4'
    assert old.sha256!=current.sha256 and current.voices_sha256==old.voices_sha256
    binding=bind(repo, out, current.path)
    shutil.copy2(__file__, out/'executed_verification.py')
    exact=[];neutral=[]
    changes=[(10013, dict(ignition=1, start_id=1)), (80017, dict(throttle=.35)),
             (120019, dict(ignition=0, throttle=0.))]
    for row in current.catalog:
        for label, mode, auto, gear in [('automatic',1,1,0), ('manual-selected-1',1,0,1)]:
            control=current.initial(row['id'])[0]
            control.update(mode=mode, automatic=auto, gear=gear, ignition=0, start_id=0,
                           throttle=0., brake=.7)
            control['events']['enabled']=1
            x=generate(old,row['id'],deepcopy(control),changes,153600)
            y=generate(current,row['id'],deepcopy(control),changes,153600)
            assert x['pcm']==y['pcm'] and np.array_equal(x['native'],y['native']), (row,label,'PCM')
            assert x['states']==y['states'] and x['notices']==y['notices'] and x['stats']==y['stats'], (row,label,'state')
            exact.append(dict(catalog=row['key'], mode=label, frames=153600,
                              pcm_sha256=hashlib.sha256(y['pcm']).hexdigest(), exact=True))
        control=current.initial(row['id'])[0]
        control.update(mode=1, automatic=0, gear=0, ignition=0, start_id=0,
                       throttle=0., brake=.7)
        control['events']['enabled']=1
        y=generate(current,row['id'],control,[(10013,dict(ignition=1,start_id=1))],153600)
        assert all(state['gear']==0 and state['shifts']==0 and state['operating']==0 for state in y['states']),row
        assert all(state['speed_mps']==0. for state in y['states']),row
        assert y['states'][-1]['lifecycle']==4,row
        assert not [n for n in y['notices'] if n['type']==4 and n['action']==1],row
        neutral.append(dict(catalog=row['key'], stationary=True, shift_count=0,
                            no_shift_cut_or_recover=True, final_rpm=y['states'][-1]['rpm']))
        print(json.dumps(dict(catalog=row['key'],exact_modes=2,neutral_start_passed=True)),flush=True)
    for selection in (0, len(current.catalog)-1):
        control=current.initial(selection)[0]
        control.update(mode=0, automatic=0, gear=0, ignition=0, start_id=0, rpm=3500.,load=.3)
        x=generate(old,selection,deepcopy(control),changes,153600)
        y=generate(current,selection,deepcopy(control),changes,153600)
        assert x['pcm']==y['pcm'] and np.array_equal(x['native'],y['native'])
        assert x['states']==y['states'] and x['notices']==y['notices'] and x['stats']==y['stats']
        exact.append(dict(catalog=current.catalog[selection]['key'],mode='RPM-bench',frames=153600,exact=True))
    root=Path('E:/VehicleSoundLab/references/analysis/startup_handoff_v1')
    original,_=sf.read(root/'original1/native.wav',dtype='float32',always_2d=True)
    fixed,_=sf.read(root/'fixed1/native.wav',dtype='float32',always_2d=True)
    no_catch,_=sf.read(root/'no-catch1/native.wav',dtype='float32',always_2d=True)
    assert np.array_equal(original[:,19:],fixed[:,19:]),'Fix must not alter event parameters or PCM'
    assert np.array_equal(original[:61440],fixed[:61440]),'No audio difference before original RUNNING boundary'
    assert np.array_equal(original[:,:19],no_catch[:,:19]),'Event level must not change continuous voice'
    refusals=[]
    for label,action in [('old-preset',lambda:recipe.validate(current,json.loads((root/'original1/startup.recipe.json').read_text(encoding='utf-8')))),
                         ('old-take',lambda:take.read(root/'original1/lifecycle.vsltake.json',current))]:
        try:action()
        except ValueError as exc:refusals.append(dict(case=label,reason=str(exc)))
        else:raise AssertionError(label+' silently accepted another binary')
    verify(repo,binding)
    write_json(out/'report.json', dict(schema='vsl.startup-handoff-verification/1',result='passed',
        old_bridge_sha256=old.sha256,new_bridge_sha256=current.sha256,abi=9,
        exact_cases=exact,neutral_cases=neutral,old_documents_refused=refusals,
        event_pcm_exact=True,all_pcm_before_running_exact=True,event_does_not_change_continuous_pcm=True,
        voice_bank_sha256=current.voices_sha256,source_binding_verified=True,
        sound_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='passed',exact_cases=len(exact),neutral_cases=len(neutral),
                          new_bridge_sha256=current.sha256)),flush=True)


if __name__=='__main__':main()
