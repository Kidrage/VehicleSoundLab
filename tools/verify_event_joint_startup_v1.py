"""Put the new authored catch into the unchanged V12 complete startup generator."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from vehicle_controller.native import Bridge
from startup_handoff_v1.session import generate
from startup_response_evidence_v1 import capture,verify
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-preset',type=Path);parser.add_argument('--candidate',type=Path)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis')
    bridge=Bridge(repo);assert bridge.abi()==11
    assert bridge.sha256=='97cff42c3244d15f4a48e11026737e92a6427bcdb8201a944ed9e6f33f577b9f'
    bound=capture(repo,out,bridge.path)
    source_path=args.source_preset or root/'startup_contour_v1/verification1/V12-candidate/startup.recipe.json'
    candidate_path=args.candidate or root/'event_joint_v1/verification2/A/analysis/profile.json'
    source=load(source_path)
    old=generate(bridge,source,out/'original',crank_seconds=.58)
    candidate=deepcopy(source)
    document=load(candidate_path);assert document['kind']=='catch'
    candidate['event_overrides']['catch']=document
    new=generate(bridge,candidate,out/'candidate',crank_seconds=.58)
    before,_=sf.read(out/'original/native.wav',dtype='float32',always_2d=True)
    after,_=sf.read(out/'candidate/native.wav',dtype='float32',always_2d=True)
    assert before.shape==(384000,23) and after.shape==before.shape
    assert np.array_equal(before[:,:19],after[:,:19])
    assert not np.array_equal(before[:,19:],after[:,19:])
    notices=[load(out/variant/'lifecycle.vsltake.json')['source_events'] for variant in ('original','candidate')]
    assert notices[0]==notices[1] and old['final_state']==new['final_state']
    verify(repo,bound)
    frozen=Path('E:/VehicleSoundLab/baselines/startup_contour_v1/delivery1/evidence/verification1/exact_sources')
    voices=[p for p in (repo/'voices').rglob('*') if p.is_file()]
    assert len(voices)==89 and all(sha(p)==sha(frozen/p.relative_to(repo)) for p in voices)
    save(out/'report.json',dict(result='passed',bridge_sha256=bridge.sha256,
        source_preset=str(source_path),source_preset_sha256=sha(source_path),
        candidate_profile=str(candidate_path),candidate_profile_sha256=sha(candidate_path),
        source_ABI=11,author_ABI=4,preset_schema=7,take_schema=8,
        continuous_19channels_exact=True,only_event_audio_changes=True,
        event_notices_exact=True,final_state_exact=True,variable_block_replay_exact=True,
        source_binding_verified=True,formal_voices_unchanged=len(voices),
        own_native_window_launched=False,persistent_service_restarted=False,timbre_accepted=False,
        description='Same V12 runtime and composite A-exterior/F2-idle/A-cabin demonstration; only A catch parameters replaced. B cabin event remains a separate study.'))
    shutil.copy2(__file__,out/'executed_verification.py')
    print(dict(result='passed',source_ABI=11,continuous_channels_exact=19),flush=True)


if __name__=='__main__':main()
