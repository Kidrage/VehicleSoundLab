"""Deliver material-derived editable events and an actual C full-cycle comparison."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_authoring.audio import sha
from event_designer.package import write_json
from startup_timbre_v1.projects import build
from startup_timbre_v1.review import build as review
from startup_response_evidence_v1 import capture as bind,verify
from vehicle_controller.native import Bridge
from vehicle_controller import recipe
from vehicle_scenarios.scenario import sport_lifecycle
from vehicle_scenarios.capture import capture,replay
from vehicle_scenarios.checks import inspect


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--review',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    bridge=Bridge(repo);binding=bind(repo,a.output,bridge.path)
    projects=build(repo,a.output/'projects',Path('E:/VehicleSoundLab/designs/events'))
    frozen=Path('E:/VehicleSoundLab/renders/exhaust_return_v1/cycle2/lifecycle.vsltake.json')
    original=json.loads(frozen.read_text(encoding='utf-8'));control=deepcopy(original['initial'])
    base=deepcopy(original['event_overrides']);updated=dict(base,**{r['kind']:r['document'] for r in projects['projects']})
    reports={};values={}
    for name,overrides in [('original',base),('candidate',updated)]:
        folder=a.output/name;folder.mkdir();value,scenario=sport_lifecycle(bridge,0,overrides,control,original['startup_response'])
        write_json(folder/'scenario.json',scenario)
        result,rows,transitions=capture(bridge,value,folder);replayed=replay(bridge,value)
        result.update(checks=inspect(bridge,value,result,rows,replayed),replay=replayed,
            bridge_sha256=bridge.sha256,voices_sha256=bridge.voices_sha256,timbre_accepted=False,goal_complete=False,
            event_profile_description='A crank/catch mixed-cabin candidates; E 1.2–14 kHz acoustic transient retained, not confirmed full-band afterfire.')
        write_json(folder/'verification.json',result)
        assert all(r['passed'] for r in result['checks']),result['checks']
        reports[name]=result;values[name]=value
    left,rate=sf.read(a.output/'original/native.wav',dtype='float32',always_2d=True)
    right,_=sf.read(a.output/'candidate/native.wav',dtype='float32',always_2d=True)
    event_offset=sum(r['channels'] for r in bridge.stems[:12])
    assert event_offset==19 and np.array_equal(left[:,:event_offset],right[:,:event_offset])
    assert values['original']['source_events']==values['candidate']['source_events']
    assert reports['original']['final_state']==reports['candidate']['final_state']
    assert not np.array_equal(left[:,event_offset:],right[:,event_offset:])
    # The E event at lift is intentionally unchanged; only startup event PCM changes.
    assert np.array_equal(left[3*rate:],right[3*rate:])
    preset=recipe.create(bridge,0,values['candidate']['initial'],'踏板驾驶',updated,original['startup_response'])
    recipe.validate(bridge,preset);write_json(a.output/'startup-candidate.recipe.json',preset)
    review(repo,a.output,a.review,projects)
    verify(repo,binding);shutil.copy2(__file__,a.output/'executed_build.py')
    result=dict(schema='vsl.startup-timbre-delivery/1',result='passed',bridge_sha256=bridge.sha256,
        voice_bank_sha256=bridge.voices_sha256,event_bank_mask=bridge.event_available_mask,
        projects=projects,full_cycle_reports=reports,continuous_19_channels_exact=True,
        event_schedule_and_final_state_exact=True,after_3_seconds_all_23_channels_exact=True,
        startup_candidate_changes_audio=True,recipe=str(a.output/'startup-candidate.recipe.json'),
        review=str(a.review),source_binding_sha256=sha(a.output/'source_binding.json'),
        timbre_accepted=False,goal_complete=False)
    write_json(a.output/'report.json',result)
    print(json.dumps(dict(result='passed',review=str(a.review),project_ids=[r['id'] for r in projects['projects']])),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        import sys,traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
