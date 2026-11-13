"""Independent compensated moments and FFT transfer verification for every case."""
import argparse, itertools, math, shutil, sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']:
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load, save, sha


def total(values):
    return math.fsum(np.asarray(values).tolist())


def scalar(x, weights=None):
    w = np.ones(len(x))/len(x) if weights is None else weights
    mean = [total(w*x[:, b]) for b in range(4)]
    y = x - mean
    covariance = np.empty((4,4))
    fourth = np.empty((4,4))
    for b in range(4):
        for c in range(4):
            covariance[b,c] = total(w*y[:,b]*y[:,c])
            fourth[b,c] = total(w*(y[:,b]**2)*(y[:,c]**2))
    v = covariance.diagonal()
    K = np.array([[fourth[b,c]-v[b]*v[c]-2*covariance[b,c]**2 for c in range(4)] for b in range(4)])
    return dict(mean=mean, variance=v, covariance=covariance, cumulant=K,
        normalized=np.array([[K[b,c]/v[b]/v[c] for c in range(4)] for b in range(4)]))


def normalized(x):
    out = x.copy()
    for first in range(0,len(x),1920):
        for b in range(4):
            part = x[first:first+1920,b]
            out[first:first+1920,b] /= math.sqrt(total(part*part)/1920)
    return out


def transfer(sos, size):
    z = np.cos(-2*np.pi*np.arange(size//2+1)/size)+1j*np.sin(-2*np.pi*np.arange(size//2+1)/size)
    out = np.ones(len(z), complex)
    for row in sos:
        out *= (row[0]+row[1]*z+row[2]*z*z)/(row[3]+row[4]*z+row[5]*z*z)
    return out


def fft_filter(x, sos):
    size = 1 << int(math.ceil(math.log2(len(x)+131072)))
    z = np.fft.rfft(x, n=size)
    return np.column_stack([np.fft.irfft(z*transfer(s,size), n=size)[:len(x)] for s in sos])


a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', observations=0, matrices=0)
try:
    observed = load(a.input/'report.json')
    assert observed['result'] == 'all_joint_idle_observations_complete_NO_sound_promotion'
    for name,digest in observed['sources'].items():
        assert sha(repo/name) == digest == sha(a.input/'exact_sources'/name), name
    parent_tables = {}
    for name,digest in observed['parent_manifests'].items():
        path = a.workspace/'baselines'/name/'manifest.json'
        assert sha(path) == digest
        parent_tables[name] = {v['path']:v['sha256'] for v in load(path)['files']}
    for path,digest in observed['inputs'].items():
        path = Path(path)
        relative = path.relative_to(a.workspace/'baselines')
        assert sha(path) == digest == parent_tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
    maximum_moment_error = 0.
    for name in ['independent_marks','shared_marks','independent_FIR']:
        known = np.load(a.input/'known'/(name+'.npz'))
        x,w = known['x'],known['weights']
        if name == 'independent_FIR':
            h = known['responses']
            for i,row in enumerate(x):
                binary = [1. if i&(1<<(7-k)) else -1. for k in range(8)]
                for b in range(4):
                    assert abs(row[b]-math.fsum(binary[2*j+k]*h[b,j,k] for j in range(4) for k in range(2))) < 1e-14
            theory = np.array([[-2*math.fsum((h[b,j,k]*h[c,j,k])**2 for j in range(4) for k in range(2)) for c in range(4)] for b in range(4)])
            assert np.allclose(theory,known['expected_cumulant'],atol=1e-13)
        else:
            shared = name == 'shared_marks'
            count = 2 if shared else 16
            for mark_index in range(count):
                marks = [int(bool(mark_index&(1<<(0 if shared else 3-b)))) for b in range(4)]
                for index in range(81):
                    digits = [(index//(3**(3-b)))%3 for b in range(4)]
                    expected = [(d-1)*math.sqrt(3.)*marks[b]*2 for b,d in enumerate(digits)]
                    position = mark_index*81+index
                    probability = math.prod((.25 if bit else .75) for bit in (marks[:1] if shared else marks))
                    probability *= math.prod((2/3 if d==1 else 1/6) for d in digits)
                    assert np.allclose(x[position],expected,atol=1e-14) and abs(w[position]-probability)<1e-14
            theory = np.full((4,4), 3. if shared else 0.)
            np.fill_diagonal(theory,9.)
            assert np.allclose(scalar(x,w)['normalized'],theory,atol=1e-12)
        actual = scalar(x,w)
        for key,value in actual.items():
            error = float(abs(np.array(value)-observed['known'][name]['observation'][key]).max())
            maximum_moment_error = max(maximum_moment_error,error)
            assert np.allclose(value,observed['known'][name]['observation'][key],atol=1e-11,rtol=1e-10)
    print(dict(stage='exact_known_ensembles_verified'),flush=True)
    architecture = np.load(a.input/'architecture.npz')
    sos = architecture['sos']
    cache_key,cache = None,None
    actual_rows = {}
    maximum_filter_error = maximum_phase_error = 0.
    original = {}
    parent = a.workspace/'baselines/idle_excitation_moments_v1/evidence/observe1'
    for portion in ['training','check']:
        data = np.load(parent/(portion+'.npz'))
        original[portion] = data['audio']
        assert np.array_equal(sos,data['sos'])
    for index,row in enumerate(observed['observations']):
        kind = row['kind']
        if kind == 'source':
            data = np.load(row['parent_npz'])
            filtered = fft_filter(data['audio'][:,0],sos)[4800:-4800]
            error = float(abs(filtered-data['filtered']).max())
            maximum_filter_error = max(maximum_filter_error,error)
            assert error<1e-11
        elif kind == 'phase':
            data = np.load(a.input/row['control'])
            z = np.fft.rfft(original[row['portion']],axis=0)
            shifted = np.fft.rfft(data['audio'],axis=0)
            phase = data['phase']
            expected = z*(np.cos(phase)+1j*np.sin(phase))[:,None]
            error = float(abs(shifted-expected).max()/max(1.,abs(z).max()))
            maximum_phase_error = max(maximum_phase_error,error)
            assert error<1e-12
            assert abs(abs(z)-abs(shifted)).max()<1e-10
            assert abs(z[:,0]*z[:,1].conj()-shifted[:,0]*shifted[:,1].conj()).max()/max(1.,abs(z[:,0]*z[:,1].conj()).max())<1e-12
            filtered = fft_filter(data['audio'][:,0],sos)[4800:-4800]
        elif kind == 'main':
            filtered = fft_filter(architecture['main'][:,0],sos)[4800:-4800]
        else:
            if cache_key != row['path']:
                audio,rate = sf.read(row['path'],always_2d=True)
                assert rate==48000 and len(audio)==576000
                cache = fft_filter(audio[:,0],sos)
                cache_key = row['path']
            first,last = row['block']*144000+4800,(row['block']+1)*144000-4800
            filtered = cache[first:last]
        assert len(filtered)==row['frames']==134400
        actual_rows[row['label']] = {}
        for transform,x in [('raw',filtered),('local40ms',normalized(filtered))]:
            actual = scalar(x)
            actual_rows[row['label']][transform] = actual
            for key,value in actual.items():
                error = float(abs(np.array(value)-row[transform][key]).max())
                maximum_moment_error = max(maximum_moment_error,error)
                assert np.allclose(value,row[transform][key],atol=1e-10,rtol=1e-8),(row['label'],transform,key,error)
            r['matrices']+=1
        r['observations']+=1
        if index%12==0:
            print(dict(stage='independent_observations',done=r['observations'],total=57),flush=True)
    h = architecture['responses']
    assert np.array_equal(h,np.load(parent/'effective_impulses.npz')['impulses'])
    model = load(parent/'model.json')
    kappa = np.zeros(6)
    kappa[model['kernel_indices']] = model['excess_input']
    assert np.array_equal(kappa,architecture['kappa'])
    budget = load(parent/'moment_budget.json')
    v = np.array(budget['model_variance'])
    assert np.array_equal(v,architecture['variance'])
    K = np.array([[math.fsum(kappa[i]*total((h[b,i]*h[c,i])**2) for i in range(6)) for c in range(4)] for b in range(4)])
    assert np.allclose(K,architecture['independent_cumulant'],rtol=1e-10,atol=1e-25)
    main_K = actual_rows['main']['raw']['cumulant']
    for amount in [0,.5,1]:
        value = (main_K+amount**2*K)/np.outer(v,v)
        assert np.allclose(value,observed['theoretical_raw'][str(amount)],atol=1e-10,rtol=1e-8)
    for pair in observed['pairs']:
        b,c=pair['bands']
        assert pair['independent_full']==observed['theoretical_raw']['1'][b][c]
        for transform in ['raw','local40ms']:
            for value in pair[transform]:
                source = actual_rows[value['portion']][transform]['normalized'][b,c]
                controls = [actual_rows[vv['label']][transform]['normalized'][b,c] for vv in observed['observations'] if vv['kind']=='phase' and vv['portion']==value['portion']]
                assert abs(source-value['source'])<1e-10 and np.allclose(controls,value['phase_controls'],atol=1e-10)
                assert value['exceeds_every_phase_control']==bool(source>max(controls))
        expected = all(vv['exceeds_every_phase_control'] and vv['source']>pair['independent_full'] for vv in pair['raw'])
        assert pair['both_raw_above_controls_and_full_expectation']==expected
    assert r['observations']==57 and r['matrices']==114
    r.update(result='all57_joint_observations_and_independent_architecture_verified',
        exact_known_ensembles=3,maximum_moment_error=maximum_moment_error,
        maximum_filter_error=maximum_filter_error,maximum_phase_relative_error=maximum_phase_error,
        all6_pair_summaries_verified=True,input_report_sha256=sha(a.input/'report.json'),
        no_source_identity_or_sound_promotion=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
print(r,flush=True)
