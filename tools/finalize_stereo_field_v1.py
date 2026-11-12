"""Verify recorded-transfer diagnostics and unchanged C/model contracts."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import scipy
from drive_evidence_v1.sources import sha

root=args.workspace/'references/analysis/stereo_field_v1'
out=root/'verification1';out.mkdir(exist_ok=False)
shutil.copy2(Path(__file__),out/Path(__file__).name)
r=dict(schema='vsl.stereo-field-verification/1',result='running',clipping_reproduction=[],source_sha256={Path(__file__).relative_to(repo).as_posix():sha(Path(__file__))})
try:
    attempts={name:json.loads((root/name/'report.json').read_text(encoding='utf-8')) for name in ('analysis1','budget1','detail1','components1')}
    assert [attempts[k]['result'] for k in attempts]==['diagnostics_completed','diagnostics_completed','pass','diagnostics_completed']
    inputs={}
    for name,record in attempts.items():
        for path,digest in record['source_sha256'].items():
            assert sha(root/name/'exact_sources'/path)==digest,(name,path)
            assert sha(repo/path)==digest,(name,path)
        for path,digest in record['input_sha256'].items():assert sha(path)==digest,path
        inputs.update(record['input_sha256'])
    field=attempts['analysis1'];parts=attempts['components1'];budget=attempts['budget1'];detail=attempts['detail1']
    assert len(field['controls'])==len(parts['controls'])==12 and len(budget['known_controls'])==6
    for family in (field,parts):
        for control in family['controls']:
            if control['name']=='coloured_delay':assert control['bidirectional_bands']>=4
            else:assert control['bidirectional_bands']==0
    assert len(detail['decompositions'])==96
    for observation in budget['observations']:
        path=repo/'voices/residual_osc_v1'/(observation['identity']+'.residual')
        old=np.loadtxt(path,skiprows=1);inputs[str(path)]=sha(path)
        coarse=[row for row in observation['rows'] if row['subdivisions']==1]
        maximum=0
        for row,profile in zip(coarse,old):
            scale=row['target_trace'];power=np.maximum(row['raw_diagonal_debt_relative'],0)
            desired=complex(*row['raw_cross_debt_relative']);bound=np.sqrt(np.prod(power))
            expected=desired if abs(desired)<=bound else desired*bound/abs(desired)
            actual=complex(*profile[4:])*np.sqrt(profile[2]*profile[3])/scale
            maximum=max(maximum,float(abs(power-profile[2:4]/scale).max()),float(abs(expected-actual)))
        assert maximum<1e-10,(observation['identity'],maximum)
        r['clipping_reproduction'].append(dict(identity=observation['identity'],maximum_normalized_moment_error=maximum,profile_sha256=sha(path)))
    index=repo/'handoff/C文件索引.csv'
    frozen_index=args.workspace/'baselines/residual_dense_v1/docs/C文件索引.csv'
    assert sha(index)==sha(frozen_index)
    with index.open(encoding='utf-8-sig',newline='') as stream:code=list(csv.DictReader(stream))
    assert len(code)==442
    for row in code:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    models={'voices/dna_bank_v1/V10 Exterior.model':'6f8992e6674f603334f82bdbc526fd8ac5bbe750606154c5e83c166c077bb1b7',
        'voices/coherent_low_v1/measured_phase.model':'9e456a4198bce540a4ccc60220b9cf86e40dc80eadc8d1c2904dc5248715e895'}
    for name,digest in models.items():assert sha(repo/name)==digest,name
    r.update(result='pass',C_H_unchanged=442,c_index_sha256=sha(index),accepted_model_sha256=models,
        default_binaries_rebuilt=False,new_audio_or_models=False,new_listening_acceptance=False,
        numpy_version=np.__version__,scipy_version=scipy.__version__,python_version=sys.version)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
sources=[p for p in sorted((repo/'tools/stereo_field_v1').glob('*.py'))]
sources += [repo/name for name in ('tools/analyze_stereo_field_v1.py','tools/analyze_stereo_budget_v1.py',
    'tools/detail_stereo_field_v1.py','tools/analyze_stereo_components_v1.py','tools/finalize_stereo_field_v1.py','tools/freeze_stereo_field_v1.py',
    'research/stereo_field_v1_plan.json','research/stereo_budget_v1_plan.json','research/stereo_components_v1_plan.json')]
cases=[]
for original,component in zip(field['observations'],parts['observations']):
    assert original['name']==component['name']
    def passed(record):
        return [dict(hz=b['hz'],axes=[d['selected'].get('axis','joint') for d in b['directions']],
            subdivisions=[d['selected']['subdivisions'] for d in b['directions']],
            forward_reverse_RMSE_reduction=[d['test_rmse_reduction'] for d in b['directions']]) for b in record['bands'] if b['bidirectional_gate_passed']]
    cases.append(dict(name=original['name'],seconds=original['case']['seconds'],source=original['source'],blocks=original['blocks'],
        joint_family_qualified=passed(original),component_family_qualified=passed(component),insufficient_training=original['blocks']//2<2))
summary=dict(schema='vsl.stereo-field-summary/1',date='2026-11-12',result='diagnostic_only_no_runtime_promotion',
    evidence_root=str(root),attempts=[dict(folder=name,result=record['result']) for name,record in attempts.items()],
    synthetic_controls_per_family=12,known_alpha_controls=6,recorded_cases=cases,
    original_joint_maximum_oracle_absolute_error=max(row['oracle']['maximum_absolute_error'] for row in field['controls']+field['observations']),
    maximum_synthetic_DFT_relative_error=max(row['scalar_DFT_relative'] for row in field['controls']+parts['controls']),
    maximum_alpha_control_error=max(row['alpha_error'] for row in budget['known_controls']),
    maximum_budget_scalar_eigenvalue_error=max(row['independent_eigenvalue_error'] for ob in budget['observations'] for row in ob['rows']),
    fixed_model_clipping_reproduced=r['clipping_reproduction'],additive_budget=detail['budgets'],
    C_H_unchanged=442,c_index_sha256=sha(index),accepted_model_sha256=models,
    C_changes=False,models_changed=False,driver_changes=False,new_audio=False,human_accepted=False,
    current_source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},input_sha256=inputs,
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts},
    limits=field['limits']+budget['limits']+parts['limits']+[
        'The original joint total gate passed five recorded bands but can hide balance regression; the new axis family/component gate is a separate exploratory result, not a revised threshold on the original run',
        'Only two D dyno bands survive the component family. No cabin transfer candidate qualified; do not select a one-direction E improvement or relax the10percent gate',
        'A uses only three raw blocks, insufficient for train-only selection; its near-mono debt can require a small alpha because of a weak side direction, not a recommended large attenuation',
        'Feasibility counts/trace fractions do not measure audible defect size; alpha must never be automatically used as a per-cell gain curve',
        'No C contract changed, no C tests or device build rerun, and no additional listening question was issued'])
(repo/'research/stereo_field_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=summary['result'],cases=len(cases),component_qualified_bands=sum(len(x['component_family_qualified']) for x in cases),C_H=442)))
