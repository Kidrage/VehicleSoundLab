"""Full approved-media LF survey; mixed observations, not source separation."""
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from runtime_review import ROOT, sha
from reference_segments import catalog, checked_source, read_segment

OUT = ROOT / 'references/analysis/low_rumble_v2'
BANDS = [(20,40),(40,80),(80,150),(150,250),(250,400),(400,1000)]
RATE = 2000


def db(value):
    return float(10*np.log10(max(float(value),1e-30)))


def power(x):
    f,p = signal.welch(x,RATE,nperseg=min(4096,len(x)),axis=0)
    return f,p


def summarize(x):
    f,p = power(x)
    ps = p.mean(axis=1); df = f[1]-f[0]
    mask = (f>=25)&(f<=280)
    peaks,_ = signal.find_peaks(ps)
    peaks = [int(i) for i in peaks if mask[i]]
    peaks = sorted(peaks,key=lambda i:ps[i],reverse=True)[:8]
    total = ps[mask].sum()*df
    narrow = np.zeros(len(f),dtype=bool)
    for i in peaks[:3]:narrow |= abs(f-f[i])<2
    return dict(bands_dbfs={f'{a}-{b}':db(ps[(f>=a)&(f<b)].sum()*df) for a,b in BANDS},
                low25_280_dbfs=db(total),
                strongest_lf_peaks_hz=[round(float(f[i]),3) for i in peaks],
                top3_4hz_band_fraction=float(ps[mask&narrow].sum()/max(ps[mask].sum(),1e-30)),
                spectral_flatness25_280=float(np.exp(np.mean(np.log(ps[mask]+1e-30)))/(np.mean(ps[mask])+1e-30)))


def low_reference(x,rate):
    # The reference is an explicitly filtered mixture, never labelled a stem.
    sos=signal.butter(4,[25,280],btype='bandpass',fs=rate,output='sos')
    y=signal.sosfiltfilt(sos,x,axis=0)*.5
    n=min(240,len(y)//2);y[:n]*=np.linspace(0,1,n)[:,None];y[-n:]*=np.linspace(1,0,n)[:,None]
    return y


def run():
    OUT.mkdir(exist_ok=False)
    (OUT/'references').mkdir()
    source_results={}; segment_results={}
    for identity in ['A','B','D','E']:
        source=checked_source(identity)
        x,rate=sf.read(ROOT/source['master'],always_2d=True,dtype='float64')
        assert np.isfinite(x).all()
        ratio=RATE/float(rate)
        from fractions import Fraction
        fraction=Fraction(ratio).limit_denominator(10000)
        low=signal.resample_poly(x,fraction.numerator,fraction.denominator,axis=0)
        np.savez_compressed(OUT/f'{identity}_downsampled.npz',audio=low,rate=RATE)
        rows=[]
        # Include the final incomplete interval; no selection is used to claim
        # that the whole source was reviewed.
        for start in range(0,len(low),RATE):
            stop=min(len(low),start+RATE*3)
            if stop-start<64:continue
            rows.append(dict(seconds=[start/RATE,stop/RATE],**summarize(low[start:stop])))
        source_results[identity]=dict(raw=source['raw'],raw_sha256=source['raw_sha256'],
            master=source['master'],master_sha256=source['master_sha256'],sample_rate=rate,
            frames=len(x),channels=2,duration_seconds=len(x)/rate,
            scanned_seconds=len(x)/rate,full_source_statistics=summarize(low),windows=rows,
            processing='Full L/R joint antialiased resample to2kHz for LF analysis; no gain/denoise/normalization.',
            limitation='Complete numeric LF scan, not a claim of complete subjective listening or separated engine/wind/road sources.')
        print(json.dumps(dict(source=identity,seconds=len(x)/rate,statistics=source_results[identity]['full_source_statistics'])),flush=True)
    for name,segment in catalog()['segments'].items():
        x,rate,provenance=read_segment(name,segment['allowed_uses'][0])
        from fractions import Fraction
        ratio=Fraction(RATE,rate)
        low=signal.resample_poly(x,ratio.numerator,ratio.denominator,axis=0)
        f,p=power(low)
        z=low_reference(x,rate)
        path=OUT/'references'/f'{name}_low25_280.wav'
        sf.write(path,z,rate,subtype='PCM_24')
        np.savez(OUT/'references'/f'{name}_spectrum.npz',frequency=f,psd=p)
        segment_results[name]=dict(provenance=provenance,perspective=segment['perspective'],
            statistics=summarize(low),lf_reference=str(path.relative_to(ROOT)),lf_reference_sha256=sha(path),
            filter='Fourth-order Butterworth25..280Hz, forward/backward; fixed0.5 gain and5ms endpoints.',
            separation='Filtered recording mixture; no identified engine stem or transfer.')
        print(json.dumps(dict(segment=name,statistics=segment_results[name]['statistics'])),flush=True)
    result=dict(schema='vsl.low-rumble-survey/2',sources=source_results,segments=segment_results,
                catalog_sha256=sha(ROOT/'references/segments_v1.json'),
                coverage='Every decoded sample of all four approved local sources was included in the numeric LF scan.',
                unapproved_C='Not downloaded/used',
                media_and_state_limits='B has no local video. Existing A/D/E visual evidence retained; no new RPM/pedal/load/source-separation claim.')
    (OUT/'survey.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
