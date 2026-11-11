"""Known-signal tests for low-root resampling alias and carrier clock correction."""
import argparse
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from exterior_clock_v1.warp import warp,polish,carrier_rows
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True,exist_ok=False)
t=np.arange(48000*5)/48000
x=np.column_stack([.1*np.cos(2*np.pi*12000*t),.07*np.cos(2*np.pi*12000*t+.4)])
clock=np.linspace(.2,4.8,461);hz=np.full_like(clock,10.)
legacy,_,_=warp(x,0,clock,hz,.4,4.6,adaptive=False)
protected,_,meta=warp(x,0,clock,hz,.4,4.6,adaptive=True)
legacy_alias=float(np.sqrt(np.mean(legacy[2048:-2048]**2)))
protected_alias=float(np.sqrt(np.mean(protected[2048:-2048]**2)))
assert legacy_alias>.03 and protected_alias<1e-6

# A genuine varying clock; supplied frequencies have a known bias. Synthesize
# separate L/R amplitudes and phases directly in source time, not via the warp.
true_hz=32+8*np.sin(2*np.pi*.17*t)
true_cycles=np.r_[0,np.cumsum((true_hz[1:]+true_hz[:-1])/(2*48000))]
audio=np.zeros((len(t),2));partials=[(3,.04),(5,.15),(7,.03),(10,.08),(15,.025)]
for order,amplitude in partials:
    for c in (0,1):audio[:,c]+=amplitude*(1-.2*c)*np.cos(2*np.pi*order*true_cycles+.13*order+.35*c)
observed=np.interp(clock,t,true_hz)*1.008
y,positions,initial=warp(audio,0,clock,observed,.4,4.6)
corrected,where,phase=polish(audio,0,y,positions,5,initial['source_cutoff_hz'])
def error(data,source_positions):
    # Known high-order waveform accuracy, allowing only the arbitrary common
    # cycle origin left by reference phase fitting; no per-channel alignment.
    q=np.interp(source_positions,t,true_cycles)
    ideal_phase=source_positions*0+np.arange(len(data))/1024
    residual=q-ideal_phase
    return float(np.std(residual))
before=error(y,positions);after=error(corrected,where)
assert before>.1 and after<.002 and after<before/50
coherence={}
for order,_ in partials:
    _,rows=carrier_rows(corrected,order)
    coherent=abs(rows.mean(axis=0))/np.mean(abs(rows),axis=0)
    assert min(coherent)>.99
    phase_difference=np.angle(rows[:,1]/rows[:,0])
    assert max(abs(np.angle(np.exp(1j*(phase_difference-.35)))))<.002
    coherence[str(order)]=coherent.tolist()
result=dict(schema='vsl.exterior-warp-controls/1',result='pass',
    legacy_14k_alias_rms=legacy_alias,adaptive_alias_rms=protected_alias,
    low_root_filter=meta,known_clock_cycle_residual_std_before=before,
    known_clock_cycle_residual_std_after=after,phase_fit=phase,
    heldout_carrier_coherence=coherence,limits='Known signals only; real reference/order paths still need independent evidence',
    source_sha256={str(p.relative_to(Path(__file__).parent)).replace('\\','/'):sha(p)
        for p in [Path(__file__),Path(__file__).parent/'exterior_clock_v1/warp.py']})
(args.out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(alias_change_db=20*np.log10(protected_alias/legacy_alias),clock_cycles_std=[before,after])))
