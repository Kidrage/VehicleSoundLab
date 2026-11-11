"""Fit separate recording-informed LF spectral beds; no physical source claim."""
import json
import numpy as np
from scipy import ndimage, signal
from runtime_review import ROOT, sha
from reference_segments import read_segment
from .analysis import OUT, RATE

SOURCES=[('A Exterior','A_exterior_blips','exterior_dynamic_observation'),
         ('B Cabin','B_cabin_pull','interior_channel_observation'),
         ('D Dyno','D_dyno_gears_context','audio_transition_observation'),
         ('E Cabin','E_sport_context','cabin_dynamic_observation')]


def run():
    bank=ROOT/'voices/low_rumble_v2';bank.mkdir(exist_ok=False)
    fits=OUT/'fits';fits.mkdir()
    index=[]
    for name,segment,use in SOURCES:
        x,rate,provenance=read_segment(segment,use)
        from fractions import Fraction
        ratio=Fraction(RATE,rate)
        y=signal.resample_poly(x,ratio.numerator,ratio.denominator,axis=0)
        f,t,z=signal.stft(y,RATE,nperseg=2048,noverlap=1536,axis=0,boundary=None,padded=False)
        # Average observed channel POWER, not L/R complex waveforms. A mono LF
        # source is a stated projection; no phase-cancellation or bank inference.
        density=(abs(z)**2).mean(axis=1)
        density=np.mean(density,axis=1)
        # Remove narrow whistles while retaining the source's broad LF contour.
        # 12Hz power smoothing is a design projection, not a denoising claim.
        smooth=ndimage.gaussian_filter1d(density,6/(f[1]-f[0]),mode='nearest')
        frequency=30+(np.arange(192)+.5)*270/192
        p=np.interp(frequency,f,smooth)
        p*=1/(1+(32/frequency)**8)/(1+(frequency/290)**12)
        # Shared full-scale LF level makes profile timbre comparisons meaningful;
        # this is an explicit engineering gain, not microphone/SPL calibration.
        target_rms=.14
        amplitude=np.sqrt(p/max(p.sum(),1e-30))*target_rms
        band=signal.sosfiltfilt(signal.butter(4,[35,280],btype='bandpass',fs=RATE,output='sos'),y,axis=0)
        env=np.sqrt(ndimage.uniform_filter1d(np.mean(band*band,axis=1),80)+1e-30)
        local=env/(ndimage.uniform_filter1d(env,800)+1e-12)-1
        corr=signal.correlate(local,local,mode='full',method='fft')[len(local)-1:]
        corr/=max(corr[0],1e-30)
        hits=np.flatnonzero(corr[:RATE//2]<np.exp(-1))
        measured=float(hits[0]/RATE) if len(hits) else .5
        tau=float(np.clip(measured,.025,.065))
        model=bank/f'{name}.model'
        with model.open('w',encoding='ascii',newline='\n') as stream:
            stream.write(f'VSL_LOW_RUMBLE 2 48000 192 30.703125 1.40625 {tau:.17g}\n')
            stream.write(' '.join(f'{v:.17g}' for v in amplitude)+'\n')
        entry=dict(name=name,file=model.name,model_sha256=sha(model),source=provenance,
                   oscillator_count=192,carrier_hz=[float(frequency[0]),float(frequency[-1])],
                   design=dict(full_amount_unfiltered_expected_rms=target_rms,
                               spectral_smoothing_sigma_hz=6,quadrature_tau_seconds=tau,
                               coefficient_update_hz=250,output_filter='Second-order24Hz highpass and340Hz lowpass'),
                   observed_envelope_efold_seconds=measured,
                   temporal_limit='Envelope correlation informs bounded quadrature bandwidth; not an identified physical damping or complete modulation fit.',
                   physical_limit='Filtered mixed recording spectrum, no engine/wind/road/room source separation.',
                   projection='Channel power average to ONE mono source; separate listener rendering required.')
        (fits/f'{name}.json').write_text(json.dumps(entry,ensure_ascii=False,indent=2),encoding='utf-8')
        np.savez(fits/f'{name}.npz',frequency=f,observed_power=density,smoothed_power=smooth,
                 carriers_hz=frequency,amplitude=amplitude,envelope=env,rate=RATE)
        index.append(entry)
    record=dict(schema='vsl.low-rumble-bank/2',profiles=index,
                default='A Exterior',
                separation_policy='Separate A exterior, B cabin, D dyno and E cabin profiles; never average their transfers together.',
                runtime='Fresh stochastic quadrature OSC generation; no PCM playback or analysis timeline.',
                DNA='Unchanged sound_dna_v1',status='New low layer pending listening')
    (bank/'index.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(profiles=[dict(name=v['name'],tau=v['design']['quadrature_tau_seconds']) for v in index]),indent=2))
