"""Preserve the first meter failure and compare both independent FFT windows."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','failed-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_diagnosis.py')
    failure=load(a.failed_audit/'report.json')
    assert failure['result']=='failed' and 'line_CV' in failure['error']
    with np.load(a.study/'mono.npz') as f:z={k:f[k] for k in f.files}
    size,hop,rate=int(z['size']),int(z['hop']),float(z['rate'])
    raw=np.array([z['audio'][s:s+size] for s in z['starts']])
    bins=4*np.arange(1,289)
    ids=np.searchsorted([3000,6000,8000,10000,14000],64*np.arange(1,289),side='right')
    r=dict(result='roundoff_diagnosis',original_failure=failure,window_comparisons=[],
        inputs={str(q):sha(q) for q in (a.study/'report.json',a.study/'mono.npz',a.failed_audit/'report.json')},
        fixture_orders=[5,65,110,140,185,300],line_orders=[1,288],
        interpretation='Order300 is deliberately retained. Its19200Hz tone belongs to the complete broad spectrum but not the1..288 line centers. Tiny positive line-band leakage is not trustworthy physical modulation.',
        no_fixture_or_gate_or_failed_evidence_changes=True)
    for name,w in (('scipy_periodic_hann',signal.windows.hann(size,sym=False)),
                   ('declared_discrete_hann',.5-.5*np.cos(2*np.pi*np.arange(size)/size))):
        frequency,psd=signal.welch(raw,fs=rate,window=w,nperseg=size,noverlap=0,detrend=False,scaling='density',axis=1)
        gain=rate*np.dot(w,w)/w.sum()**2
        power=np.stack([psd[:,bins[ids==b]].sum(axis=1)*gain for b in range(6)],axis=1)
        mean=power.mean(axis=0);cv=power.std(axis=0)/mean
        r['window_comparisons'].append(dict(window=name,
            last_line_band_power=mean[-1].tolist(),last_line_band_CV=cv[-1].tolist(),
            last_line_band_CV_difference=(cv[-1]-z['line_CV'][-1]).tolist(),
            maximum_power_error_relative_fixture=float(np.max(abs(power-z['line_power']))/np.max(z['broad_mean_power'])),
            last_broad_band_power=z['broad_mean_power'][-1].tolist()))
    save(a.out/'report.json',r)
    print(r['window_comparisons'],flush=True)


if __name__=='__main__':main()
