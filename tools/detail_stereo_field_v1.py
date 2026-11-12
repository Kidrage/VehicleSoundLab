"""Decompose fixed held-out errors and summarize additive budgets, no new fit."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from stereo_field_v1.model import packed,fit

root=args.workspace/'references/analysis/stereo_field_v1'
field=json.loads((root/'analysis1/report.json').read_text(encoding='utf-8'))
budget=json.loads((root/'budget1/report.json').read_text(encoding='utf-8'))
assert field['result']==budget['result']=='diagnostics_completed'
args.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),repo/'tools/stereo_field_v1/model.py',repo/'tools/drive_evidence_v1/sources.py']
for p in paths:
    target=args.out/'exact_sources'/p.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
r=dict(schema='vsl.stereo-field-detail/1',result='running',decompositions=[],budgets=[],
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    input_sha256={str(root/name/'report.json'):sha(root/name/'report.json') for name in ('analysis1','budget1')})
try:
    for observation in field['observations']:
        path=args.workspace/'baselines/reference_audit_v1/evidence/stereo_delay_v1/analysis1'/(observation['name']+'_observations.npz')
        assert sha(path)==field['input_sha256'][str(path)];r['input_sha256'][str(path)]=sha(path)
        with np.load(path) as archive:data={key:archive[key] for key in archive.files}
        for band in observation['bands']:
            low,high=band['hz'];mask=(data['hz']>=low)&(data['hz']<high);values=packed(data,mask)
            for direction in band['directions']:
                train,test=direction['train_blocks'],direction['test_blocks'];selected=direction['selected']
                base,_=fit(values,train,1,0);candidate,_=fit(values,train,selected['subdivisions'],selected['prior'])
                parts=[]
                for prediction in (base,candidate):
                    balance=[];cross=[]
                    for block in test:
                        sample=values[block];trace=sample[:,0]+sample[:,1];q=sample/np.maximum(trace[:,None],1e-300)
                        difference=(q-prediction)**2
                        balance.append(float(np.sum(trace*difference[:,:2].sum(axis=1))))
                        cross.append(float(np.sum(2*trace*difference[:,2:].sum(axis=1))))
                    parts.append(dict(LR_power_balance_mse=float(np.mean(balance)),complex_cross_mse=float(np.mean(cross))))
                for part,key in zip(parts,('baseline_test_rmse','candidate_test_rmse')):
                    assert abs(np.sqrt(sum(part.values()))-direction[key])<1e-12
                r['decompositions'].append(dict(name=observation['name'],hz=band['hz'],direction=direction['direction'],
                    bidirectional_gate_passed=band['bidirectional_gate_passed'],baseline=parts[0],candidate=parts[1]))
    for observation in budget['observations']:
        for count in (1,4,8):
            rows=[x for x in observation['rows'] if x['subdivisions']==count]
            total=sum(x['target_trace'] for x in rows)
            bad=[x for x in rows if not x['unmodified_debt_PSD']]
            r['budgets'].append(dict(identity=observation['identity'],subdivisions=count,cells=len(rows),infeasible_cells=len(bad),
                target_trace_in_infeasible_cells_fraction=sum(x['target_trace'] for x in bad)/total,
                minimum_DNA_power_alpha_bound=min(x['maximum_independent_additive_DNA_power_alpha'] for x in rows),
                maximum_raw_negative_eigenvalue_relative=max(0,-min(x['raw_minimum_eigenvalue_relative'] for x in rows))))
    r.update(result='pass',meaning='Describes already chosen models and fixed diagnostic grids; no new gate, threshold, complexity selection or runtime recipe')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],decompositions=len(r['decompositions']),budgets=len(r['budgets']))))
