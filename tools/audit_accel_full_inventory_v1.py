"""Independent explicit native waves/support, reference maps and coverage audit."""
import argparse,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.fft import rfft
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
r=dict(result='running',windows=0,lines=0,maximum_waveform_error=0.,maximum_support_error=0.,maximum_power_error=0.,summaries=[])
bands=load(repo/'research/accel_coverage_v1_plan.json')['bands_hz']


def near(x,y,tol=1e-10):
    error=float(abs(np.asarray(x)-np.asarray(y)).max(initial=0));assert error<=tol,(error,tol)
    return error


def native_powers(x,y):
    n=len(x);w=np.hanning(n+1)[:-1];X=rfft(x*w[:,None],axis=0);Y=rfft(y*w[:,None],axis=0);R=X-Y
    weight=np.full(len(X),2.);weight[[0,-1]]=1;weight/=n*math.fsum(w*w)
    arrays=dict(source=abs(X)**2,model=abs(Y)**2,residual=abs(R)**2,interference=2*(Y.real*R.real+Y.imag*R.imag))
    return {key:np.array([[math.fsum(float(value[i,c])*weight[i] for i in range(len(X)) if lo<=i*4<hi)
        for c in range(2)] for lo,hi in bands]) for key,value in arrays.items()}


def audit_wave(path,row,coverage=False):
    z=np.load(path);x=z['audio'];nominal=z['nominal'];v=z['parameters'];m=len(nominal);n=len(x)
    t=np.array([(i-n/2)/48000 for i in range(n)])
    phase=2*np.pi*(t[:,None]*(nominal+v[:m])+.5*t[:,None]**2*v[m:2*m]);osc=np.exp(1j*phase)
    co=np.column_stack((v[2*m:],z['right_coefficients']));stems=(osc[:,:,None]*(co[:m]-1j*co[m:2*m])[None,:,:]).real
    y=stems.sum(axis=1)+co[-1];res=x-y
    r['maximum_waveform_error']=max(r['maximum_waveform_error'],near(y,z['reconstructed'],2e-12),near(res,z['residual'],2e-12))
    w=np.array([.5-.5*math.cos(2*np.pi*i/n) for i in range(n)]);weight=np.sqrt(w/n)
    design=np.column_stack((osc.real,osc.imag,np.ones(n)));singular=np.linalg.svd(weight[:,None]*design,compute_uv=False)
    rank=int(sum(singular>singular[0]*max(design.shape)*np.finfo(float).eps))
    assert rank==row['rank'] and row['success']==(row['status']>0)
    near(design.T@(weight**2*res[:,1]),np.zeros(2*m+1),1e-11)
    near(.5*math.fsum((weight*res[:,0])**2),row['cost'],1e-12)
    near(np.linalg.norm(weight[:,None]*res,axis=0)/np.linalg.norm(weight[:,None]*x,axis=0),row['weighted_relative_residual_LR'])
    width=np.full(m,2.)
    if m>1:
        gaps=np.diff(nominal);width=np.minimum(width,.45*np.minimum(np.r_[np.inf,gaps],np.r_[gaps,np.inf]))
    near(width,row['frequency_offset_bounds_hz']);near(z['lower'][:m],-width);near(z['upper'][:m],width)
    assert np.all(z['lower'][m:2*m]==-500) and np.all(z['upper'][m:2*m]==500)
    amplitude=np.hypot(co[:m],co[m:2*m]);power=.5*np.mean(amplitude**2,axis=1);floor=power.max()*10**(-42/10)
    grouping=8*np.finfo(float).eps*max(float(abs(x).max()),float(abs(y).max()),float(abs(co[-1]).max()))
    near(z['residual'],x-z['reconstructed'],grouping)
    zr=rfft(z['residual']*w[:,None],axis=0);hz=np.arange(n//2+1)*4
    eligible=[]
    for k,line in enumerate(row['lines']):
        f=nominal[k]+v[k];q=v[m+k];extent=abs(q)*n/96000+8;use=(hz>=f-extent)&(hz<=f+extent)
        zl=rfft(stems[:,k]*w[:,None],axis=0)
        before=np.array([math.fsum(abs((zr+zl)[use,c])**2) for c in range(2)])
        after=np.array([math.fsum(abs(zr[use,c])**2) for c in range(2)])
        explained=1-np.divide(after,before,out=np.ones(2),where=before>0)
        r['maximum_support_error']=max(r['maximum_support_error'],near(explained,line['local_explained_fraction_LR'],1e-9))
        contact=bool(abs(v[k])>=width[k]-1e-7 or abs(q)>=500-1e-7)
        good=bool(row['success'] and rank==2*m+1 and not contact and power[k]>=floor and power[k]>0 and min(explained)>=.8)
        assert good==line['eligible'] and contact==line['bound_contact'] and (power[k]>=floor)==line['relative_power_ok']
        near([f,q],[line['frequency_hz'],line['chirp_hz_per_second']]);near(amplitude[k],line['amplitude_LR'])
        near(co[k],line['cosine_LR']);near(co[m+k],line['sine_LR']);eligible.append(k)
    if coverage:
        for tag,chosen in [('all',list(range(m))),('eligible',[k for k,line in enumerate(row['lines']) if line['eligible']])]:
            model=co[-1]+stems[:,chosen].sum(axis=1)
            for key,power in native_powers(x,model).items():
                r['maximum_power_error']=max(r['maximum_power_error'],near(power,row['coverage'][tag][key],1e-12))
    r['windows']+=1;r['lines']+=m
    return z


try:
    report=load(a.input/'report.json');assert report['result']=='full_original_reference_native_fits_complete'
    for name,h in report['sources'].items():assert sha(a.input/'exact_sources'/name)==h==sha(repo/name)
    known=load(a.input/'controls.json')
    for name,row in known['original_controls'].items():
        if isinstance(row,dict) and 'lines' in row:audit_wave(a.input/'known'/(name+'.npz'),row)
    audit_wave(a.input/'known/omitted_dominant.npz',known['omitted_dominant'])
    parent=a.workspace/'baselines/accel_ridges_v1/evidence/observe2'
    for name in report['plan']['segments']:
        source=load(parent/(name+'.json'));audio=np.load(parent/(name+'.npz'))['audio'];cor=load(a.input/name/'correspondence.json')
        assert cor['reference_hz']==source['inventories'][0]['hz']
        assert cor['parent_json_sha256']==sha(parent/(name+'.json')) and cor['parent_audio_sha256']==sha(parent/(name+'.npz'))
        refs=cor['reference_hz'];graphs=[]
        for inv,guide,expected in zip(source['inventories'],source['guides'],cor['graphs']):
            ratio=guide['ratio'];edges=[]
            for k,f in enumerate(refs):
                center=f*ratio;radius=4*(1+ratio)+center*(2**(.5/192)-1)
                near(center,expected['expected_hz'][k]);near(radius,expected['radius_hz'][k])
                edges.append([int(abs(center-observed)<=radius) for observed in inv['hz']])
            assert edges==expected['edges']
            for k,edge in enumerate(edges):
                indices=[j for j,yes in enumerate(edge) if yes];unique=len(indices)==1 and sum(other[indices[0]] for other in edges)==1
                state='unique' if unique else 'ambiguous' if indices else 'absent'
                assert state==expected['state'][k] and (indices[0] if unique else None)==expected['chosen'][k]
            graphs.append(expected)
        rows=load(a.input/name/'fits.json');old=load(a.workspace/'baselines/accel_chirp_v1/evidence/observe1'/name/'fits.json')
        assert len(rows)==len(graphs);dominant=max(range(len(refs)),key=lambda k:sum(source['inventories'][0]['power_LR'][k]))
        assert refs[dominant]<300
        for i,row in enumerate(rows):
            z=audit_wave(a.input/name/f'tile_{i:02d}.npz',row,coverage=True)
            assert np.array_equal(z['audio'],audio[i*12000:(i+1)*12000])
            assert row['ratio']==cor['guides'][i]['ratio'] and row['guide_supported']==cor['guides'][i]['supported']
            assert row['old_fit_success']==old[i]['success'] and row['old_eligible_count']==sum(v['eligible'] for v in old[i]['lines'])
            selected=[k for k,state in enumerate(graphs[i]['state']) if state=='unique']
            order=sorted(selected,key=lambda k:source['inventories'][i]['bin'][graphs[i]['chosen'][k]])
            assert [line['reference_index'] for line in row['lines']]==order
            for j,k in enumerate(order):
                def frequency(v):return source['inventories'][v]['hz'][graphs[v]['chosen'][k]]
                neighbors=[v for v in [i-1,i+1] if 0<=v<len(rows) and graphs[v]['state'][k]=='unique']
                q=(frequency(i+1)-frequency(i-1))/.5 if len(neighbors)==2 else (frequency(neighbors[0])-frequency(i))/((neighbors[0]-i)*.25) if neighbors else 0.
                near(z['nominal'][j],source['inventories'][i]['bin'][graphs[i]['chosen'][k]]*4)
                near(z['initial'][len(order)+j],max(-500+1e-6,min(500-1e-6,q)))
        aggregate={}
        for tag in ['all','eligible']:
            powers={key:np.sum([row['coverage'][tag][key] for row in rows],axis=0) for key in ['source','model','residual','interference']}
            aggregate[tag]=dict(powers={key:value.tolist() for key,value in powers.items()},
                model_over_source=(powers['model']/powers['source']).tolist(),residual_over_source=(powers['residual']/powers['source']).tolist())
        selected=[(row['tile'],line) for row in rows if row['guide_supported'] for line in row['lines'] if line['reference_index']==dominant and line['eligible']]
        r['summaries'].append(dict(segment=name,dominant_reference=dominant,dominant_initial_hz=refs[dominant],
            dominant_eligible_tiles=[i for i,_ in selected],failed_fit_tiles=[row['tile'] for row in rows if not row['success']],
            guide_failed_tiles=[row['tile'] for row in rows if not row['guide_supported']],
            successful=sum(row['success'] for row in rows),eligible_lines=sum(line['eligible'] for row in rows for line in row['lines']),aggregate=aggregate))
    invariant=a.workspace/'baselines/idle_microtexture_c_v1/inputs'
    for filename,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        table=load(invariant/filename);assert len(table)==count
        for name,h in table.items():assert sha(repo/name)==h,name
    r.update(result='all_original_inventory_native_fits_maps_and_coverage_verified',input_report_sha256=sha(a.input/'report.json'),
        C_H_unchanged=612,old_voices_unchanged=67,common_phase_or_RPM_load=False,new_audio_or_profile=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print({key:r[key] for key in ['result','windows','lines','maximum_waveform_error','maximum_support_error','maximum_power_error']},flush=True)
