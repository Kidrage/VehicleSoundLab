"""Independent native sample, explicit oscillator and train-only prediction audit."""
import argparse, math, shutil, sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','observation','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy.fft import rfft
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
plan=load(a.observation/'exact_sources/research/accel_chirp_v1_plan.json')
r=dict(result='running',windows=0,lines=0,predictions=0,maximum_waveform_error=0.,maximum_support_error=0.,summaries=[])


def near(x,y,tol=1e-10):
    error=float(np.max(abs(np.asarray(x)-np.asarray(y)),initial=0.))
    assert error<=tol,(error,tol)
    return error


def audit_file(path,row):
    z=np.load(path);x=z['audio'];nominal=z['nominal'];v=z['parameters'];m=len(nominal);n=len(x)
    t=np.array([(i-n/2)/48000 for i in range(n)])
    angle=2*math.pi*(t[:,None]*(nominal+v[:m])+.5*t[:,None]**2*v[m:2*m])
    # Independent complex oscillators, not the fitted basis/evaluate implementation.
    osc=np.exp(1j*angle);co=np.column_stack((v[2*m:],z['right_coefficients']))
    complex_co=co[:m]-1j*co[m:2*m]
    stems=(osc[:,:,None]*complex_co[None,:,:]).real
    recon=stems.sum(axis=1)+co[-1];res=x-recon
    r['maximum_waveform_error']=max(r['maximum_waveform_error'],near(recon,z['reconstructed'],2e-12),near(res,z['residual'],2e-12))
    window=np.array([.5-.5*math.cos(2*math.pi*i/n) for i in range(n)]);weight=np.sqrt(window/n)
    design=np.column_stack((osc.real,osc.imag,np.ones(n)))
    singular=np.linalg.svd(weight[:,None]*design,compute_uv=False)
    rank=int(np.sum(singular>singular[0]*max(design.shape)*np.finfo(float).eps))
    assert rank==row['rank'] and row['success']==(row['status']>0)
    near(design.T@(weight**2*res[:,1]),np.zeros(2*m+1),1e-11)
    near(.5*math.fsum((weight*res[:,0])**2),row['cost'],1e-13)
    near(np.linalg.norm(weight[:,None]*res,axis=0)/np.linalg.norm(weight[:,None]*x,axis=0),row['weighted_relative_residual_LR'])
    widths=np.full(m,2.)
    if m>1:
        gaps=np.diff(nominal);widths=np.minimum(widths,.45*np.minimum(np.r_[np.inf,gaps],np.r_[gaps,np.inf]))
    near(widths,row['frequency_offset_bounds_hz']);near(z['lower'][:m],-widths);near(z['upper'][:m],widths)
    assert np.all(z['lower'][m:2*m]==-500) and np.all(z['upper'][m:2*m]==500)
    assert np.isneginf(z['lower'][2*m:]).all() and np.isposinf(z['upper'][2*m:]).all()
    amplitude=abs(complex_co);power=.5*np.mean(amplitude**2,axis=1)
    floor=power.max()*10**(-42/10);hz=np.arange(n//2+1)*48000/n
    # Exact-null controls make a residual-energy ratio ill-conditioned to the
    # independently summed oscillator roundoff. Audit waveform error above;
    # evaluate support with the validated stored residual arithmetic, retaining
    # the original gate (no relaxed energy/support threshold).
    # The observer subtracts stems then DC, while stored reconstruction adds
    # DC first; allow the arithmetic grouping bound, not a changed fit gate.
    grouping_bound=8*np.finfo(float).eps*max(float(abs(x).max()),float(abs(z['reconstructed']).max()),float(abs(co[-1]).max()))
    near(z['residual'],x-z['reconstructed'],grouping_bound)
    zr=rfft(z['residual']*window[:,None],axis=0)
    for k,line in enumerate(row['lines']):
        f=float(nominal[k]+v[k]);q=float(v[m+k]);extent=abs(q)*n/96000+8
        use=np.where((hz>=f-extent)&(hz<=f+extent))[0]
        zs=rfft(stems[:,k]*window[:,None],axis=0)
        before=np.array([math.fsum(abs(zr[use,ch]+zs[use,ch])**2) for ch in range(2)])
        after=np.array([math.fsum(abs(zr[use,ch])**2) for ch in range(2)])
        explained=1-np.divide(after,before,out=np.ones(2),where=before>0)
        r['maximum_support_error']=max(r['maximum_support_error'],near(explained,line['local_explained_fraction_LR'],1e-9))
        near([f,q],[line['frequency_hz'],line['chirp_hz_per_second']]);near(amplitude[k],line['amplitude_LR'])
        near(co[k],line['cosine_LR']);near(co[m+k],line['sine_LR'])
        near(np.angle(complex_co[k]),line['phase_at_midpoint_LR'])
        contact=abs(v[k])>=widths[k]-1e-7 or abs(q)>=500-1e-7
        eligible=bool(row['success'] and rank==2*m+1 and not contact and power[k]>=floor and power[k]>0 and min(explained)>=.8)
        assert contact==line['bound_contact'] and (power[k]>=floor)==line['relative_power_ok'] and eligible==line['eligible']
    r['windows']+=1;r['lines']+=m
    return z


try:
    report=load(a.observation/'report.json');r['observation_report_sha256']=sha(a.observation/'report.json')
    for name,h in report['sources'].items():assert sha(a.observation/'exact_sources'/name)==h
    known=load(a.observation/'controls.json')
    for name,row in known.items():
        if isinstance(row,dict) and 'lines' in row:audit_file(a.observation/'known'/(name+'.npz'),row)
    truth=known['analytic_truth'];n=12000;t=(np.arange(n)-n/2)/48000
    theta=2*np.pi*(t[:,None]*truth['frequencies']+.5*t[:,None]**2*truth['chirps'])
    amp=np.array(truth['amplitudes']);phase=np.array(truth['phases'])
    exact=np.column_stack((np.cos(theta+phase)@amp,np.cos(theta+phase+.37)@(amp*.67)))
    near(exact,np.load(a.observation/'known/dense_moving_and_fixed.npz')['audio'],1e-12)
    near(exact*.13,np.load(a.observation/'known/global_gain.npz')['audio'],1e-12)
    # Keep the observed non-linear FM counterexample; eligibility is only local fit support.
    r['nonlinear_FM_counterexample']=known['nonlinear_FM_mismatch']['lines']
    r['noise_eligible']={name:sum(line['eligible'] for line in known[name]['lines']) for name in ['same_mono_noise','independent_stereo_noise']}
    parent=a.workspace/'references/analysis/accel_ridges_v1/observe2'
    assert report['parent_report_sha256']==sha(parent/'report.json')
    native=a.workspace/'references/analysis/state_media_v1/F3_inspect1/native_reference.wav'
    spans={'F3_fifth1':[159,162],'F3_fifth2':[190,193],'F3_sixth':[194,200]}
    for name in plan['segments']:
        src=load(parent/(name+'.json'));rows=load(a.observation/name/'fits.json');e=src['evidence'];half=len(rows)//2
        with sf.SoundFile(native) as stream:
            assert stream.samplerate==48000 and stream.channels==2
            stream.seek(spans[name][0]*48000);raw=stream.read((spans[name][1]-spans[name][0])*48000,always_2d=True)
        assert np.array_equal(raw,np.load(parent/(name+'.npz'))['audio'])
        for i,row in enumerate(rows):
            z=audit_file(a.observation/name/f'tile_{i:02d}.npz',row)
            assert np.array_equal(z['audio'],raw[i*12000:(i+1)*12000])
            guide=e['rows'][i];assert row['ratio']==guide['ratio'] and row['guide_supported']==guide['guide_supported']
            selected=[k for k in range(len(e['reference_hz'])) if guide['moving']['state'][k]=='unique']
            order=sorted(selected,key=lambda k:src['inventories'][i]['bin'][guide['moving']['chosen'][k]])
            assert order==[line['reference_index'] for line in row['lines']]
            for j,k in enumerate(order):
                def f(at):return src['inventories'][at]['hz'][e['rows'][at]['moving']['chosen'][k]]
                neighbors=[at for at in [i-1,i+1] if 0<=at<len(rows) and e['rows'][at]['moving']['state'][k]=='unique']
                q=(f(i+1)-f(i-1))/.5 if len(neighbors)==2 else (f(neighbors[0])-f(i))/((neighbors[0]-i)*.25) if neighbors else 0.
                near(z['nominal'][j],src['inventories'][i]['bin'][guide['moving']['chosen'][k]]*4.)
                near(z['initial'][len(order)+j],max(-500+1e-6,min(500-1e-6,q)))
        predictions=load(a.observation/name/'predictions.json');errors=[]
        for expected in predictions:
            k=expected['reference_index']
            def selection(begin,end):
                return [(i,line) for i in range(begin,end) if rows[i]['guide_supported'] for line in rows[i]['lines'] if line['reference_index']==k and line['eligible']]
            train=selection(0,half);check=selection(half,len(rows))
            assert expected['training_count']==len(train) and expected['check_count']==len(check)
            if len(train)<3 or len(check)<3:assert expected['status']=='insufficient';continue
            assert expected['status']=='compared'
            f0=float(np.median([line['frequency_hz']/rows[i]['ratio'] for i,line in train]))
            a0=np.array([math.sqrt(math.fsum(line['amplitude_LR'][ch]**2 for _,line in train)/len(train)) for ch in range(2)])
            near(f0,expected['training_frequency_hz']);near(a0,expected['training_amplitude_LR'])
            ferr=[];dbs=[]
            for (i,line),saved in zip(check,expected['check']):
                assert saved['tile']==i
                error=line['frequency_hz']-f0*rows[i]['ratio'];db=[20*math.log10(line['amplitude_LR'][ch]/a0[ch]) for ch in range(2)]
                near(error,saved['frequency_error_hz']);near(db,saved['amplitude_error_db_LR']);ferr.append(abs(error));dbs.extend(map(abs,db))
            assert len(expected['check'])==len(check)
            near(max(ferr),expected['maximum_frequency_error_hz']);near(np.median(dbs),expected['median_absolute_amplitude_error_db'])
            assert expected['diagnostic_target_met']==(max(ferr)<=4 and np.median(dbs)<=3)
            errors.append([max(ferr),float(np.median(dbs))]);r['predictions']+=len(check)
        r['summaries'].append(dict(segment=name,compared_lines=len(errors),frequency_error_range_hz=[min(v[0] for v in errors),max(v[0] for v in errors)],
            median_amplitude_error_range_db=[min(v[1] for v in errors),max(v[1] for v in errors)],
            frequency_target_met=sum(v[0]<=4 for v in errors),amplitude_target_met=sum(v[1]<=3 for v in errors),
            both_targets_met=sum(v[0]<=4 and v[1]<=3 for v in errors),
            optimizer_failed_tiles=[row['tile'] for row in rows if not row['success']],
            bound_contact_lines=sum(line['bound_contact'] for row in rows for line in row['lines'])))
    r.update(result='native_waveforms_support_and_training_only_predictions_verified',pristine_holdout=False,physical_identity=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
