"""Independent scalar registration, physical FIR, inverse clock and native PSD."""
import argparse
import bisect
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],inputs={},maximum_errors={})
    def check(name,x,y,scale,gate=2e-11):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
        if scale==0:
            assert np.count_nonzero(x)==np.count_nonzero(y)==0;error=0.
        else:error=float(np.max(abs(x-y))/scale)
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.))
        assert error<gate,(name,error,gate)
    try:
        source=load(a.study/'report.json');assert source['result']=='native_clock_six_real_intervals_prepared'
        r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
        for name,digest in source['inputs'].items():assert sha(name)==digest
        for name,digest in source['sources'].items():assert sha(a.study/'exact_sources'/name)==digest
        for c in source['cases']:
            path=a.study/c['file'];assert sha(path)==c['sha256'];r['inputs'][str(path)]=sha(path)
            assert sha(c['original_preparation'])==c['original_preparation_sha256']
            with np.load(path) as f:z={k:f[k] for k in f.files}
            with np.load(c['original_preparation']) as f:original={k:f[k] for k in f.files}
            context_path=Path(c['context_report']);archive=context_path.parents[2]
            manifest=load(archive/'manifest.json');entries={v['path']:v['sha256'] for v in manifest['files']}
            assert entries[context_path.relative_to(archive).as_posix()]==sha(context_path)
            context=load(context_path);row=next(v for v in context['cases'] if v['label']==c['label'])
            assert c['source_cutoff_hz']==row['info']['cutoff_hz']
            coords=original['target_source_coordinates'];origin=float(original['source_start'])
            first=math.ceil((float(coords[0])-origin)*48000);stop=math.floor((float(coords[-1])-origin)*48000)+1
            assert first==int(z['first'])==c['native_first'] and stop==int(z['stop'])==c['native_stop']
            assert np.array_equal(z['raw_native_target'],original['native'][first:stop])
            assert float(z['native_start'])==origin+first/48000
            for name in ('source_coordinates','target_source_coordinates','positions','original_positions','orders'):
                assert np.array_equal(z[name],original[name]),name
            assert np.array_equal(z['orders'],np.arange(1,289))
            k=np.arange(-512,513);cutoff=c['source_cutoff_hz']
            base=np.array([2*cutoff/48000 if i==0 else math.sin(2*math.pi*cutoff*i/48000)/(math.pi*i) for i in k])
            kernel=base*np.i0(12*np.sqrt(1-(k/512)**2))/np.i0(12);kernel/=math.fsum(kernel)
            check('explicit_source_FIR_taps',z['source_FIR_taps'],kernel,float(np.max(abs(kernel))))
            direct=np.column_stack([np.convolve(original['native'][:,ch],kernel,mode='valid') for ch in (0,1)])[first-512:stop-512]
            scale=float(np.max(abs(original['native'])))
            check('every_native_source_FIR_sample',z['source_FIR_only_target'],direct,scale)
            relative=z['source_coordinates']-z['source_coordinates'][0]
            count=stop-first
            for up in (16,32):
                ticks=np.arange(-128*up,(count-1)*up+128*up+1)
                times=float(z['native_start'])-z['source_coordinates'][0]+ticks/(48000*up)
                assert times[0]>=0 and times[-1]<=relative[-1]
                slots=np.searchsorted(relative,times,side='right')-1
                slots[slots==len(relative)-1]=len(relative)-2
                inverse=slots+(times-relative[slots])/(relative[slots+1]-relative[slots])
                check('all_inverse_query_cycles'+str(up),z['query'+str(up)]/1024,inverse/1024,1.)
                for index in np.unique(np.linspace(0,len(times)-1,97,dtype=int)):
                    j=min(bisect.bisect_right(relative,float(times[index]))-1,len(relative)-2)
                    q=j+(float(times[index])-float(relative[j]))/float(relative[j+1]-relative[j])
                    check('scalar_inverse_cycles',z['query'+str(up)][index]/1024,q/1024,1.)
            for label,audio in (('raw',z['raw_native_target']),('FIR_only',z['source_FIR_only_target'])):
                starts=np.arange(0,len(audio)-4096+1,256)
                frames=np.array([audio[s:s+4096] for s in starts]);w=signal.windows.hann(4096,sym=False)
                kwargs=dict(fs=48000,window=w,nperseg=4096,noverlap=0,detrend=False,scaling='density',axis=1)
                frequency,psd=signal.welch(frames,**kwargs)
                _,cross=signal.csd(frames[:,:,1],frames[:,:,0],**kwargs)
                groups=np.searchsorted([3000,6000,8000,10000,14000],frequency,side='right')
                power=np.stack([psd[:,groups==b].sum(axis=1)*48000/4096 for b in range(6)],axis=1)
                C=np.stack([cross[:,groups==b].sum(axis=1)*48000/4096 for b in range(6)],axis=1)
                energy=float(np.max(power))
                check('independent_native_bands_'+label,z[label+'_broad_power'],power,energy)
                check('independent_native_LR_'+label,z[label+'_broad_Gram'][:,:,0,1],C,energy)
                # Linear differences are checked in actual units without a
                # gain fit. Normalized tiny-band statistics stay in output.
            delta=z['FIR_only_broad_mean_power']-z['raw_broad_mean_power']
            check('signed_native_power_changes',c['source_FIR_only_signed_changes']['broad']['power_change_FS2'],delta,
                float(np.max(z['raw_broad_mean_power'])))
            r['cases'].append(dict(label=c['label'],all_preparation_checks_passed=True,native_frames=count,
                source_cutoff_hz=cutoff,both_16x_32x_real_context_verified=True,
                actual_fitted_native_render_qualified=False))
            save(a.out/'report.json',r);print('NATIVE_PREPARATION_AUDIT',c['label'],'PASS',flush=True)
        assert len(r['cases'])==6
        r.update(result='independent_native_clock_real_preparation_verified',all_preparation_qualified=True,
            producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),
            no_actual_fitted_native_or_C_or_hearing_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
