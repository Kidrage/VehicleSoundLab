"""Predeclared sparse-harmonic supplement; preserves the adjacent-only study."""
import json
from runtime_review import ROOT,sha
from phase_fingerprint import complex_coefficients
import numpy as np

OUT=ROOT/'references/analysis/phase_spaced_triplets_v1'
SPACINGS=tuple(range(1,17))
FLOOR=.03


def triplets(z,spacing):
    z=np.asarray(z);a=abs(z);d=spacing
    unit=z/np.maximum(a,1e-30)
    value=unit[:-2*d]*unit[d:-d].conj()**2*unit[2*d:]
    minimum=np.minimum(np.minimum(a[:-2*d],a[d:-d]),a[2*d:])
    mask=minimum>=FLOOR*a.max(axis=0)
    return value,minimum**2,mask


def score(ca,cb,w,mask,indices):
    if int(mask.sum())<3:
        return dict(status='unmeasured',triplets=int(mask.sum()),reason='Fewer than three common strong triplets')
    a=ca[mask];b=cb[mask];weight=w[mask]
    err=float(np.sum(weight*abs(b-a)**2)/weight.sum())
    flat=float(np.sum(weight*abs(b-1)**2)/weight.sum())
    return dict(status='measured',triplets=int(mask.sum()),triplet_indices=indices[mask].tolist(),
        future_weighted_phase_chord_error=err,zero_curvature_chord_error=flat,
        learned_over_zero_error_db=float(10*np.log10(max(err,1e-30)/max(flat,1e-30))),
        weighted_phase_drift_degrees=float(np.sum(weight*abs(np.angle(b*a.conj())))/weight.sum()*180/np.pi))


def compare(past,future):
    gap=future['source_window_seconds'][0]-past['source_window_seconds'][1]
    assert gap>=.2
    a=complex_coefficients(past);b=complex_coefficients(future);n=min(len(a),len(b))
    rows=[];all_a=[];all_b=[];all_w=[];all_mask=[];all_indices=[]
    for d in SPACINGS:
        if 2*d>=n:continue
        ca,_,ma=triplets(a[:n],d);cb,wb,mb=triplets(b[:n],d)
        centers=np.arange(d+1,n-d+1)
        indices=np.column_stack([centers-d,centers,centers+d])
        rows.append(dict(spacing=d,channels=[score(ca[:,c],cb[:,c],wb[:,c],(ma&mb)[:,c],indices) for c in range(2)]))
        all_a.append(ca);all_b.append(cb);all_w.append(wb);all_mask.append(ma&mb);all_indices.append(indices)
    ca=np.concatenate(all_a);cb=np.concatenate(all_b);w=np.concatenate(all_w);mask=np.concatenate(all_mask);indices=np.concatenate(all_indices)
    return dict(support_gap_seconds=gap,by_spacing=rows,
        combined_channels=[score(ca[:,c],cb[:,c],w[:,c],mask[:,c],indices) for c in range(2)])


def controls():
    k=np.arange(1,129);z=np.zeros((128,2),complex)
    selected=k%5==0
    z[selected,0]=np.exp(1j*(.13*k[selected]**2+.4*k[selected]))/np.sqrt(k[selected])
    z[selected,1]=.7*np.exp(1j*(.09*k[selected]**2-.3*k[selected]))/np.sqrt(k[selected])
    gauged=z*np.exp(1j*(.41+.73*k[:,None]))
    error=0
    for d in SPACINGS:
        a,_,mask=triplets(z,d);b,_,other=triplets(gauged,d)
        assert np.array_equal(mask,other)
        if mask.any():error=max(error,float(abs(a[mask]-b[mask]).max()))
    assert error<1e-11
    assert not triplets(z,1)[2].any() and triplets(z,5)[2].sum()>3
    return dict(sparse_every_fifth_control=True,adjacent_unmeasured_but_spacing_five_supported=True,
        maximum_affine_phase_gauge_error=error,
        selection='All spacings 1..16, amplitude floor .03 and minimum 3 fixed before reference scoring. No spacing selected for best phase prediction.')


def main():
    if OUT.exists():raise SystemExit('Preserve phase_spaced_triplets_v1.')
    control=controls();source=ROOT/'references/analysis/phase_fingerprint_v1/results.json'
    base=json.loads(source.read_text());runs={}
    for key,row in base['runs'].items():
        if row['past']['status']=='measured' and row['future']['status']=='measured':
            runs[key]=compare(row['past'],row['future'])
    result=dict(schema='vsl.phase-spaced-triplets/1',controls=control,spacings=SPACINGS,
        relative_amplitude_floor=FLOOR,runs=runs,
        inputs={source.relative_to(ROOT).as_posix():sha(source)},
        sources={'tools/analyze_spaced_phase.py':sha(__file__)},
        interpretation='Affine phase-invariant mixed-microphone comparisons, conditional on supplied frequency paths and future amplitude selection/weights. Overlapping triplets are dependent; their counts are not independent samples. No fitted RPM, bank separation, waveform prediction, uncertainty interval or realism score. Constant/linear phase is deliberately discarded. All spacing results retained; combined values are descriptive, not significance tests.')
    OUT.mkdir(parents=True);(OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v['combined_channels'] for k,v in runs.items()},indent=2))


if __name__=='__main__':main()
