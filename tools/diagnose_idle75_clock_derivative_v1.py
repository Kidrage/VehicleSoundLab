"""Reproduce the failed central derivative gate and distinguish cubic node seams."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from idle75_clock_v1.row import nodes,gain
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_diagnosis.py')
plan=repo/'research/idle75_clock_v1_derivative_diagnosis.json';shutil.copy2(plan,a.out/plan.name)
model=load(a.input/'row.json');model['taps']=np.array(model['taps']);model['covariance']=np.array(model['covariance'])
values,white=nodes(model,149921,12.);p0=np.ones(2);g,jac,x=gain(model,values,144000,p0)
fraction=np.remainder(np.arange(144000)/48000*model['node_rate'],1.)
out=dict(result='running',original_report_sha256=sha(a.input/'report.json'),plan_sha256=sha(plan),step=1e-6,gate=1e-6,cases=[])
arrays=dict(nodes=values,white=white,fraction=fraction,gain=g,analytic_jacobian=jac)
for k in range(2):
    h=np.zeros(2);h[k]=1e-6
    plus=gain(model,values,144000,p0+h)[0];minus=gain(model,values,144000,p0-h)[0]
    plus2=gain(model,values,144000,p0+2*h)[0];minus2=gain(model,values,144000,p0-2*h)[0]
    central=(plus-minus)/(2e-6)
    forward=(-3*g+4*plus-plus2)/(2e-6);backward=(3*g-4*minus+minus2)/(2e-6)
    sided=np.where(fraction<=.5,forward,backward) if k==0 else central
    ce=abs(central-jac[:,k]);se=abs(sided-jac[:,k]);index=int(np.argmax(ce))
    out['cases'].append(dict(parameter=k,central_maximum_error=float(ce.max()),central_worst_sample=index,
        central_worst_node_fraction=float(fraction[index]),branch_preserving_maximum_error=float(se.max()),
        original_gate_passed=bool(se.max()<1e-6)))
    arrays[f'central_{k}']=central;arrays[f'branch_preserving_{k}']=sided
out['result']='cubic_node_seam_truncation_identified' if all(row['original_gate_passed'] for row in out['cases']) else 'branch_preserving_gate_failed'
np.savez_compressed(a.out/'derivatives.npz',**arrays);save(a.out/'report.json',out);print(out)
