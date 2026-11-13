"""Independent native power and saved-cell scalar rejection-census audit."""
import argparse,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
from scipy.fft import rfft
from research_archive_v1 import load,save,sha


def close(x,y,tolerance=1e-10):
    error=float(np.max(abs(np.asarray(x)-np.asarray(y)),initial=0))
    assert error<=tolerance,(error,tolerance)
    return error


def scalar_peaks(log):
    result=[];i=1;n=len(log)
    while i<n-1:
        end=i
        while end<n-1 and log[end+1]==log[i]:end+=1
        if log[i]>log[i-1] and end<n-1 and log[end]>log[end+1]:
            k=(i+end)//2;level=log[k];minimum=[]
            for step in [-1,1]:
                at=k;low=level
                while 0<=at<n and log[at]<=level:
                    low=min(low,float(log[at]));at+=step
                minimum.append(low)
            result.append((k,level-max(minimum)))
        i=end+1
    return result


def check(path,actual,plan):
    z=np.load(path);audio=z['audio'];n=len(audio)
    assert audio.shape==(12000,2)
    hz,psd=signal.periodogram(audio,fs=48000,window='hann',detrend=False,scaling='density',axis=0)
    power=psd*4
    absolute_error=close(power,z['cells'],1e-12)
    win=np.hanning(12001)[:-1];spectrum=rfft(audio*win[:,None],axis=0)
    spectrum_error=close(spectrum,z['spectrum'],1e-10)
    close(z['total'],z['cells'].sum(axis=1),0)
    close(z['logged'],10*np.log10(np.maximum(z['total'],np.finfo(float).tiny)),0)
    parseval=close(power.sum(axis=0),np.sum((audio*win[:,None])**2,axis=0)/np.sum(win*win),1e-12)
    # Absolute PSD and transform verified first. Threshold arithmetic below uses
    # exact saved diagnostic cells, including meaningless numerical null peaks.
    total=z['total'];log=z['logged'];peaks=scalar_peaks(log)
    old_max=max(float(total[i]) for i in range(len(total)) if 200<=i*4<7000)
    close(old_max,actual['old_maximum_cell_power'],0)
    expected=[];max_prom=0.;max_freq=0.
    for b,(lo,hi) in enumerate(plan['upper_bands_hz']):
        indices=[i for i in range(len(total)) if lo<=i*4<hi]
        maximum=max(float(total[i]) for i in indices)
        for k,prom in peaks:
            if not lo<=k*4<hi:continue
            den=log[k-1]-2*log[k]+log[k+1]
            delta=max(-.5,min(.5,.5*(log[k-1]-log[k+1])/den)) if den else 0.
            prominent=prom>=8
            old_floor=bool(total[k]>=old_max*10**(-42/10) and total[k]>0)
            local_floor=bool(total[k]>=maximum*10**(-42/10) and total[k]>0)
            expected.append(dict(band=b,bin=k,frequency_hz=(k+delta)*4,power_LR=z['cells'][k].tolist(),
                prominence_db=prom,prominence_ok=prominent,old_floor_ok=old_floor,local_floor_ok=local_floor,
                old_domain_ok=200<=k*4<7000,old_accepted=bool(prominent and old_floor and 200<=k*4<7000),
                local_candidate=bool(prominent and local_floor)))
        stored=actual['bands'][b];subtotal=[v for v in expected if v['band']==b]
        counts={key:sum(row[key] for row in subtotal) for key in ['prominence_ok','old_floor_ok','local_floor_ok','old_domain_ok','old_accepted','local_candidate']}
        counts.update(raw_maxima=len(subtotal),prominent_rejected_by_old_floor=sum(v['prominence_ok'] and not v['old_floor_ok'] for v in subtotal),
            prominent_outside_old_domain=sum(v['prominence_ok'] and not v['old_domain_ok'] for v in subtotal))
        assert counts==stored['counts']
        sums=[math.fsum(z['cells'][i,c] for i in indices) for c in range(2)]
        close(sums,stored['power_LR'],1e-12);close(maximum,stored['maximum_cell_power'],0)
        mean=math.fsum(float(total[i]) for i in indices)/len(indices)
        geom=math.exp(math.fsum(math.log(float(total[i])) for i in indices)/len(indices)) if all(total[i]>0 for i in indices) else 0.
        expected_flat=geom/mean if mean>0 else None
        if expected_flat is None:assert stored['flatness'] is None
        else:close(expected_flat,stored['flatness'],1e-10)
        if mean>0:
            close(math.fsum(i*4*float(total[i]) for i in indices)/math.fsum(float(total[i]) for i in indices),stored['centroid_hz'],1e-8)
            cross=sum(complex(z['spectrum'][i,0])*complex(z['spectrum'][i,1]).conjugate() for i in indices)*2/(n*math.fsum(win*win))
            close([cross.real/math.sqrt(sums[0]*sums[1]),cross.imag/math.sqrt(sums[0]*sums[1])],stored['normalized_cross_LR'],1e-10)
        if maximum>0 and old_max>0:close(10*math.log10(maximum/old_max),stored['maximum_relative_to_old_db'],1e-10)
        elif stored['maximum_relative_to_old_db'] is not None:raise AssertionError('Undefined level')
        median=float(np.median([total[i] for i in indices]))
        if median>0:close(10*math.log10(maximum/median),stored['maximum_over_median_db'],1e-10)
        else:assert stored['maximum_over_median_db'] is None
    assert len(expected)==len(actual['peaks'])
    for first,second in zip(expected,actual['peaks']):
        assert set(first)==set(second)
        for key in first:
            if key=='prominence_db':max_prom=max(max_prom,close(first[key],second[key],1e-8))
            elif key=='frequency_hz':max_freq=max(max_freq,close(first[key],second[key],1e-8))
            elif key=='power_LR':close(first[key],second[key],0)
            else:assert first[key]==second[key],key
    return dict(maximum_cell_power_error=absolute_error,maximum_transform_error=spectrum_error,
                maximum_Parseval_error=parseval,maximum_saved_prominence_error=max_prom,maximum_saved_frequency_error=max_freq,
                peaks=len(expected))


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',known=0,windows=0,peaks=0,maximum_cell_power_error=0.,maximum_transform_error=0.,
       maximum_Parseval_error=0.,maximum_saved_prominence_error=0.,maximum_saved_frequency_error=0.)
try:
    report=load(a.input/'report.json');assert report['result']=='all48_upper_inventory_rejection_census_complete';plan=report['plan']
    assert plan['frames']==12000 and plan['sample_rate']==48000 and round(6/4)==2
    for name,digest in report['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    parent=a.workspace/'baselines/accel_candidate_prediction_v1'
    assert sha(parent/'manifest.json')==report['parent_manifest_sha256']
    table={row['path']:row['sha256'] for row in load(parent/'manifest.json')['files']}
    for name,digest in report['parent_files'].items():assert sha(parent/name)==digest==table[name]
    for name,actual in report['known'].items():
        assert actual==load(a.input/'known'/(name+'.json'))
        out=check(a.input/'known'/(name+'.npz'),actual,plan);r['known']+=1;r['peaks']+=out.pop('peaks')
        for key,value in out.items():r[key]=max(r[key],value)
    for summary in report['observations']:
        case=summary['segment'];rows=[]
        original=load(parent/f'evidence/observe1/{case}/initialization.json')['inventories']
        for i in range(summary['windows']):
            path=a.input/case/f'tile_{i:02d}.npz';actual=load(a.input/case/f'tile_{i:02d}.json')
            assert actual['window']==i
            close(np.load(path)['audio'],np.load(parent/f'evidence/observe1/{case}/native_{i:02d}.npz')['audio'],0)
            assert actual['old_inventory']['bin']==[v for v in original[i]['bin'] if v>=50]
            assert [v['bin'] for v in actual['peaks'] if v['old_accepted']]==[v for v in actual['old_inventory']['bin'] if v>=1000]
            out=check(path,actual,plan);r['windows']+=1;r['peaks']+=out.pop('peaks')
            for key,value in out.items():r[key]=max(r[key],value)
            rows.append(actual)
        for b,band in enumerate(summary['bands']):
            assert band['counts']=={key:sum(row['bands'][b]['counts'][key] for row in rows) for key in rows[0]['bands'][b]['counts']}
            close([min(row['bands'][b]['maximum_relative_to_old_db'] for row in rows),max(row['bands'][b]['maximum_relative_to_old_db'] for row in rows)],band['maximum_relative_to_old_db_range'],0)
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        values=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/filename);assert len(values)==count
        for name,digest in values.items():assert sha(repo/name)==digest
    assert r['known']==12 and r['windows']==48
    r.update(result='all48_upper_cells_rejections_descriptors_verified',input_report_sha256=sha(a.input/'report.json'),
             saved_cell_null_arithmetic_NOT_physical_precision=True,C_H_unchanged=612,old_voices_unchanged=67,
             source_identity_or_audio_promotion=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
