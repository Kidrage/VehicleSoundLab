"""Check whether independent additions can represent frozen stereo spectral debt."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from residual_osc_v1.sources import read
from residual_osc_v1.spectrum import matrices,BANDS
from stereo_field_v1.budget import matrix,minimum,analyze,controls,scalar_minimum

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/stereo_budget_v1_plan.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
paths=[Path(__file__),plan_path,repo/'tools/stereo_field_v1/budget.py',repo/'tools/drive_evidence_v1/sources.py',
    repo/'tools/residual_osc_v1/sources.py',repo/'tools/residual_osc_v1/spectrum.py']
for p in paths:
    target=args.out/'exact_sources'/p.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
r=dict(schema='vsl.stereo-additive-budget/1',result='running',known_controls=[],observations=[],input_sha256={},
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
(args.out/'metadata.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')

try:
    r['known_controls']=controls(plan)
    for identity in plan['cases']:
        reference,bases,provenance=read(args.workspace,repo,identity);base,path=bases['1.0']
        r['input_sha256'][str(path)]=sha(path)
        r['input_sha256'][provenance['normalized_source']]=provenance['normalized_sha256']
        rows=[]
        for count in plan['subdivisions']:
            hz=np.fft.rfftfreq(2048,1/48000);cells=[]
            for parent,(lo,hi) in enumerate(BANDS):
                bins=np.flatnonzero((hz>=lo)&(hz<hi));parts=np.array_split(bins,count)
                edges=[lo]+[float((hz[parts[i][-1]]+hz[parts[i+1][0]])/2) for i in range(count-1)]+[hi]
                cells.extend((parent,(edges[i],edges[i+1])) for i in range(count))
            bounds=[band for _,band in cells];target=matrices(reference,bounds);represented=matrices(base[24000:],bounds)
            for (parent,bound),a,b in zip(cells,target,represented):
                t=matrix(a);s=matrix(b);row=analyze(t,s,plan['PSD_relative_tolerance'],plan['bisection_steps'])
                oracle=scalar_minimum((t-s)/row['target_trace'])
                difference=abs(oracle-row['raw_minimum_eigenvalue_relative'])
                assert difference<plan['independent_matrix_error_maximum']
                # Separate principal-minor check at the reported alpha boundary.
                alpha=row['maximum_independent_additive_DNA_power_alpha']
                residual=(t-alpha*s)/row['target_trace']+np.eye(2)*plan['PSD_relative_tolerance']
                determinant=float((residual[0,0]*residual[1,1]-residual[0,1]*residual[1,0]).real)
                assert min(np.diag(residual).real)>-1e-12 and determinant>-1e-12
                rows.append(dict(subdivisions=count,parent_band=parent,hz=list(bound),target=a,base=b,
                    independent_eigenvalue_error=difference,boundary_principal_determinant=determinant,**row))
        r['observations'].append(dict(identity=identity,source=provenance,reference_frames=len(reference),base_frames=len(base),rows=rows))
        coarse=[x for x in rows if x['subdivisions']==1]
        print(json.dumps(dict(identity=identity,infeasible=sum(not x['unmodified_debt_PSD'] for x in coarse),
            coarse_alpha=[round(x['maximum_independent_additive_DNA_power_alpha'],4) for x in coarse])),flush=True)
    r.update(result='diagnostics_completed',C_changes=False,models_changed=False,human_accepted=False,
        limits=[plan['scope'],'The alpha bound is conditional on same-window measured target/base matrices and the chosen numerical tolerance, not a physical engine-source budget',
            'Independent stochastic addition assumes zero ensemble cross with DNA; finite deterministic OSC sums can have finite-window cross terms',
            'A different PSD projection may redistribute error but cannot exactly represent an indefinite independent-additive debt at unchanged base'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
