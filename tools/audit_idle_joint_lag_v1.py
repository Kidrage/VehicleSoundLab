"""Independent convolution, general cumulant partitions and direct overlap checks."""
import argparse,math,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve
from research_archive_v1 import load,save,sha

PAIRS=[(b,c) for b in range(4) for c in range(b,4)]


def total(x):return math.fsum(np.asarray(x).tolist())


def partitions(items):
    if not items:
        yield [];return
    first=items[0]
    for rest in partitions(items[1:]):
        yield [[first]]+[block[:] for block in rest]
        for i in range(len(rest)):
            yield [([first]+block if i==j else block[:]) for j,block in enumerate(rest)]


PARTITIONS=list(partitions([0,1,2,3]))
assert len(PARTITIONS)==15


def independent_curves(x,lags):
    n=len(x);x=x-np.array([total(x[:,b])/n for b in range(4)])
    variance=np.array([total(x[:,b]**2)/n for b in range(4)])
    first=np.maximum(0,-lags);last=np.minimum(n,n-lags);count=n-abs(lags)
    prefix={p:np.vstack((np.zeros(4),np.cumsum(x**p,axis=0))) for p in [1,2]}
    cumulants=[];covariances=[]
    for b,c in PAIRS:
        moments={(0,0):np.ones(len(lags))}
        for p in [1,2]:moments[p,0]=(prefix[p][last,b]-prefix[p][first,b])/count
        for q in [1,2]:moments[0,q]=(prefix[q][last+lags,c]-prefix[q][first+lags,c])/count
        for p in [1,2]:
            for q in [1,2]:
                values=fftconvolve(x[::-1,b]**p,x[:,c]**q,mode='full')
                moments[p,q]=values[n-1+lags]/count
        terms=[]
        for partition in PARTITIONS:
            value=np.ones(len(lags))*((-1)**(len(partition)-1)*math.factorial(len(partition)-1))
            for block in partition:
                p=sum(index<2 for index in block);q=len(block)-p
                value*=moments[p,q]
            terms.append(value)
        cumulants.append(np.sum(terms,axis=0))
        covariances.append(moments[1,1]-moments[1,0]*moments[0,1])
    K=np.array(cumulants)
    normalized=np.array([K[j]/variance[b]/variance[c] for j,(b,c) in enumerate(PAIRS)])
    covariance=np.array([covariances[j]/np.sqrt(variance[b]*variance[c]) for j,(b,c) in enumerate(PAIRS)])
    return K,normalized,variance,covariance


def direct(x,lags):
    mean=np.array([total(x[:,b])/len(x) for b in range(4)])
    v=np.array([total((x[:,b]-mean[b])**2)/len(x) for b in range(4)])
    result=np.empty((10,len(lags)))
    for j,(b,c) in enumerate(PAIRS):
        for k,lag in enumerate(lags):
            first=max(0,-lag);last=min(len(x),len(x)-lag)
            u=x[first:last,b].copy();w=x[first+lag:last+lag,c].copy()
            u-=np.mean(u);w-=np.mean(w)
            result[j,k]=(np.mean((u*w)**2)-np.mean(u*u)*np.mean(w*w)-2*np.mean(u*w)**2)/v[b]/v[c]
    return result


def local_normalize(x):
    out=x.copy()
    for first in range(0,len(x),1920):
        for b in range(4):
            part=x[first:first+1920,b]
            out[first:first+1920,b]/=math.sqrt(total(part*part)/1920)
    return out


def filter_polynomial(x,sos):
    size=1<<int(math.ceil(math.log2(len(x)+131072)))
    frequency=np.arange(size//2+1)/size
    z=np.cos(-2*np.pi*frequency)+1j*np.sin(-2*np.pi*frequency)
    X=np.fft.rfft(x,n=size);rows=[]
    for cascade in sos:
        H=np.ones(len(z),complex)
        for s in cascade:H*=(s[0]+s[1]*z+s[2]*z*z)/(s[3]+s[4]*z+s[5]*z*z)
        rows.append(np.fft.irfft(H*X,n=size)[:len(x)])
    return np.array(rows).T


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',observations=0,curves=0)
try:
    observed=load(a.input/'report.json')
    assert observed['result']=='all33_idle_lag_observations_complete_NO_sound_promotion'
    for name,digest in observed['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    tables={}
    for name,digest in observed['parent_manifests'].items():
        path=a.workspace/'baselines'/name/'manifest.json';assert sha(path)==digest
        tables[name]={v['path']:v['sha256'] for v in load(path)['files']}
    for path,digest in observed['inputs'].items():
        relative=Path(path).relative_to(a.workspace/'baselines')
        assert sha(path)==digest==tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
    lags=np.arange(-1920,1921,48);zero=40
    maximum_curve_error=maximum_direct_error=maximum_filter_error=0.
    for name in ['delayed_common','slow_common_amplitude']:
        with np.load(a.input/'known'/(name+'.npz')) as archive:known={key:archive[key] for key in archive.files}
        K,Q,v,cov=independent_curves(known['audio'],lags)
        error=float(abs(Q-known['normalized']).max());maximum_curve_error=max(maximum_curve_error,error)
        assert error<1e-9
        error=float(abs(direct(known['audio'],lags)-Q).max());maximum_direct_error=max(maximum_direct_error,error)
        assert error<1e-9
        if name=='delayed_common':
            assert np.array_equal(known['audio'][96:,1],known['audio'][:-96,0])
            assert np.all(known['audio'][:96,1]==0)
            assert int(lags[np.argmax(Q[PAIRS.index((0,1))])])==96
    parent=a.workspace/'baselines/idle_joint_cumulant_v1/evidence/observe1'
    prior=load(parent/'report.json')
    with np.load(parent/'architecture.npz') as archive:architecture={key:archive[key] for key in archive.files}
    cache_path=None;cache=None;main_K=None
    # The plan says13 but explicitly lists11 points. Follow that list; preserve its counting typo.
    direct_lags=np.array([0,-48,48,-240,240,-480,480,-960,960,-1920,1920])
    direct_indices=[int(np.flatnonzero(lags==lag)[0]) for lag in direct_lags]
    for row in observed['observations']:
        if row.get('main'):
            filtered=filter_polynomial(architecture['main'][:,0],architecture['sos'])[4800:-4800]
        elif 'source_npz' in row:
            with np.load(row['source_npz']) as archive:data={key:archive[key] for key in archive.files}
            filtered=filter_polynomial(data['audio'][:,0],architecture['sos'])[4800:-4800]
            if 'filtered' in data:
                error=float(abs(filtered-data['filtered']).max());maximum_filter_error=max(maximum_filter_error,error)
                assert error<1e-11
        else:
            if cache_path!=row['path']:
                audio,rate=sf.read(row['path'],always_2d=True);assert rate==48000
                cache=filter_polynomial(audio[:,0],architecture['sos']);cache_path=row['path']
            filtered=cache[row['block']*144000+4800:(row['block']+1)*144000-4800]
        assert sha(a.input/row['file'])==row['sha256']
        with np.load(a.input/row['file']) as archive:data={key:archive[key] for key in archive.files}
        assert np.array_equal(data['lags'],lags)
        old=next(v for v in prior['observations'] if v['label']==row['label'])
        for transform,x in [('raw',filtered),('local40ms',local_normalize(filtered))]:
            K,Q,v,cov=independent_curves(x,lags)
            error=float(abs(Q-data[transform+'_normalized']).max());maximum_curve_error=max(maximum_curve_error,error)
            assert error<1e-9,(row['label'],transform,error)
            assert np.allclose(K,data[transform+'_cumulant'],rtol=1e-7,atol=1e-20)
            assert np.allclose(v,data[transform+'_variance'],rtol=1e-9,atol=1e-22)
            assert np.allclose(cov,data[transform+'_normalized_covariance'],atol=1e-9)
            oracle=direct(x,direct_lags)
            error=float(abs(oracle-Q[:,direct_indices]).max());maximum_direct_error=max(maximum_direct_error,error)
            assert error<1e-9,(row['label'],transform,error)
            expected=[old[transform]['normalized'][b][c] for b,c in PAIRS]
            assert np.allclose(Q[:,zero],expected,atol=1e-9)
            mask=(abs(lags)>=384)&(abs(lags)<=960)
            late=[total(q[mask])/int(mask.sum()) for q in Q]
            assert np.allclose(late,row['summary'][transform]['late8_to20ms_mean'],atol=1e-10)
            for lag,values in row['summary'][transform]['selected'].items():
                assert np.allclose(Q[:,int(np.flatnonzero(lags==int(lag))[0])],values,atol=1e-9)
            if row.get('main') and transform=='raw':main_K=K
            r['curves']+=10
        r['observations']+=1
        if r['observations']%8==0:print(dict(stage='independent_lag_curves',done=r['observations'],total=33),flush=True)
    with np.load(a.input/'expectation.npz') as archive:expectation={key:archive[key] for key in archive.files}
    h=architecture['responses'];kappa=architecture['kappa'];v=architecture['variance']
    assert np.array_equal(expectation['h'],h) and np.array_equal(expectation['kappa'],kappa)
    theoretical=[]
    for b,c in PAIRS:
        row=np.zeros(81)
        for i in range(6):
            values=fftconvolve(h[b,i,::-1]**2,h[c,i]**2,mode='full')
            row+=kappa[i]*values[len(h[b,i])-1+lags]
        theoretical.append(row)
    theoretical=np.array(theoretical)
    assert np.allclose(theoretical,expectation['independent_cumulant'],rtol=1e-7,atol=1e-22)
    normalized=np.array([(theoretical[j]+main_K[j])/v[b]/v[c] for j,(b,c) in enumerate(PAIRS)])
    assert np.allclose(normalized,expectation['normalized'],atol=1e-9)
    for row in observed['response_support']:
        power=h[row['band'],row['input']]**2;energy=total(power)
        q=[int(np.searchsorted(np.cumsum(power),p*energy)) for p in [.05,.95]]
        assert q==row['q05_q95_frames']
        assert np.isclose(energy,row['energy'],rtol=1e-12)
        centroid=total(np.arange(len(power))*power)/energy
        assert abs(centroid-row['centroid_frames'])<1e-8
    assert r['observations']==33 and r['curves']==660
    r.update(result='all33_lag_observations_660curves_and_response_support_verified',
        known_cases_all81_direct_lags=2,source_direct_lags=direct_lags.tolist(),
        plan_direct_count_typo_preserved='Plan text13; explicit list11. All11listed points directly verified; every81point curve independently convolved.',
        maximum_normalized_curve_error=maximum_curve_error,maximum_direct_error=maximum_direct_error,
        maximum_filter_error=maximum_filter_error,input_report_sha256=sha(a.input/'report.json'),
        no_source_identity_or_sound_promotion=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
