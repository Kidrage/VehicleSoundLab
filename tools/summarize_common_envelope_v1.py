"""Bind the observed common/colour decomposition to inputs and frozen contracts."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

root=args.workspace/'references/analysis/common_envelope_v1'
a=json.loads((root/'analysis1/report.json').read_text(encoding='utf-8'))
v=json.loads((root/'verification1/report.json').read_text(encoding='utf-8'))
assert a['result']==v['result']=='pass'
assert v['analysis_report_sha256']==sha(root/'analysis1/report.json')
for name,report in (('analysis1',a),('verification1',v)):
    for source,digest in report['source_sha256'].items():
        assert sha(repo/source)==sha(root/name/'exact_sources'/source)==digest,(name,source)
for row in a['observations']:assert sha(root/'analysis1'/(row['name']+'.npz'))==row['source_power_sha256']
for path,digest in a['frozen_inputs'].items():assert sha(path)==digest,path
assert sha(args.workspace/'references/segments_v1.json')==a['catalog_sha256']
assert sha(args.workspace/'baselines/residual_motion_v1/manifest.json')==a['prior_manifest_sha256']
assert sha(args.workspace/'baselines/temporal_texture_v1/manifest.json')==a['temporal_manifest_sha256']
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
assert len(index)==a['c_h_count']==436
for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
assert not subprocess.check_output(['git','diff','HEAD','--','*.c','*.h'],cwd=repo).strip()
acceptance=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
assert sha(repo/acceptance['model'])==acceptance['model_sha256']
assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model')==acceptance['dna_model_sha256']

observations=[]
for ob in a['observations']:
    selected=next(s for s in ob['summary'] if s['block_seconds']==1 and s['offset_fraction']==0 and s['detrend_order']==1)
    sensitivity=[dict(block_seconds=s['block_seconds'],offset_fraction=s['offset_fraction'],
        detrend_order=s['detrend_order'],blocks=s['blocks'],
        common_variance_fraction_L=s['medians']['common_variance_fraction_LR'][0],
        slow_shape_rms_db_L=s['medians']['slow_shape_rms_db_LR'][0]) for s in ob['summary']]
    observations.append(dict(name=ob['name'],provenance=ob['provenance'],
        input_frames=ob['input_frames'],one_second_linear=selected,sensitivity_L=sensitivity))
sources=[Path(__file__),repo/'tools/freeze_common_envelope_v1.py',
    repo/'research/common_envelope_v1_plan.json',repo/'tools/analyze_common_envelope_v1.py',
    repo/'tools/verify_common_envelope_v1.py',repo/'tools/drive_evidence_v1/sources.py',
    *sorted((repo/'tools/common_envelope_v1').glob('*.py'))]
summary=dict(schema='vsl.common-envelope-summary/1',date='2026-11-12',result='pass',
    base_commit=a['base_commit'],evidence_root=str(root),observations=observations,
    known_controls=[dict(name=c['name'],known_envelope_rms_error_db=c.get('known_envelope_rms_error_db'),
        common_variance_fraction_LR=c['summary']['common_variance_fraction_LR'],
        all_rms_db_LR=c['summary']['all_rms_db_LR'],direct_dft_relative_error=c['direct_dft_relative_error'],
        constant_gain_invariance_error=c.get('constant_gain_invariance_error')) for c in a['controls']],
    independent_verification=dict(checked_rows=v['checked_rows'],maximum_relative_error=v['maximum_relative_error'],method=v['method']),
    direct_dft_relative_error_max=max([c['direct_dft_relative_error'] for c in a['controls']]+[r['direct_dft_relative_error'] for r in a['observations']]),
    maximum_decomposition_relative_error=max(r[k] for ob in a['observations'] for r in ob['rows']
        for k in ('decomposition_relative_error','slow_decomposition_relative_error')),
    maximum_parseval_relative_error=max(r['parseval_relative_error'] for ob in a['observations'] for r in ob['rows']),
    c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
    accepted_models_unchanged=True,runtime_changes=False,model_bank_changes=False,
    new_state_mapping=False,new_human_acceptance=False,
    decision='Do not transfer large moving/stationary-blip common envelopes into autonomous texture. Fixed-target shape motion remains; no causal attribution or new synthesis recipe is qualified.',
    pending_listening='Existing harmonic magnitude V1 review; no new response or duplicate question in this stage',
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts},
    input_metadata_sha256={name:sha(args.workspace/name) for name in (
        'references/segments_v1.json','references/approval_manifest.json',
        'baselines/residual_motion_v1/manifest.json','baselines/temporal_texture_v1/manifest.json')},
    limits=a['limits']+[
        'Candidate observation uses only the first predeclared review seed; no multi-seed conclusion',
        'Shape slow energy is not identified source AM: deterministic pitch/beat/transfer and analysis effects remain possible',
        'No C changes, device tests, new timbre or physical 7.1.4 acceptance; prior 40 CTests were not rerun'])
(repo/'research/common_envelope_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result='pass',observations=len(observations),controls=len(a['controls']),
    verified_rows=v['checked_rows'],maximum_independent_error=v['maximum_relative_error'],c_h_count=len(index))))
