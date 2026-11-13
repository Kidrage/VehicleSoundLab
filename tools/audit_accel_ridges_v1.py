"""Independent FFT, native peak scan, assignment graph and all class decisions."""
import argparse,math,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--observation',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy.fft import rfft
from research_archive_v1 import load,save,sha
plan=load(a.observation/'exact_sources/research/accel_ridges_v1_plan.json')
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',inventory_count=0,assignment_count=0,class_count=0,maximum_hz_error=0,maximum_prominence_error=0)


def scan(audio,expected):
    n=len(audio);df=plan['rate']/n
    window=np.array([.5-.5*math.cos(2*math.pi*i/n) for i in range(n)])
    z=rfft(audio*window[:,None],axis=0);power=(z.real*z.real+z.imag*z.imag)*2/(n*math.fsum(window*window))
    power[0]*=.5;power[-1]*=.5;total=power[:,0]+power[:,1]
    logged=np.array([10*math.log10(max(float(v),np.finfo(float).tiny)) for v in total])
    raw=[i for i in range(1,len(logged)-1) if logged[i]>logged[i-1] and logged[i]>logged[i+1]]
    # SciPy applies distance before prominence. Prioritize by peak height;
    # ties in these fixtures must not silently choose another inventory.
    priority=np.argsort(logged[raw]);distance=max(1,round(plan['peak_spacing_hz']/df));keep=set(raw)
    for at in reversed(priority):
        i=raw[at]
        if i not in keep:continue
        for j in raw:
            if j!=i and abs(j-i)<distance:keep.discard(j)
    selected=[];prom=[];lo,hi=plan['inventory_hz']
    maximum=max(total[i] for i in range(len(total)) if lo<=i*df<hi)
    for i in sorted(keep):
        if not lo<=i*df<hi or total[i]<maximum*10**(plan['peak_floor_db_relative_to_maximum']/10):continue
        minima=[]
        for direction in [-1,1]:
            j=i;minimum=logged[i]
            while 0<=j<len(logged) and logged[j]<=logged[i]:minimum=min(minimum,logged[j]);j+=direction
            minima.append(minimum)
        prominence=logged[i]-max(minima)
        if prominence>=plan['peak_prominence_db']:selected.append(i);prom.append(prominence)
    assert selected==expected['bin'],(selected,expected['bin'])
    for i,bin_number in enumerate(selected):
        b=bin_number;denominator=logged[b-1]-2*logged[b]+logged[b+1]
        d=.5*(logged[b-1]-logged[b+1])/denominator if denominator else 0
        f=(b+max(-.5,min(.5,d)))*df
        error=abs(f-expected['hz'][i]);r['maximum_hz_error']=max(r['maximum_hz_error'],error);assert error<1e-8
        error=abs(prom[i]-expected['prominence_db'][i]);r['maximum_prominence_error']=max(r['maximum_prominence_error'],error);assert error<1e-7
        assert np.max(abs(power[b]-expected['power_LR'][i]))<1e-12
    r['inventory_count']+=1


def assignment(refs,observed,ratio,expected):
    edges=[]
    for i,f in enumerate(refs):
        center=f*ratio;radius=4*(1+ratio)+center*(math.pow(2,.5/192)-1)
        assert abs(center-expected['expected_hz'][i])<1e-9 and abs(radius-expected['radius_hz'][i])<1e-10
        edges.append([int(abs(center-v)<=radius) for v in observed])
    assert edges==expected['edges']
    for i,row in enumerate(edges):
        indices=[j for j,value in enumerate(row) if value]
        unique=len(indices)==1 and sum(other[indices[0]] for other in edges)==1
        state='unique' if unique else 'ambiguous' if indices else 'absent'
        assert state==expected['state'][i] and (indices[0] if unique else None)==expected['chosen'][i]
    r['assignment_count']+=1


def run_length(indices):
    runs=[];run=[]
    for i in indices:
        if run and i!=run[-1]+1:runs.append(len(run));run=[]
        run.append(i)
    return max(runs+[len(run)])


def audit(audio,inventories,evidence,guides=None):
    refs=evidence['reference_hz'];n=plan['tile_frames']
    lo,hi=plan['reference_hz'];assert refs==[v for v in inventories[0]['hz'] if lo<=v<hi]
    for i,inv in enumerate(inventories):
        scan(audio[i*n:(i+1)*n],inv);row=evidence['rows'][i]
        if guides is not None:assert row['ratio']==guides[i]['ratio'] and row['guide_supported']==guides[i]['supported']
        for name,ratio in [('moving',row['ratio']),('fixed',1.)]:assignment(refs,inv['hz'],ratio,row[name])
        for k,f in enumerate(refs):
            moving=row['moving'];fixed=row['fixed']
            eligible=bool(i>0 and row['guide_supported'] and abs(f*row['ratio']-f)>2*max(moving['radius_hz'][k],fixed['radius_hz'][k]))
            assert eligible==row['eligible'][k]
    counts=dict(moving=0,fixed=0,uncertain=0)
    for k,expected in enumerate(evidence['classes']):
        used=[i for i,row in enumerate(evidence['rows']) if row['eligible'][k]]
        hits={name:[i for i in used if evidence['rows'][i][name]['state'][k]=='unique'] for name in ['moving','fixed']}
        fraction={name:len(hit)/len(used) if used else 0 for name,hit in hits.items()}
        label='uncertain'
        for name,other in [('moving','fixed'),('fixed','moving')]:
            if len(used)>=5 and fraction[name]>=.8 and fraction[other]<=.2 and run_length(hits[name])>=5:label=name
        assert used==expected['eligible_tiles'] and hits==expected['hypothesis_unique_tiles'] and fraction==expected['support_fraction']
        assert label==expected['classification'] and all(run_length(hits[name])==expected['longest_consecutive'][name] for name in hits)
        counts[label]+=1;r['class_count']+=1
    assert counts==evidence['counts']


try:
    import shutil
    shutil.copy2(__file__,a.out/'executed_audit.py');r['observation_report_sha256']=sha(a.observation/'report.json')
    controls=load(a.observation/'controls.json');known=np.load(a.observation/'known.npz')
    for name in known.files:audit(known[name],controls[name]['inventories'],controls[name]['evidence'])
    for name in plan['segments']:
        row=load(a.observation/(name+'.json'));audio=np.load(a.observation/(name+'.npz'))['audio']
        audit(audio,row['inventories'],row['evidence'],row['guides'])
    r.update(result='all_native_inventories_assignments_and_classifications_passed',
        dense_comb_limitation=controls['dense_comb_limitation'],source_or_physical_identity_established=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
