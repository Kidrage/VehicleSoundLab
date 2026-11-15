"""Read-only known-coordinate frequency accounting, with bin and Nyquist controls."""
import argparse, ast, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    repo=Path(__file__).resolve().parents[1]
    run=repo/'tools/run_observer_stable_full_v1.py'
    band=repo/'tools/observer_frequency_v1/metric.py'
    source=load(a.study/'report.json')
    assert source['sources']['tools/run_observer_stable_full_v1.py']==sha(run)
    assert source['sources']['tools/observer_frequency_v1/metric.py']==sha(band)
    roots=[ast.literal_eval(n.args[1]) for n in ast.walk(ast.parse(run.read_text()))
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='SupportedMetric']
    assert roots==[64.]
    edges=[ast.literal_eval(n.value) for n in ast.walk(ast.parse(band.read_text()))
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EDGES' for t in n.targets)]
    assert len(edges)==1 and edges[0]==(0.,3000.,6000.,8000.,10000.,14000.)
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    # No live basis, solver vectors or material waveform is opened.
    cycle,root,fft=1024,roots[0],4096
    rate=cycle*root
    frequencies=np.arange(fft//2+1)*rate/fft
    membership=np.empty(len(frequencies),dtype=int)
    for j,f in enumerate(frequencies):
        membership[j]=sum(f>=cut for cut in edges[0][1:])
    assert np.array_equal(membership,np.searchsorted(edges[0][1:],frequencies,side='right'))
    counts=[int(np.sum(membership==j)) for j in range(6)]
    assert sum(counts)==2049 and membership[-1]==5 and frequencies[-1]==32768
    controls=[]
    n=np.arange(fft)
    for k in (187,188,1600,2048):
        wave=np.cos(2*np.pi*(k/fft)*n)
        spectrum=np.fft.rfft(wave)
        weights=np.full(len(spectrum),2.);weights[[0,-1]]=1
        recovered=float(np.sum(weights*abs(spectrum)**2)/fft)
        exact=float(wave@wave)
        assert abs(recovered-exact)/exact<2e-14
        found=int(np.argmax(abs(spectrum)))
        assert found==k
        controls.append(dict(bin=k,hz=frequencies[k],band=int(membership[k]),
            selected_energy_fraction=float(weights[k]*abs(spectrum[k])**2/(fft*exact)),
            Parseval_relative_error=abs(recovered-exact)/exact))
    assert controls[0]['band']==0 and controls[1]['band']==1
    assert controls[2]['hz']==25600 and controls[2]['band']==5
    assert controls[-1]['hz']==32768 and controls[-1]['band']==5
    result=dict(result='independent_observer_stable_frequency_units_passed',analysis_rate_Hz=rate,
        analysis_samples_per_acoustic_cycle=cycle,known_root_Hz=root,rFFT_bins=len(frequencies),
        final_band_Hz=[14000.,32768.],final_band_includes_Nyquist=True,bins_per_band=counts,controls=controls,
        original_21600Hz_is_not_a_cut_in_this_known_metric=True,live_basis_or_source_audio_read=False,
        no_native48k_or_measured_RPM_or_material_frequency_calibration_claim=True,
        producer_source_sha256=sha(run),band_edges_source_sha256=sha(band),auditor_sha256=sha(__file__))
    save(a.out/'report.json',result)
    print(result,flush=True)


if __name__=='__main__':
    main()
