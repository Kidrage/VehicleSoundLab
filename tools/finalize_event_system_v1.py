"""Summarize existing event evidence; does not run DSP or change sound parameters."""
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    result=read(data/'renders/event_system_v1/verification1/verification.json')
    assert result['ui'] and result['replay_pcm_exact'] and result['replay_event_notices_exact']
    old=data/'baselines/vehicle_controller_v1/delivery1';manifest=read(old/'manifest.json');protected=[]
    for row in manifest['files']:
        if row['path'].startswith('repo/voices/'):
            path=repo/row['path'][5:];actual=sha(path)
            assert actual==row['sha256'],str(path)
            protected.append(dict(path=path.relative_to(repo).as_posix(),sha256=actual))
    assert len(protected)==87
    logs={}
    for name,path in [
        ('source_three_checks',data/'renders/vehicle_controller_v1/source-event-build1.log'),
        ('event_core_two_checks',repo/'build-event-synth-v1/Testing/Temporary/LastTest.log'),
        ('latest_source_event_check',repo/'build-vehicle-source-v2/Testing/Temporary/LastTest.log')]:
        raw=path.read_bytes();assert b'Passed' in raw or b'Test Passed' in raw
        logs[name]=dict(path=str(path),sha256=sha(path))
    review=read(data/'references/analysis/event_authoring_v1/review1/review.json')
    assert review['bridge_sha256']==result['bridge_sha256'] and not review['hearing_accepted']
    analyses={kind:read(data/f'references/analysis/event_authoring_v1/{kind}2/report.json') for kind in ('afterfire','shift')}
    assert all(row['status']=='analysis_only' for row in analyses.values())
    rejected=read(data/'renders/event_system_v1/launch1/approval-rejections.json');assert rejected['result']=='not_executed'
    summary=dict(schema='vsl.event-system-milestone-verification/1',goal_complete=False,hearing_accepted=False,
        implemented=['event_synth bounded4voice parameter synthesis','event_control semantic observer and16command queue',
                     'sample-clock vehicle_source integration','23native channels and per-instance notices',
                     'independent controller event page and frame-accurate take3','reusable cropped-event authoring/JSON-to-C compiler'],
        checks=result,protected_previous_voice_files=protected,c_test_logs=logs,
        candidate_profiles=['A mixed-cabin early-start','A mixed-cabin LF build/catch'],
        refused_profiles={kind:dict(source=row['provenance'],event_to_background_db=row['observation']['event_to_background_db'],reason=row['reason'])
                          for kind,row in analyses.items()},
        prior_attempts='First CLI revision raised the same contrast refusal before creating an output directory; tool trace preserved in the conversation. Revised CLI writes analysis-only reports and exits3, without changing the3dB condition.',
        review=dict(path=str(data/'references/analysis/event_authoring_v1/review1'),sha256=sha(data/'references/analysis/event_authoring_v1/review1/review.json'),
                    http_checked_clips=7,browser_render_qa=False,hearing_accepted=False),
        persistent_launch=rejected,
        not_complete=['material-approved afterfire and mechanical profiles','startup and full lifecycle listening acceptance',
                      'event authoring workbench page and vehicle recipe packaging','long-run/overlap qualification',
                      'persistent updated workbench launch (automatic approval rejected)'],
        compute_optimized=False,adi_measured=False,new_media_downloaded=False)
    output=repo/'research/event_system_v1_verification.json'
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    agent=repo/'AGENTS.md';agent.write_text(agent.read_text(encoding='utf-8').replace('318.435..318.635','318.455..318.61'),encoding='utf-8',newline='\n')
    print(json.dumps(dict(summary=str(output),protected_voice_files=len(protected),goal_complete=False)))


if __name__=='__main__':main()
