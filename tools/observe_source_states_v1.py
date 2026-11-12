"""Observe fixed, approved source contexts before choosing stationary DNA fits."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--plan', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from shift_evidence_v1.spectrum import BANDS, observe, region_stats
from state_colour_v2.clock import peaks

args.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(Path(__file__), args.out / 'executed_observe.py')
report = dict(schema='vsl.source-state-observation/1', result='running', sources={}, segments={})
try:
    plan_path = args.plan.resolve()
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    assert plan['schema'] == 'vsl.source-state-observation-plan/1'
    assert plan['observation'] == dict(windows_ms=[80, 320], hop_samples=240, fft_size=16384)
    catalog_path = args.workspace / 'references/segments_v1.json'
    assert catalog_path.read_bytes() == (repo / 'references/segments_v1.json').read_bytes()
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    entry = catalog['sources'][plan['source']]
    approval = entry['approval'].lower()
    assert plan['source'] in ('A', 'B', 'D', 'E')
    assert 'approved by user' in approval or 'explicit user approval' in approval
    for kind in ('raw', 'master'):
        assert sha(args.workspace / entry[kind]) == entry[kind + '_sha256']
    report['input'] = dict(source=plan['source'], catalog_sha256=sha(catalog_path),
        raw_sha256=entry['raw_sha256'], master_sha256=entry['master_sha256'],
        master=entry['master'], approval=entry['approval'])
    for source in (Path(__file__), plan_path, repo / 'tools/drive_evidence_v1/sources.py',
                   repo / 'tools/shift_evidence_v1/spectrum.py', repo / 'tools/state_colour_v2/clock.py'):
        relative = source.relative_to(repo)
        target = args.out / 'exact_sources' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)
    for case in plan['segments']:
        directory = args.out / case['id']
        directory.mkdir()
        lo, hi = case['seconds']
        first, stop = [round(value * 48000) for value in (lo, hi)]
        with sf.SoundFile(args.workspace / entry['master']) as stream:
            assert (stream.samplerate, stream.channels, stream.subtype) == (48000, 2, 'FLOAT')
            stream.seek(first)
            audio = stream.read(stop - first, dtype='float64', always_2d=True)
        assert len(audio) == stop - first and np.isfinite(audio).all()
        sf.write(directory / 'unchanged_reference.wav', audio, 48000, subtype='FLOAT')
        item = dict(case=case, first_sample=first, stop_sample=stop,
            unchanged_reference_sha256=sha(directory / 'unchanged_reference.wav'),
            raw_rms_dbfs_LR=(10 * np.log10(np.maximum(np.mean(audio**2, axis=0), 1e-30))).tolist(),
            peak_LR=abs(audio).max(axis=0).tolist(), observations={})
        for window_ms in plan['observation']['windows_ms']:
            measured = observe(audio, lo, window_ms, hop=plan['observation']['hop_samples'])
            target = directory / f'observations_{window_ms}ms.npz'
            np.savez_compressed(target, **measured)
            sampled = []
            for seconds in np.arange(lo + .25, hi - .15, .5):
                index = int(np.argmin(abs(measured['seconds'] - seconds)))
                hz, prominence = peaks(measured['hz'], measured['power_low'][:, index])
                order = np.argsort(prominence)[-12:][::-1]
                sampled.append(dict(seconds=float(measured['seconds'][index]),
                    hz=hz[order].tolist(), prominence_db=prominence[order].tolist()))
            figure, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True, constrained_layout=True)
            hz = measured['hz']
            keep = hz >= 25
            db = 10 * np.log10(np.maximum(measured['power_low'][keep], 1e-30))
            axes[0].pcolormesh(measured['seconds'], hz[keep], db,
                vmin=db.max()-55, vmax=db.max(), cmap='magma', shading='auto', rasterized=True)
            axes[0].set(ylabel='Observed Hz',
                title=f"{plan['source']} {case['id']} | {window_ms}ms Hann | raw stereo mean PSD; no RPM/load labels")
            for index, (low, high) in enumerate(BANDS):
                power = measured['power_LR'][:, index]
                axes[1].plot(measured['seconds'], 10*np.log10(np.maximum(power.mean(axis=0), 1e-30)),
                    label=f'{low}..{high} Hz')
                axes[2].plot(measured['seconds'], 10*np.log10(np.maximum(power[0], 1e-30) /
                    np.maximum(power[1], 1e-30)))
            axes[1].set(ylabel='Band power dBFS')
            axes[1].legend(ncol=3, fontsize=8)
            axes[2].set(ylabel='L/R level dB', xlabel='Original decoded source seconds; no calibrated A/V latency')
            plot = directory / f'observations_{window_ms}ms.png'
            figure.savefig(plot, dpi=130)
            plt.close(figure)
            regions = [region_stats(measured, start+window_ms/2000, end-window_ms/2000)
                       for start, end in case['regions']]
            item['observations'][str(window_ms)] = dict(frames=len(measured['seconds']),
                sampled_peaks=sampled, fixed_regions=regions,
                observations_sha256=sha(target), plot_sha256=sha(plot))
        (directory / 'report.json').write_text(json.dumps(item, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        report['segments'][case['id']] = dict(report_sha256=sha(directory / 'report.json'), **item)
        print(json.dumps(dict(segment=case['id'], frames=len(audio),
            raw_rms_dbfs_LR=item['raw_rms_dbfs_LR']), ensure_ascii=False), flush=True)
    report.update(result='observed_not_fitted', plan=plan, limits=plan['limits'])
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
