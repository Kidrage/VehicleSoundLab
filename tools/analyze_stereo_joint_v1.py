"""Test whether a lossless stereo basis correction can robustly repair the low-mid debt."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha,read
from residual_osc_v1.spectrum import matrices
from stereo_field_v1.budget import matrix,scalar_minimum
plan_path=repo/'research/stereo_joint_v1_plan.json';plan=json.loads(plan_path.read_text())
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',plan=plan,sources={},inputs={},controls=[],cases=[])
def unitary(target,base):
    _,t=np.linalg.eigh(target);_,b=np.linalg.eigh(base)
    phase=np.exp(1j*np.angle(np.diag(t.conj().T@b)))
    return (t*phase)@b.conj().T
def encode(m):return np.stack((m.real,m.imag),axis=-1).tolist()
def observe(t,b):
    scale=np.trace(t).real;values=np.linalg.eigvalsh(t-b)
    assert abs(values[0]-scalar_minimum(t-b))<plan['checks']['scalar_eigenvalue_absolute_tolerance']
    return dict(target=encode(t),base=encode(b),debt_eigenvalues=values.tolist(),
        target_eigenvalues=np.linalg.eigvalsh(t).tolist(),base_eigenvalues=np.linalg.eigvalsh(b).tolist(),
        additive_feasible=bool(values[0]>=-scale*plan['checks']['matrix_relative_tolerance']),
        normalized_shape_error=float(np.linalg.norm(t/scale-b/np.trace(b).real,'fro')))
try:
    for path in (Path(__file__),plan_path,repo/'tools/residual_osc_v1/spectrum.py',repo/'tools/stereo_field_v1/budget.py',repo/'tools/drive_evidence_v1/sources.py'):
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    # Known spectral bases: correct rotation, impossible weak-direction excess,
    # and channel permutation covariance. No data-dependent tolerance changes.
    z=np.array([[np.cos(.4),np.sin(.4)*np.exp(.7j)],[-np.sin(.4)*np.exp(-.7j),np.cos(.4)]])
    target=np.diag([1.,3.]);base=z@np.diag([.2,2.])@z.conj().T;u=unitary(target,base)
    err=float(abs(u@base@u.conj().T-np.diag([.2,2.])).max())
    ident=float(abs(u@u.conj().T-np.eye(2)).max());assert max(err,ident)<1e-14
    assert observe(target,u@base@u.conj().T)['additive_feasible']
    impossible=np.diag([1.1,2.]);bound=np.linalg.eigvalsh(target)-np.linalg.eigvalsh(impossible)
    assert min(bound)<0 and not observe(target,impossible)['additive_feasible']
    swap=np.array([[0.,1.],[1.,0.]]);swapped=unitary(swap@target@swap,swap@base@swap)
    cov_error=float(abs(swapped@(swap@base@swap)@swapped.conj().T-swap@(u@base@u.conj().T)@swap).max())
    assert cov_error<1e-14;r['controls']=dict(known_basis_error=err,unitarity_error=ident,channel_swap_error=cov_error,impossible_weak_direction_rejected=True)
    summary=json.loads((repo/'research/stereo_resonance_v1_summary.json').read_text(encoding='utf-8'))
    fit=a.workspace/'references/analysis/stereo_resonance_v1/fit2'
    verification=a.workspace/'references/analysis/stereo_resonance_v1/verify1'
    vr=json.loads((verification/'report.json').read_text(encoding='utf-8'))
    for path in (fit/'report.json',verification/'report.json'):
        key=path.relative_to(a.workspace).as_posix();assert sha(path)==summary['evidence_sha256'][key]
    raw=fit/'reference.wav';main=verification/'DNA_50s.wav'
    assert sha(main)==vr['evidence_sha256']['DNA_50s.wav']
    x,rate=sf.read(raw,always_2d=True);y,rate2=sf.read(main,always_2d=True);assert rate==rate2==48000
    original,provenance=read(a.workspace,'A_start_context','audio_onset_observation')
    assert np.array_equal(x,original[round((38.48-33)*48000):round((39.51-33)*48000)])
    r['source_provenance']=provenance
    y=y[96000:];band=[plan['band_hz']]
    t=matrix(matrices(x,band)[0]);b=matrix(matrices(y,band)[0]);nominal=np.trace(t).real
    half=[matrix(matrices(v,band)[0]) for v in np.array_split(x,2)]
    normalized=[m*nominal/np.trace(m).real for m in half]
    uf=unitary(t,b);full=observe(t,uf@b@uf.conj().T)
    records=[]
    for i,reference in enumerate(normalized):
        uh=unitary(reference,b);candidate=uh@b@uh.conj().T;test=normalized[1-i]
        old=observe(test,b);new=observe(test,candidate)
        gain=1-new['normalized_shape_error']**2/old['normalized_shape_error']**2
        # Sorted eigenvalues are a necessary condition even for the best
        # possible lossless rotation, independent of a fitted angle or phase.
        margin=np.linalg.eigvalsh(reference)-np.linalg.eigvalsh(b)
        necessary=bool(min(margin)>=-nominal*plan['checks']['matrix_relative_tolerance'])
        records.append(dict(train_half=i,normalized_target=encode(reference),trace_scale=float(nominal/np.trace(half[i]).real),
            raw_half=observe(half[i],b),optimal_same_half=observe(reference,candidate),
            necessary_lossless_eigenvalue_margins=margin.tolist(),necessary_feasible=necessary,
            heldout_before=old,heldout_after=new,heldout_shape_improvement=float(gain),
            heldout_improvement_pass=bool(gain>=plan['checks']['heldout_shape_improvement_minimum']),
            unitary=encode(uh)))
    qualified=full['additive_feasible'] and all(v['necessary_feasible'] and v['optimal_same_half']['additive_feasible'] and v['heldout_after']['additive_feasible'] and v['heldout_improvement_pass'] for v in records)
    r.update(result='lossless_stereo_correction_qualified' if qualified else 'lossless_stereo_correction_not_qualified',
        unmodified_full=observe(t,b),optimal_full=full,halves=records,qualified=qualified,
        parameter_or_runtime_changed=False,audio_exported=False,
        conclusion='A lossless stereo basis alone is insufficient across the observed source halves; no automatic DNA attenuation.' if not qualified else 'Diagnostic only; actual source rendering and listening remain unverified.')
    for path in (raw,main,fit/'report.json',verification/'report.json',repo/'research/stereo_resonance_v1_summary.json'):
        r['inputs'][str(path)]=sha(path)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],qualified=r.get('qualified'),halves=[dict(necessary=v['necessary_feasible'],heldout_gain=v['heldout_shape_improvement']) for v in r.get('halves',[])])))
