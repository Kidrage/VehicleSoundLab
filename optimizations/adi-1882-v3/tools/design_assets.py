"""Rebuild compact assets from the immutable FP32 reference; no audio runtime dependencies."""
from pathlib import Path
import argparse, json, re
import numpy as np
from scipy import signal, special

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--reference',type=Path,default=ROOT.parent/'VehicleSoundLab-1882-Baseline-20261120')
BASE=parser.parse_args().reference.resolve()
N = 131072
F = np.fft.rfftfreq(N, 1/48000)

def read(path):
    t = iter(path.read_text().split())
    assert next(t) == 'VSL_SPECTRAL_TEXTURE' and next(t) == '1'
    rate, count, warm = (int(next(t)) for _ in range(3))
    bands = []
    for _ in range(count):
        n, g, r = int(next(t)), float(next(t)), float(next(t))
        bands.append((g, r, np.array([float(next(t)) for _ in range(n)])))
    # The1882 board code selects the maximum-energy contiguous512-tap window.
    cropped=[]
    for g,r,h in bands:
        if len(h)>512:
            energy=np.convolve(h*h,np.ones(512),mode='valid')
            k=int(np.argmax(energy));h=h[k:k+512]
        cropped.append((g,r,h))
    return rate, warm, cropped

def minimum_phase(power, count=512):
    c = np.fft.irfft(.5*np.log(np.maximum(power, 1e-30)))
    c[1:len(c)//2] *= 2
    c[len(c)//2+1:] = 0
    return np.fft.irfft(np.exp(np.fft.rfft(c)))[:count]

def literals(a):
    return ',\n'.join('    '+','.join((f'{float(x):.9e}f') for x in a[k:k+6]) for k in range(0,len(a),6))

def write(path, warm, bands):
    s = f'VSL_SPECTRAL_TEXTURE 2\n48000 {len(bands)} {warm}\n'
    for d,g,r,h in bands:
        s += f'{len(h)} {g:.12g} {r:.12g} {d}\n'
        s += '\n'.join(' '.join(f'{x:.10g}' for x in h[k:k+8]) for k in range(0,len(h),8))+'\n'
    path.write_text(s)

def spectral_error(p, q):
    error = 10*np.log10(np.maximum(q,1e-30)/np.maximum(p,1e-30))
    return float(np.sqrt(np.sum(p*error**2)/np.sum(p)))

report = {}
idle = Path('experiments/spectral_texture_v1/F2_fine_static.sfir')
_, warm, original = read(BASE/idle)
power = sum(g*g*np.abs(np.fft.rfft(h,N))**2 for g,r,h in original)
# Preserve independent-source power, never add the six FIR amplitudes.
assert max(abs(r-1) for g,r,h in original) < 1e-5
D = 8
interp = signal.firwin(16*D+1, 1/D, window=('kaiser',9))*D
response = abs(np.fft.rfft(interp,N))**2/D
u = np.clip((F-1500)/900,0,1)
weight = 1-u*u*(3-2*u)
fl = np.fft.rfftfreq(N//D,D/48000)
low = minimum_phase(np.interp(fl,F,power*weight/np.maximum(response,1e-20)))
high = minimum_phase(power*(1-weight))
predicted_low = np.interp(F,fl,abs(np.fft.rfft(low,N//D))**2,right=0)*response
predicted_high = abs(np.fft.rfft(high,N))**2
scale = np.sqrt(np.sum(power)/np.sum(predicted_low+predicted_high))
low *= scale; high *= scale
write(ROOT/idle,warm,[(D,1,1,low),(1,1,1,high)])
report['idle'] = dict(old_bands=6,new_bands=2,taps_each=512,low_rate=6000,
    weighted_rms_db=spectral_error(power,(predicted_low+predicted_high)*scale**2),
    stereo_side_energy_ratio=float(sum(g*g*(r-1)**2 for g,r,h in original)/sum(g*g for g,r,h in original)))

# All other shipped FIR files remain independently excited Mid/Side bands.
for path in BASE.rglob('*.sfir'):
    rel = path.relative_to(BASE)
    if rel == idle or not (ROOT/rel).exists(): continue
    _,warm,bands = read(path)
    compact=[];errors=[]
    for g,r,h in bands:
        p=abs(np.fft.rfft(h,N))**2
        short=minimum_phase(p)
        short *= np.sqrt(np.sum(h*h)/np.sum(short*short))
        compact.append((1,g,r,short));errors.append(spectral_error(p,abs(np.fft.rfft(short,N))**2))
    write(ROOT/rel,warm,compact)
    report[rel.as_posix()] = dict(weighted_rms_db=errors)

# The production flare embeds its kernels. Rewrite from the original arrays;
# keep all ridge atoms, envelope knots and seeds unchanged.
model = (BASE/'modules/startup_flare/model.c').read_text()
errors=[]
def shorten(match):
    name,body=match.group(1),match.group(2)
    h=np.array([float(x.rstrip('f')) for x in re.findall(r'[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?f?',body)])
    assert len(h)==8192,(name,len(h))
    k=int(np.argmax(np.convolve(h*h,np.ones(512),mode='valid')))
    h=h[k:k+512]
    p=abs(np.fft.rfft(h,N))**2
    short=minimum_phase(p);short*=np.sqrt(sum(h*h)/sum(short*short))
    errors.append(spectral_error(p,abs(np.fft.rfft(short,N))**2))
    return f'static const float {name}[512]={{\n{literals(short)}\n}};'
model,n=re.subn(r'static const float (taps_\d_\d)\[8192\]\s*=\s*\{(.*?)\};',shorten,model,flags=re.S)
assert n==6,n
model=model.replace('.count=8192;','.count=512;')
(ROOT/'modules/startup_flare/model.c').write_text(model)
report['embedded_flare']=dict(weighted_rms_db=errors)

(ROOT/'dsp/interpolation.h').write_text('/* Generated 8x interpolator: Kaiser 129 taps, gain 8; phase-major. */\n'
    +'static const float sf_interpolation[8][17]={\n'
    +',\n'.join('  {'+','.join(f'{x:.9e}f' for x in np.pad(interp[phase::8],(0,17-len(interp[phase::8]))))+ '}' for phase in range(8))+'\n};\n')

# Half-normal inverse CDF: central 4096 cells; analytic tail handles rare >3.67 sigma.
x=np.linspace(.5,1-1/8192,4097)
table=special.ndtri(x)
(ROOT/'dsp/normal_table.h').write_text('/* Generated central half-normal quantile table. */\nstatic const float normal_table[4097]={\n'+literals(table)+'\n};\n')
(ROOT/'dsp/wave_table.h').write_text('/* Generated one-cycle sine table. */\nstatic const float wave_table[4096]={\n'+literals(np.sin(2*np.pi*np.arange(4096)/4096))+'\n};\n')
(ROOT/'docs/asset_design.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k in ('idle','embedded_flare')},indent=2))
