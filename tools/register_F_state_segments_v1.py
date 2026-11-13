"""Append human-reviewed F sources to the permissioned catalogue; preserve its exact prior bytes."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F-state-catalogue/1',result='running',sources={},runtime_changed=False)
try:
    catalogue=repo/'references/segments_v1.json'
    data_catalogue=args.workspace/'references/segments_v1.json'
    assert sha(catalogue)==sha(data_catalogue)
    original=load(catalogue)
    assert all(key not in original['sources'] for key in ('F1','F2','F3'))
    review=load(repo/'research/F_state_audition_v1_review.json')
    assert review['human_listening_result']=='received'
    assert review['clip_decisions']['F3_stopped'].startswith('Rejected')
    audition=args.workspace/'references/analysis/F_state_audition_v1/review1/report.json'
    clips=load(audition)['clips']
    approval=load(repo/'research/approved_state_media_v1_plan.json')
    metadata={row['id']:row for row in approval['sources'] if row['approved']}
    shutil.copy2(catalogue,args.out/'catalogue_before.json')
    report['prior_catalogue_sha256']=sha(catalogue)
    for path in (Path(__file__),repo/'research/F_state_audition_v1_review.json',
                 repo/'research/approved_state_media_v1_plan.json',repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    for key in ('F1','F2','F3'):
        clip=next(row for row in clips if row['source']==key)
        assert sha(args.workspace/clip['source_master'])==clip['source_master_sha256']
        assert sha(args.workspace/clip['original_encoded'])==clip['original_encoded_sha256']
        original['sources'][key]=dict(url=metadata[key]['url'],approval=approval['approval_evidence'],
            raw=clip['original_encoded'],raw_sha256=clip['original_encoded_sha256'],
            master=clip['source_master'],master_sha256=clip['source_master_sha256'],
            video=clip['original_encoded'],video_sha256=clip['original_encoded_sha256'],
            alignment='Same muxed media timeline; precise audio/video/instrument latency not calibrated')
    for clip in clips:
        key=clip['id']
        allowed=['source_usability_review']
        if key in ('F2_tailpipe','F3_fifth1','F3_fifth2','F3_sixth'):
            allowed+=['recording_power','fixed_window_spectral_observation']
        if key in ('F3_fifth1','F3_fifth2','F3_sixth'):
            allowed+=['state_context']
        original['segments'][key]=dict(source=clip['source'],seconds=clip['actual_seconds'],
            perspective='near-tailpipe LP-610' if key.startswith('F2') else
                'cabin Tecnica candidate' if key.startswith('F3') else 'multi-car street / moving microphone',
            visual=clip['note'],audio_interpretation=review['clip_decisions'].get(key,
                'Complete recording not individually rated in the short-clip feedback'),
            allowed_uses=allowed,existing_audition='references/analysis/F_state_audition_v1/review1/'+clip['file'],
            not_established=['exact RPM / warm idle / stock exhaust','precise AV or instrument timing',
                'pedal / torque / fueling / calibrated load','physical noise-source separation',
                'accepted synthesis timbre / phase extractor qualification'])
        if key=='F3_stopped':
            original['segments'][key]['excluded_from_DNA_reason']='User heard speech masking engine in54..56s'
    before=load(args.out/'catalogue_before.json')
    assert all(original['sources'][key]==value for key,value in before['sources'].items())
    assert all(original['segments'][key]==value for key,value in before['segments'].items())
    text=json.dumps(original,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    catalogue.write_text(text,encoding='utf-8',newline='\n')
    data_catalogue.write_text(text,encoding='utf-8',newline='\n')
    shutil.copy2(catalogue,args.out/'catalogue_after.json')
    report.update(result='F_sources_and_restricted_intervals_registered_existing_entries_unchanged',
        catalogue_sha256=sha(catalogue),audition_report_sha256=sha(audition),
        added_sources=['F1','F2','F3'],added_segments=[clip['id'] for clip in clips],
        F3_stopped_DNA_rejected=True,model_exported=False,C_changed=False)
    print(json.dumps(dict(result=report['result'],sources=3,segments=7)),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
