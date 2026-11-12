"""Bind the integrated stereo-bed implementation, old/new players and measured evidence."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import sys

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);args=p.parse_args()
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
root=args.workspace/'references/analysis/stereo_bed_v1'
records={key:json.loads((root/key/'report.json').read_text(encoding='utf-8')) for key in ['before','build1','verification1','review1']}
assert records['build1']['result']=='build_and_41tests_pass'
assert records['verification1']['result']=='technical_pass_only' and records['review1']['result']=='pass'
for key in ['build1','verification1','review1']:
    for name,digest in records[key].get('source_sha256',{}).items():assert sha(repo/name)==digest,(key,name)
    for name,digest in records[key].get('input_sha256',{}).items():assert sha(name)==digest,(key,name)
for name,digest in records['before']['files'].items():assert sha(root/'before'/name)==digest
index=repo/'handoff/C文件索引.csv'
with index.open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
assert len(old)==445
spec=importlib.util.spec_from_file_location('vsl_bed_index',repo/'handoff/tools/index_sources.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rows=list(m.code_rows());assert len(rows)==448
mapping={r[0]:r for r in rows}
changed=[r['文件'] for r in old if r['SHA-256']!=mapping[r['文件']][-1]]
expected={'modules/atlas_drive/render.c','modules/atlas_drive/render.h','modules/atlas_take/assets.c','modules/atlas_take_io/codec.c',
          'experiments/atlas_drive_v1/probe.c','experiments/atlas_monitor_v1/ui.c','experiments/atlas_monitor_v1/verify.c',
          'experiments/atlas_take_v1/checks.c','experiments/atlas_take_v1/device_checks.c'}
assert set(changed)==expected,changed
for row in old:assert tuple(row.values())[:4]==mapping[row['文件']][:4],row['文件']
with index.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.writer(f,lineterminator='\n');writer.writerow(old[0].keys());writer.writerows(rows)
approved={'voices/dna_bank_v1/V10 Exterior.model':'6f8992e6674f603334f82bdbc526fd8ac5bbe750606154c5e83c166c077bb1b7',
          'voices/coherent_low_v1/measured_phase.model':'9e456a4198bce540a4ccc60220b9cf86e40dc80eadc8d1c2904dc5248715e895'}
for name,digest in approved.items():assert sha(repo/name)==digest
ui=json.loads((root/'ui_launch.json').read_text(encoding='utf-8'));assert ui['Responding'] and 'Stereo Bed' in ui['MainWindowTitle']
v=records['verification1'];review=records['review1']
summary=dict(schema='vsl.stereo-bed-summary/1',date='2026-11-12',result='integrated_optional_bed_technical_pass_only',
    C_H_count=448,new_C_H_count=3,changed_C_H=changed,unchanged_prior_C_H=445-len(changed),c_index_sha256=sha(index),
    ctests=41,default_routing='legacy objects; existing deployed binaries retained',
    native_entry='Launch-Stereo-Bed.cmd',native_build='build-stereo-bed-v1',native_UI=ui,
    legacy_cases=v['legacy'],bed_cases=v['bed'],bed_only=v['bed_only'],device=v['device'],take=v['take'],exports=v['exports'],
    take_schema=3,control_fields=25,old_schema2_player_preserved=v['old_schema2_player_preserved'],
    review=review['clips'],page=review['page'],accepted_models_unchanged=approved,
    human_accepted=False,long_run_checked=False,hardware12_checked=False,UI_interaction_checked=False,
    limitations=['Front stereo bed preserves observed channels, not reconstructed engine-bank locations',
                 'No new spatial information or upmix from near-mono A; E demonstration is an unaccepted cabin model',
                 'Room,perspective,propagation apply only to engineering auxiliary/events in bed mode',
                 'Only short muted512frame device proof;5ms offline overruns still not resolved',
                 'Actual12speaker calibration, listening and complete state-specific timbres remain unfinished'],
    current_source_sha256={**records['build1']['source_sha256'],**v['source_sha256'],**review['source_sha256'],
                          'tools/prepare_stereo_bed_v1.py':sha(repo/'tools/prepare_stereo_bed_v1.py'),
                          'tools/finalize_stereo_bed_v1.py':sha(__file__),'handoff/tools/index_sources.py':sha(repo/'handoff/tools/index_sources.py')},
    evidence_sha256={x.relative_to(root).as_posix():sha(x) for x in sorted(root.rglob('*')) if x.is_file() and '__pycache__' not in x.parts})
(repo/'research/stereo_bed_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=summary['result'],C_H=448,changed=len(changed),ctests=41,evidence_files=len(summary['evidence_sha256']))))
