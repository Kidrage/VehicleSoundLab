"""Bind fresh functional checks and approved state-reference inventory."""
import argparse
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

root=args.workspace/'references/analysis/system_status_v1'
device=json.loads((root/'device1/report.json').read_text(encoding='utf-8'))
review=json.loads((root/'reference1/report.json').read_text(encoding='utf-8'))
assert device['result']=='short_device_checks_passed' and review['result']=='pass'
assert device['c_index_sha256']==sha(repo/'handoff/C文件索引.csv')
for name,digest in device['binary_sha256'].items():assert sha(root/'device1/bin'/name)==digest
assert device['exports'][0]['source_hash']==device['exports'][1]['source_hash']
for path,digest in review['input_sha256'].items():assert sha(path)==digest,path
for name,digest in review['source_sha256'].items():assert sha(root/'reference1/exact_sources'/name)==sha(repo/name)==digest,name
for name,digest in device['source_sha256'].items():assert sha(repo/name)==digest,name
sources=[repo/name for name in ('tools/probe_current_system_v1.py','tools/make_state_reference_review_v1.py',
    'tools/summarize_system_status_v1.py','tools/freeze_system_status_v1.py')]
summary=dict(schema='vsl.system-status-summary/1',date='2026-11-12',result='short_functional_checks_and_reference_inventory',
    evidence_root=str(root),C_H_unchanged=442,c_index_sha256=device['c_index_sha256'],
    native_stereo_device_checked=True,device_cases={name:{k:row[k] for k in ('frames','healthy','offline_float_equal','queue_empty','budget_exceeded','render_max_ms','shifts','overruns')} for name,row in device['device_cases'].items()},
    take_verified=device['take']['verified'],take_queue_empty=[device['take']['record_queue_empty'],device['take']['play_queue_empty']],
    take_over_budget=[device['take']['record_over_budget'],device['take']['play_over_budget']],
    offline_exports=device['exports'],actual_12channel_device_checked=False,long_run_checked=False,new_UI_interaction_checked=False,
    page=review['url'],reference_clips=[{k:row[k] for k in ('key','title','source','seconds','limits')} for row in review['clips'] if row['kind']=='approved_recording_reference'],
    C_device_capture_clips=2,matched_state_timbre_comparison_complete=False,human_timbre_accepted=False,C_changes=False,
    current_source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},input_sha256=review['input_sha256'],
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts},
    limitations=['Actual muted short stereo tests verify function/control/replay, not sound realism or a long-run realtime guarantee',
        'Current12channel source consistency is offline; spatial routing still uses the explicit mono-proxy path',
        'A low-rev reference is not confirmed warm idle; stationary revs do not establish neutral gear or pedal/load',
        'Startup is cabin reference, not an exterior transient fit; E transitions have display/synchronization limits',
        'Shutdown, isolated backfire and isolated intake lack confirmed clean reference excerpts',
        'Reference clips and functional captures have different actions/perspectives/levels and are not a matched AB test'])
(repo/'research/system_status_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=summary['result'],reference_clips=len(summary['reference_clips']),device_cases=len(summary['device_cases']))))
