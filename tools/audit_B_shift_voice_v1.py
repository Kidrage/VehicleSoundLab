"""Direct FFT/sample/peak-graph audit of the single declared B attempt."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'fit', 'frames', 'out'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out/'executed_audit.py')
r = dict(result='running', inputs={}, clips=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def reachable(nodes, times, initial, cap):
    reach = [abs(math.log2(v/initial)) <= .10 for v in nodes[0]]
    first_dead = None if any(reach) else 0
    for i in range(1, len(nodes)):
        reach = [any(ok and abs(math.log2(v/u))/(times[i]-times[i-1]) <= cap
                     for u, ok in zip(nodes[i-1], reach)) for v in nodes[i]]
        if first_dead is None and not any(reach):
            first_dead = i
    return dict(connected=any(reach), first_dead_index=first_dead)


try:
    # Analytic Fourier power and graph controls precede this auditor's source read.
    w = .5-.5*np.cos(2*np.pi*np.arange(3840)/3840)
    x = .2*np.cos(2*np.pi*200*np.arange(3840)/48000)
    z = np.fft.rfft(w*x, 16384)
    density = abs(z)**2/(48000*math.fsum(w*w)); density[1:-1] *= 2
    power_error = abs(math.fsum(density)*48000/16384-.2**2/2)
    assert power_error < 1e-14
    assert reachable([[40],[41],[40]], [0,.05,.10], 40, 32)['connected']
    assert not reachable([[40],[80]], [0,.005], 40, 32)['connected']
    assert not reachable([[40],[],[40]], [0,.05,.1], 40, 32)['connected']
    r['known_before_source'] = dict(FFT_power_FS2=power_error, connected_and_overfast_and_missing_graphs=True)
    fit = load(consume(a.fit/'report.json'))
    assert fit['result'] == 'fixed_centers_checked'
    for name, digest in fit['sources'].items():
        assert sha(repo/name) == digest == sha(a.fit/'exact_sources'/name)
    plan = load(consume(repo/'research/B_shift_voice_v1_plan.json'))
    frames = load(consume(a.frames/'report.json'))['sources']['B']['frames']
    for row in frames:
        assert sha(consume(a.frames/'B'/row['file'])) == row['sha256']
    annotations = load(consume(repo/'research/B_shift_voice_v1_annotations.json'))
    for row in annotations['gear_display_brackets_video_seconds']:
        for key in ('last_old', 'first_new'):
            assert min(abs(f['source_seconds']-row[key]) for f in frames) < 1e-6
    catalog = load(consume(a.workspace/'references/segments_v1.json'))
    entry = catalog['sources']['B']
    for key in ('raw','master'):
        assert sha(consume(a.workspace/entry[key])) == entry[key+'_sha256']
    first, stop = [round(t*48000) for t in plan['source_seconds']]
    with sf.SoundFile(a.workspace/entry['master']) as stream:
        stream.seek(first)
        audio = stream.read(stop-first, dtype='float64', always_2d=True)
    with np.load(consume(a.fit/'observed.npz')) as f:
        observed = {k:f[k] for k in f.files}
    times, hz = observed['seconds'], observed['hz']
    assert len(times) == (len(audio)-3840)//240+1
    bands = [(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,16000)]
    all_hz = np.arange(8193)*48000/16384
    nodes, peaks, empty = [], [], []
    maximum_spectrum = maximum_band = maximum_cross = 0.
    for i, start in enumerate(range(0,len(audio)-3840+1,240)):
        assert abs(times[i]-(475+(start+1920)/48000)) < 1e-12
        z = np.fft.rfft(audio[start:start+3840]*w[:,None], 16384, axis=0)
        power = abs(z)**2/(48000*math.fsum(w*w)); power[1:-1] *= 2
        cross = z[:,0]*z[:,1].conj()/(48000*math.fsum(w*w)); cross[1:-1] *= 2
        low = power[:len(hz)].mean(axis=1)
        maximum_spectrum = max(maximum_spectrum,float(abs(low-observed['power_low'][:,i]).max()))
        for b,(lo,hi) in enumerate(bands):
            keep = (all_hz>=lo)&(all_hz<hi)
            values = np.array([math.fsum(power[keep,c])*48000/16384 for c in (0,1)])
            maximum_band = max(maximum_band,float(abs(values-observed['power_LR'][:,b,i]).max()))
            value = sum(cross[keep])*48000/16384
            maximum_cross = max(maximum_cross,float(abs(value-observed['cross_LR'][b,i])))
        db = 10*np.log10(np.maximum(low,1e-30))
        indices, properties = signal.find_peaks(db,prominence=4)
        row = []
        for j,k in enumerate(indices):
            if not 35 <= hz[k] < 1200:
                continue
            before, middle, after = map(float, db[k-1:k+2])
            denominator = before-2*middle+after
            delta = .5*(before-after)/denominator if abs(denominator)>1e-12 else 0.
            frequency = float(hz[k]+max(-.5,min(.5,delta))*(48000/16384))
            row.append(dict(hz=frequency,prominence_db=float(properties['prominences'][j])))
        roots = [v['hz']/5 for v in row if 20 <= v['hz']/5 <= 90]
        nodes.append(roots)
        peaks.append(dict(seconds=float(times[i]),roots_hz=roots,all_observed_peaks=row))
        if not roots:
            empty.append(float(times[i]))
    assert max(maximum_spectrum,maximum_band,maximum_cross) < 1e-12
    k = int(np.argmin(abs(times-plan['anchor_seconds'])))
    candidates = sorted([v for v in peaks[k]['all_observed_peaks'] if 100 <= v['hz'] <= 450],
                        key=lambda v:(-v['prominence_db'],v['hz']))
    assert len(candidates) == len(fit['anchor']['candidates'])
    anchor_error = max(abs(v[key]-expected[key]) for v,expected in
                       zip(candidates,fit['anchor']['candidates']) for key in ('hz','prominence_db'))
    assert anchor_error < 1e-10
    assert abs(candidates[0]['hz']/5-fit['anchor']['root_hz']) < 1e-12
    graph = reachable(nodes,times,fit['anchor']['root_hz'],plan['max_octaves_per_second'])
    assert graph['connected'] == (fit['family']['status']=='connected_observed_family')
    if graph['first_dead_index'] is not None:
        graph['first_dead_seconds'] = float(times[graph['first_dead_index']])
    save(a.out/'observed_peak_graph.json',dict(frames=peaks,empty_reference_frames=empty,reachability=graph))
    r.update(direct_FFT_maximum_FS2_Hz=maximum_spectrum, direct_band_maximum_FS2=maximum_band,
             direct_cross_maximum_FS2=maximum_cross,frames_checked=len(times),
             anchor_maximum_scalar_difference=anchor_error,
             empty_reference_frames=len(empty),reachability=graph)
    assert fit['accepted_count'] == 0 and fit['rejected_count'] == 2
    assert not list(a.fit.rglob('*.model')) and not list(a.fit.rglob('DNA.wav'))
    r['failure_does_not_prove'] = 'Missing engine sound or impossibility of a local voice; one uninterrupted observed family is unsupported by the declared procedure'
    # These are playback excerpts only, not substitute fitting windows.
    for key, lo, hi in [('whole',475,485),('after',478.5,479.5),('later',482.5,483.5)]:
        values = audio[round((lo-475)*48000):round((hi-475)*48000)]*.5
        n = 240
        fade = .5-.5*np.cos(np.pi*np.arange(n)/n)
        values[:n] *= fade[:,None]; values[-n:] *= fade[::-1,None]
        dest = a.out/(key+'.wav'); sf.write(dest,values,48000,subtype='FLOAT')
        saved,rate = sf.read(dest,always_2d=True)
        assert rate == 48000 and np.array_equal(saved,values.astype('float32').astype('float64'))
        r['clips'].append(dict(key=key,file=dest.name,source_seconds=[lo,hi],frames=len(values),sha256=sha(dest)))
    protected = a.workspace/'baselines/catalog_decel_v1'
    for key,count in [('C_files_sha256.json',646),('voice_files_sha256.json',74)]:
        records = load(consume(protected/'inputs'/key))
        assert len(records)==count and all(sha(repo/n)==h for n,h in records.items())
    r.update(protected_C_H_exact=646,protected_voice_parameters_exact=74)
    fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True,layout='constrained')
    db=10*np.log10(np.maximum(observed['power_low'],1e-30))
    axes[0].pcolormesh(times,hz,db,shading='auto',vmin=db.max()-55,vmax=db.max(),cmap='magma',rasterized=True)
    axes[0].axhspan(100,450,facecolor='none',edgecolor='cyan',lw=.7)
    axes[0].set(ylabel='Observed Hz',title='B cabin | one declared observed family failed | no fitted voice')
    axes[1].plot(times,[len(n) for n in nodes],lw=1)
    if empty:
        axes[1].plot(empty,np.zeros(len(empty)),'.',color='red',ms=3,label='No reference peak')
        axes[1].legend()
    axes[1].set(ylabel='Observed reference\npeak count, 100..450Hz')
    for b,(lo,hi) in enumerate(bands):
        axes[2].plot(times,10*np.log10(np.maximum(observed['power_LR'][:,b].mean(axis=0),1e-30)),label=f'{lo}-{hi} Hz')
    axes[2].set(ylabel='Stereo-mean band power dBFS',xlabel='Original MP3/master seconds; not measured engine RPM/load')
    axes[2].legend(ncol=3,fontsize=8)
    for axis in axes:
        for center in (479,483):axis.axvline(center,color='gray',ls=':',lw=1)
    fig.savefig(a.out/'diagnostic.png',dpi=130);plt.close(fig)
    r.update(result='passed',no_new_model_or_C_render=True,hearing=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
print({k:r.get(k) for k in ('result','frames_checked','empty_reference_frames','reachability')})
