"""Independent scalar detrending/pairwise-ratio/DFT checks of actual evidence."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--analysis',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),repo/'tools/drive_evidence_v1/sources.py']
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.common-envelope-verification/1',result='running',
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    analysis_report_sha256=sha(args.analysis/'report.json'),observations=[])
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def scalar_residual(values,order):
    # Orthogonal polynomial sums, with no least-squares solver or feature import.
    t=np.arange(len(values),dtype=float);t-=t.mean()
    result=values-values.mean()
    if order>=1:
        result=result-t*(t@values)/(t@t)
    if order>=2:
        q=t*t;q-=q.mean();q-=t*(q@t)/(t@t)
        result=result-q*(q@values)/(q@q)
    return result


def relative_error(actual,expected):
    return float(np.max(abs(np.array(actual)-expected)/np.maximum(abs(expected),1e-12)))


try:
    original=json.loads((args.analysis/'report.json').read_text(encoding='utf-8'))
    assert original['result']=='pass'
    for source,digest in original['source_sha256'].items():
        assert sha(args.analysis/'exact_sources'/source)==digest,source
    plan=json.loads((args.analysis/'exact_sources/research/common_envelope_v1_plan.json').read_text(encoding='utf-8'))
    for ob in original['observations']:
        path=args.analysis/(ob['name']+'.npz');assert sha(path)==ob['source_power_sha256']
        data=np.load(path);starts,power=data['starts'],data['power']
        maxima={};checked=0
        for row in ob['rows']:
            mask=(starts>=row['start_frame'])&(starts+plan['size']<=row['stop_frame'])
            p=power[mask];n,bands,channels=p.shape
            values=np.empty_like(p)
            for band in range(bands):
                for channel in range(channels):
                    values[:,band,channel]=scalar_residual(np.log(p[:,band,channel])/2,row['detrend_order'])
            common=values.sum(axis=1)/bands
            all_var=np.sum(values**2,axis=(0,1))/(n*bands)
            common_var=np.sum(common**2,axis=0)/n
            # Colour energy from all pairwise log ratios, independent of the
            # implementation's explicit across-band mean subtraction.
            pair_var=np.zeros(channels);pair_slow=np.zeros(channels)
            bins=np.arange(1,int(np.ceil(plan['slow_band_hz'][1]*n*plan['hop']/plan['sample_rate'])))
            phase=2*np.pi*bins[:,None]*np.arange(n)[None,:]/n
            direct=(np.cos(phase)-1j*np.sin(phase))/n
            for i in range(bands):
                for j in range(i+1,bands):
                    difference=values[:,i,:]-values[:,j,:]
                    pair_var+=np.sum(difference**2,axis=0)/n/bands**2
                    pair_slow+=2*np.sum(abs(direct@difference)**2,axis=0)/bands**2
            common_slow=2*np.sum(abs(direct@common)**2,axis=0)
            total_slow=2*np.sum(abs(np.einsum('kn,nbc->kbc',direct,values))**2,axis=(0,1))/bands
            DB=20/np.log(10)
            expected=dict(common_variance_fraction_LR=common_var/all_var,
                slow_common_variance_fraction_LR=common_slow/total_slow,
                all_rms_db_LR=DB*np.sqrt(all_var),common_rms_db_LR=DB*np.sqrt(common_var),
                shape_rms_db_LR=DB*np.sqrt(pair_var),
                slow_common_rms_db_LR=DB*np.sqrt(common_slow),slow_shape_rms_db_LR=DB*np.sqrt(pair_slow))
            for key,value in expected.items():
                error=relative_error(row[key],value)
                maxima[key]=max(maxima.get(key,0),error)
                assert error<1e-10,(ob['name'],key,error)
            checked+=1
        report['observations'].append(dict(name=ob['name'],checked_rows=checked,maximum_relative_errors=maxima))
    report.update(result='pass',checked_rows=sum(r['checked_rows'] for r in report['observations']),
        maximum_relative_error=max(v for r in report['observations'] for v in r['maximum_relative_errors'].values()),
        method='Scalar orthogonal polynomial detrend; pairwise band log-ratio variance; direct trigonometric modulation DFT')
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=report['result'],checked_rows=report['checked_rows'],maximum_relative_error=report['maximum_relative_error'])))
