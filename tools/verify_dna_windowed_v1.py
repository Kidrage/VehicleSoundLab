"""Verify legacy equivalence, integer-line response and LF boundary leakage."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sound_dna.profile import estimate as legacy
from sound_dna.windowed import coefficients
from drive_evidence_v1.sources import sha

if args.out.exists():raise RuntimeError('Preserve completed controls')
folder=args.workspace/'references/analysis/drive_evidence_v1'
previous=folder/'cabin_anchors/initial_sources/profile.py'
spec=importlib.util.spec_from_file_location('pre_refactor_profile',previous)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
sample=np.random.default_rng(34827).normal(0,.01,(32768,2))
old,old_stats=module.estimate(sample,32,8)
new,new_stats=legacy(sample,32,8)
assert old_stats==new_stats and all(np.array_equal(old[k],new[k]) for k in old)

size=48000*2
t=np.arange(size)/48000
clean=np.zeros((size,2));truth=np.zeros((288,4))
for multiple,amplitude in [(2,.08),(3,.05),(5,.04),(7,.025),(180,.001)]:
    for channel in (0,1):
        phase=.2*multiple+.3*channel
        clean[:,channel]+=amplitude*np.cos(2*np.pi*multiple*46.875*t+phase)
        truth[multiple-1,channel*2:channel*2+2]=amplitude*np.array([np.cos(phase),np.sin(phase)])
rows=coefficients(clean,288,4)
line_error=float(abs(rows.mean(axis=0).reshape(288,4)-truth).max())
assert line_error<1e-12

# A low, nonlattice tone with zero intended high-frequency content. Rectangular
# single-cycle cuts leak it into every high harmonic. Test before covariance
# fitting / rendering, without high-frequency EQ.
off=.1*np.cos(2*np.pi*13.2*t)
x=clean.copy();x[:,0]+=off;x[:,1]+=off
k=np.arange(1,289);rect=[]
for start in range(0,len(x)-1024+1,256):
    z=np.fft.rfft(x[start:start+1024],axis=0)[k]*2/1024*np.exp(-2j*np.pi*k*start/1024)[:,None]
    rect.append(np.column_stack([z[:,0].real,z[:,0].imag,z[:,1].real,z[:,1].imag]).ravel())
rect=np.asarray(rect).reshape(-1,288,4)
taper=coefficients(x,288,4).reshape(-1,288,4)
# Exclude the deliberately included known180th harmonic from the leakage band.
mask=(k*46.875>=8000)&(k*46.875<=14000)&(k!=180)
rect_power=float(np.mean(np.sum(rect[:,mask]**2,axis=(1,2))))
taper_power=float(np.mean(np.sum(taper[:,mask]**2,axis=(1,2))))
suppression=float(10*np.log10(taper_power/rect_power))
assert suppression < -40

fig,axes=plt.subplots(1,2,figsize=(13,4),constrained_layout=True)
for axis,name in zip(axes,('E Cabin Lower','E Cabin Upper')):
    for label,path,gain in [('Fixed-pitch recording',folder/'cabin_anchors_tapered'/name/'fixed_reference.wav',2),
        ('Single-cycle rectangular C',folder/'cabin_anchors'/name/'raw_1.0.wav',1),
        ('Four-cycle Hann C',folder/'cabin_anchors_tapered'/name/'raw_1.0.wav',1)]:
        audio,rate=sf.read(path,always_2d=True)
        audio=audio[240:-240]*gain
        hz,psd=signal.welch(audio,rate,nperseg=4096,axis=0,detrend=False)
        axis.semilogx(hz,10*np.log10(np.maximum(psd.mean(axis=1),1e-30)),label=label,lw=1)
    axis.set_xlim(300,14000);axis.set_ylim(-120,-20);axis.set_title(name)
    axis.set_xlabel('Hz | same raw level; no per-clip matching');axis.set_ylabel('PSD dBFS/Hz');axis.grid(alpha=.2)
axes[0].legend(fontsize=8)
image=args.out.with_suffix('.png');fig.savefig(image,dpi=150);plt.close(fig)
result=dict(schema='vsl.dna-windowed-controls/1',result='pass',
    legacy_statistics_refactor_bit_equal=True,legacy_source_snapshot_sha256=sha(previous),
    integer_harmonic_complex_mean_max_error=line_error,
    known_LF_offlattice_tone_high_band_leakage_change_db=suppression,
    observation_policy='Legacy compiler stays rectangular by default; only new E experiment opts into4-cycle Hann',
    plot_sha256=sha(image),verifier_sha256=sha(__file__),
    limits='Known-signal leakage mechanism verified; finite real-recording spectra do not prove all perceptual artifacts removed')
args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
