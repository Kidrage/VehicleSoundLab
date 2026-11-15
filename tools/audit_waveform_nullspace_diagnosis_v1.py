"""Independent Decimal-Cholesky check of saved reduced problems and diagnostics."""
import argparse
import hashlib
import json
import os
import shutil
import sys
from decimal import Decimal,localcontext
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','diagnosis','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(exist_ok=False,parents=True);shutil.copy2(__file__,a.out/'executed_audit.py')
    def sha(p):
        with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    def read(p):return json.loads(Path(p).read_text('utf-8'))
    source=read(a.diagnosis/'report.json')
    assert source['result']=='waveform_nullspace_reduced_precision_diagnosed'
    assert [c['label'] for c in source['cases']]==['constant_1','constant_0.01','constant_0.0001','constant_1e-05']
    for p,h in source['inputs'].items():assert sha(p)==h
    results=[]
    for case in source['cases']:
        path=a.diagnosis/case['file'];assert sha(path)==case['sha256']
        with np.load(path) as z,localcontext() as ctx:
            ctx.prec=110;d=lambda x:Decimal.from_float(float(x))
            P=[[d(x) for x in row] for row in z['F']]
            target=[d(x) for x in z['c'][:,0]]
            n=len(P[0]);m=len(P)
            H=[[sum((P[k][i]*P[k][j] for k in range(m)),Decimal(0))+(i==j) for j in range(n)] for i in range(n)]
            h=[sum((P[k][i]*target[k] for k in range(m)),Decimal(0)) for i in range(n)]
            L=[[Decimal(0)]*n for _ in range(n)]
            for i in range(n):
                for j in range(i+1):
                    v=H[i][j]-sum((L[i][k]*L[j][k] for k in range(j)),Decimal(0))
                    L[i][j]=v.sqrt() if i==j else v/L[j][j]
            forward=[]
            for i in range(n):forward.append((h[i]-sum((L[i][j]*forward[j] for j in range(i)),Decimal(0)))/L[i][i])
            exact=[Decimal(0)]*n
            for i in reversed(range(n)):
                exact[i]=(forward[i]-sum((L[j][i]*exact[j] for j in range(i+1,n)),Decimal(0)))/L[i][i]
            stationarity=max(abs(sum((H[i][j]*exact[j] for j in range(n)),Decimal(0))-h[i]) for i in range(n))
            assert stationarity<Decimal('1e-80')
            exact_float=np.array([float(x) for x in exact])
            assert np.array_equal(exact_float,z['Decimal110_z'][:,0])
            actual=[d(x) for x in z['current_z'][:,0]]
            residual=[sum((v*w for v,w in zip(row,actual)),Decimal(0))-y for row,y in zip(P,target)]
            gradient=[sum((P[i][j]*residual[i] for i in range(m)),Decimal(0))+actual[j] for j in range(n)]
            norm=float(sum((x*x for x in gradient),Decimal(0)).sqrt())
            assert abs(norm-case['current_reduced_Decimal_gradient_norm'])<=1e-14*norm
            relative=float(np.linalg.norm(z['current_z'][:,0]-exact_float)/np.linalg.norm(exact_float))
            assert relative==case['current_vs_reduced_Decimal_relative_error']
            top=z['U'][:m];T=z['T'];reconstructed=z['reconstructed_top']
            top_error=float(np.linalg.norm(top-reconstructed)/np.linalg.norm(reconstructed))
            assert top_error==case['identity_top_vs_triangular_relative_error']
            assert np.allclose(reconstructed@T,np.eye(m),atol=2e-12,rtol=0)
            assert np.array_equal(top@T-np.eye(m),z['top_identity_error'])
            rows=[float(x) for x in case['original_gap_ratios']]
            assert case['original_qualified']==all(x<=1 for x in rows)
            results.append(dict(label=case['label'],independent_Decimal110_Cholesky_stationarity=str(stationarity),
                saved_Decimal_solution_exact=True,actual_reduced_gradient_norm=norm,
                small_identity_block_relative_error=top_error,original_qualified=case['original_qualified']))
    result=dict(result='independent_waveform_nullspace_diagnosis_verified',cases=results,
        producer_sha256=sha(a.diagnosis/'report.json'),auditor_sha256=sha(__file__),
        isolated_physical_or_sole_roundoff_cause_claimed=False)
    (a.out/'report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(result,flush=True)


if __name__=='__main__':main()
