"""Validate the descriptive envelope meter with known tones, beats and AM."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from residual_dense_v1.envelope import measure

args.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),repo/'tools/residual_dense_v1/envelope.py',repo/'tools/drive_evidence_v1/sources.py']
for p in paths:
    target=args.out/'exact_sources'/p.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
r=dict(schema='vsl.residual-dense-envelope-controls/1',result='running',controls=[],
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths})
try:
    rate=48000;n=2048;hop=256;t=np.arange(16*rate)/rate
    carrier=299*rate/n;beat=rate/n;modulation=5.859375
    cases=[('fixed',np.cos(2*np.pi*carrier*t),None),
        ('two_tones',np.cos(2*np.pi*carrier*t)+np.cos(2*np.pi*(carrier+beat)*t),beat),
        ('explicit_AM',(1+.3*np.cos(2*np.pi*modulation*t))*np.cos(2*np.pi*carrier*t),modulation)]
    window=.5-.5*np.cos(2*np.pi*np.arange(n)/n);weight=window**2;weight/=sum(weight)
    starts=range(0,len(t)-n+1,hop);clock=np.arange(len(starts))*hop/rate
    design=np.column_stack((np.ones(len(clock)),clock-clock.mean()))
    mod_hz=np.fft.rfftfreq(len(clock),hop/rate);selected=np.flatnonzero((mod_hz>=.5)&(mod_hz<=40))
    for name,audio,expected_peak in cases:
        stereo=np.column_stack((audio,.7*audio))
        observed=measure(stereo,[(6000,8000)])
        # Independent time-domain weighted energy, no STFT or band-bin sum.
        power=np.array([weight@(audio[at:at+n]**2) for at in starts])
        relative=power/power.mean()-1
        relative-=design@np.linalg.lstsq(design,relative,rcond=None)[0]
        cv=float(np.sqrt(np.mean(relative**2)))
        measured_cv=observed['power_cv_LR'][0][0]
        cv_error=abs(cv-measured_cv);assert cv_error<2e-7,(name,cv_error)
        channel_error=abs(observed['power_cv_LR'][0][1]-measured_cv);assert channel_error<1e-12
        row=dict(name=name,expected_peak_hz=expected_peak,observed=observed,
            independent_time_energy_cv=cv,cv_absolute_error=cv_error,channel_scale_cv_error=channel_error)
        if expected_peak is None:
            assert measured_cv<1e-10
        else:
            measured_peak=observed['envelope_peak_hz_LR'][0][0]
            peak_error=abs(measured_peak-expected_peak);assert peak_error<rate/(hop*len(clock))
            # Scalar trigonometric modulation sum verifies the reported peak
            # power fraction; no second FFT is used by this oracle.
            sums=np.array([abs(np.exp(-2j*np.pi*mod_hz[k]*clock)@relative)**2 for k in selected])
            fraction=float(sums.max()/sum(sums))
            fraction_error=abs(fraction-observed['envelope_peak_bin_fraction_LR'][0][0])
            assert fraction_error<2e-7,(name,fraction_error)
            row.update(peak_error_hz=peak_error,independent_peak_bin_fraction=fraction,peak_fraction_absolute_error=fraction_error)
        r['controls'].append(row)
    r.update(result='pass',interpretation='A two-tone stationary sum produces envelope modulation without explicit AM. These checks validate the meter, not an engine-source attribution or perceptual improvement.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],controls=len(r['controls']),maximum_cv_error=max(x['cv_absolute_error'] for x in r['controls']))))
