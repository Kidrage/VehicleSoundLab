"""Inspect a fixed F3 acoustic residual before compiling any additional layer."""
import argparse
from fractions import Fraction
import os
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[name]='2'
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from cyclic_detail_v1.measure import split,dependence
from residual_osc_v1.spectrum import matrices
from stereo_resonance_v1.model import matrix,pack

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={})
try:
    for name in ('tools/observe_F3_detail_v1.py','tools/cyclic_detail_v1/measure.py',
        'tools/residual_osc_v1/spectrum.py','tools/stereo_resonance_v1/model.py',
        'tools/research_archive_v1.py','research/F3_detail_v1_plan.json'):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    plan=load(repo/'research/F3_detail_v1_plan.json');cyclic=plan['cyclic'];cycle=cyclic['cycle_frames']
    # Fixed analytic decomposition and modulated/stationary-noise controls before source reads.
    theta=2*np.pi*np.arange(14*cycle)/cycle;rng=np.random.default_rng(1907)
    stationary=rng.standard_normal((len(theta),2))*.04
    periodic=np.column_stack([.3*np.cos(5*theta+.2),.2*np.cos(5*theta+.5)])
    coherent,residual,info=split(periodic+stationary,cycle)
    assert abs(coherent+residual-(periodic+stationary)).max()<1e-15
    assert max(abs(v) for v in info['orthogonality'])<1e-15
    known={}
    for name,values in [('stationary',stationary),('modulated',stationary*np.sqrt(1+.8*np.cos(theta))[:,None])]:
        _,leftover,_=split(values,cycle)
        known[name]=dependence(leftover,66.78588355389799,plan['bands_hz'],cyclic)
    assert not any(v['periodic_residual_power_supported'] for v in known['stationary']['bands'])
    assert any(v['periodic_residual_power_supported'] for v in known['modulated']['bands'])
    r['known_before_source']=dict(exact_additive_decomposition=True,controls=known)
    frozen=a.workspace/'baselines/F3_lift_voice_v1';manifest=load(frozen/'manifest.json')
    folder=frozen/'evidence/fit2/F3 Sixth Before Upshift'
    for name in ('normalized.wav','reference.wav','voice.model','DNA_1.wav'):
        path=folder/name;digest=sha(path)
        assert digest==next(v['sha256'] for v in manifest['files'] if v['path']==path.relative_to(frozen).as_posix())
        r['inputs'][str(path)]=digest
    old=load(frozen/'validation.json');root=old['root_hz']
    normalized,rate=sf.read(folder/'normalized.wav',always_2d=True);assert rate==48000
    coherent,residual,decomposition=split(normalized,cycle)
    r['source_decomposition']=decomposition
    r['source_dependence']=dependence(residual,root,plan['bands_hz'],cyclic)
    ratio=Fraction(46.875/root).limit_denominator(10000)
    for name,values in [('coherent',coherent),('residual',residual)]:
        sf.write(a.out/(name+'_canonical.wav'),values,48000,subtype='FLOAT')
        native=signal.resample_poly(values,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))
        sf.write(a.out/(name+'_reference.wav'),native,48000,subtype='FLOAT')
    reference,rate=sf.read(folder/'reference.wav',always_2d=True)
    main,rate=sf.read(folder/'DNA_1.wav',always_2d=True)
    target=np.array([matrix(v) for v in matrices(reference,plan['bands_hz'])])
    current=np.array([matrix(v) for v in matrices(main[24000:],plan['bands_hz'])])
    debt=target-current
    r['bands']=[dict(band_hz=band,debt_eigenvalues=np.linalg.eigvalsh(value).tolist(),
        additive_positive=bool(min(np.linalg.eigvalsh(value))>0)) for band,value in zip(plan['bands_hz'],debt)]
    save(a.out/'matrices.json',dict(target=pack(target).tolist(),DNA=pack(current).tolist(),debt=pack(debt).tolist()))
    r.update(result='fixed_residual_observed',root_hz=root,
        resample_ratio=[ratio.numerator,ratio.denominator],positive_debt_bands=sum(v['additive_positive'] for v in r['bands']),
        physical_source_separation=False,periodic_envelope_qualified=False,human_accepted=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print({key:r.get(key) for key in ('result','positive_debt_bands','bands')})
