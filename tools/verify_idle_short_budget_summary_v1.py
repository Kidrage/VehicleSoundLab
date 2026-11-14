"""Verify pooled descriptive tables independently of the plotting/assessment script."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','assessment','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import signal
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_verifier.py')
run=load(a.input/'report.json');audit=load(a.audit/'report.json');assessment=load(a.assessment/'report.json')
assert audit['result']=='all_idle_short_buses_and_native_residual_spectra_independently_checked'
assert audit['input_sha256']==assessment['input_sha256']==sha(a.input/'report.json')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),assessment_sha256=sha(a.assessment/'report.json'),maximum_error=0.,pooled_groups=0,spectral_groups=0)
def check(x,y):
    d=float(abs(np.array(x)-np.array(y)).max());r['maximum_error']=max(r['maximum_error'],d);assert d<1e-10
for group in assessment['pooled']:
    rows=[row for row in run['cases'] if row['metadata']['kind']=='generated' and row['metadata']['phase_basis']==group['phase_basis'] and row['window_ms']==group['window_ms']];assert len(rows)==24
    total=np.zeros(6);main=np.zeros(6);detail=np.zeros(6);cross=np.zeros(6);powers=[]
    for row in rows:
        with np.load(a.input/row['file']) as f:
            total+=np.diag(f['covariance'][25])/24;main+=np.diag(f['main_covariance'][25])/24
            detail+=np.diag(f['detail_covariance'][25])/24;cross+=np.diag(f['cross_covariance'][25])/24
            p=[]
            for bus in range(3):
                c=f['coefficients'][:,bus,:][:,[1,2,4]]/f['reference'];v=np.concatenate([c.real,c.imag],axis=1);v-=v.mean(axis=0)
                hz,density=signal.periodogram(v,fs=50,window=np.hanning(117)[:-1],detrend=False,axis=0,scaling='density');s=density*50/116
                p.append([s[(hz>=lo)&(hz<hi)].sum(axis=0) for lo,hi in [[0,1],[1,3],[3,8],[8,25.000001]]])
            powers.append(p)
    check(np.sqrt(total),group['mix_std']);check(np.sqrt(main),group['main_std']);check(np.sqrt(detail),group['detail_std'])
    check(np.array([main/total,detail/total,cross/total]),group['main_detail_cross_fractions']);check(np.mean(powers,axis=0),group['temporal_power_mix_main_detail'])
    r['pooled_groups']+=1
for group in assessment['spectra']:
    if group['label'].startswith('generated_'):
        basis=group['label'].removeprefix('generated_');rows=[row for row in run['spectra'] if row['metadata']['kind']=='generated' and row['metadata']['phase_basis']==basis];assert len(rows)==24
        for key,value in group['summary'].items():check(sum(np.array(row['summary'][key]) for row in rows)/24,value)
    else:
        row=next(row for row in run['spectra'] if row['label']==group['label'])
        for key,value in group['summary'].items():check(value,row['summary'][key])
    r['spectral_groups']+=1
assert r['pooled_groups']==6 and r['spectral_groups']==4
r['result']='all_pooled_short_idle_tables_independently_verified';save(a.out/'report.json',r);print(r)
