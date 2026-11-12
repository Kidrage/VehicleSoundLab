"""Observe approved B in unchanged stereo; separate source selection from fitting."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--plan', type=Path)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read, sha
from shift_evidence_v1.spectrum import observe, region_stats, BANDS
from state_colour_v2.clock import peaks

a.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.cabin-low-observation/1', result='running', segments={}, sources={})
try:
    plan_path = a.plan.resolve() if a.plan else repo/'research/cabin_low_v1_observation_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    assert plan['source'] == 'B'
    assert plan['observation'] == dict(window_ms=80, hop_samples=240, fft_size=16384)
    for file in [Path(__file__), plan_path, repo/'tools/drive_evidence_v1/sources.py',
                 repo/'tools/shift_evidence_v1/spectrum.py', repo/'tools/state_colour_v2/clock.py']:
        name = file.relative_to(repo)
        target = a.out/'exact_sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
        r['sources'][name.as_posix()] = sha(file)
    catalog_path = a.workspace/'references/segments_v1.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    entry = catalog['sources']['B']
    assert 'Approved by user' in entry['approval']
    for kind in ('raw', 'master'):
        assert sha(a.workspace/entry[kind]) == entry[kind+'_sha256']
    r['input'] = dict(catalog_sha256=sha(catalog_path),
        raw_sha256=entry['raw_sha256'], master_sha256=entry['master_sha256'],
        master=entry['master'], approval=entry['approval'])
    for case in plan['segments']:
        out = a.out/case['id']; out.mkdir()
        if 'catalog_id' in case:
            audio, provenance = read(a.workspace, case['catalog_id'], case['use'])
            lo, hi = provenance['seconds']
        else:
            lo, hi = case['seconds']
            with sf.SoundFile(a.workspace/entry['master']) as stream:
                assert stream.samplerate == 48000 and stream.channels == 2 and stream.subtype == 'FLOAT'
                stream.seek(round(lo*48000))
                audio = stream.read(round((hi-lo)*48000), dtype='float64', always_2d=True)
            provenance = dict(source='B', seconds=[lo, hi],
                basis=case['basis'], master_sha256=entry['master_sha256'],
                perspective=case.get('perspective','B source; perspective must be checked separately against context video'),
                processing='Unchanged decoded stereo FLOAT; no filtering, level handling or downmix')
        observed = observe(audio, lo, 80, hop=240)
        np.savez_compressed(out/'observations.npz', **observed)
        top = []
        for seconds in np.arange(lo+.25, hi, .5):
            i = int(np.argmin(abs(observed['seconds']-seconds)))
            f, prominence = peaks(observed['hz'], observed['power_low'][:, i])
            order = np.argsort(prominence)[-8:][::-1]
            top.append(dict(seconds=float(observed['seconds'][i]),
                hz=f[order].tolist(), prominence_db=prominence[order].tolist()))
        fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True, constrained_layout=True)
        hz = observed['hz']; keep = hz >= 35
        db = 10*np.log10(np.maximum(observed['power_low'][keep], 1e-30))
        axes[0].pcolormesh(observed['seconds'], hz[keep], db,
            vmin=db.max()-55, vmax=db.max(), cmap='magma', shading='auto', rasterized=True)
        axes[0].set(ylabel='Observed Hz', title=f"B {case['id']} | raw stereo mean PSD selection view; no RPM/load labels")
        for j, (low, high) in enumerate(BANDS):
            axes[1].plot(observed['seconds'], 10*np.log10(np.maximum(observed['power_LR'][:, j].mean(axis=0), 1e-30)), label=f'{low}..{high}Hz')
            axes[2].plot(observed['seconds'], 10*np.log10(np.maximum(observed['power_LR'][0,j],1e-30)/np.maximum(observed['power_LR'][1,j],1e-30)))
        axes[1].set(ylabel='Band power dBFS'); axes[1].legend(ncol=3, fontsize=8)
        axes[2].set(ylabel='L/R level dB', xlabel='Decoded source seconds; no measured A/V or physical source separation')
        fig.savefig(out/'observations.png', dpi=130); plt.close(fig)
        stats = region_stats(observed, lo+.04, hi-.04)
        item = dict(provenance=provenance, frames=len(observed['seconds']),
            raw_rms_dbfs_LR=(10*np.log10(np.mean(audio**2,axis=0))).tolist(),
            peak_LR=abs(audio).max(axis=0).tolist(), region=stats, sampled_peaks=top,
            observation_sha256=sha(out/'observations.npz'), plot_sha256=sha(out/'observations.png'))
        (out/'report.json').write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        r['segments'][case['id']] = dict(report_sha256=sha(out/'report.json'), **item)
        print(json.dumps(dict(segment=case['id'], frames=item['frames'], peaks=top[:2]),ensure_ascii=False),flush=True)
    r.update(result='observed_not_fitted', plan=plan, limits=plan['limits'])
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
