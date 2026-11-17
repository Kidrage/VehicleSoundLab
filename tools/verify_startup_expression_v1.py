"""Independent phase integral and control checks, before authoring real audio."""
import argparse,json
from copy import deepcopy
from pathlib import Path
import numpy as np
from startup_character_v1.expression import ExpressionStarter
from render_startup_ridges_v1 import known as previous_contracts

RATE=48000
def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    previous_contracts(a.library,Path('E:/VehicleSoundLab/references/analysis/startup_character_v1/attempt2/startup_character_bridge.dll'),a.output/'previous')
    paths=[]
    for k in range(3):
        path=a.output/f'zero-{k}.sfir';path.write_text('VSL_SPECTRAL_TEXTURE 1 48000 2 0\n1 0 1\n1\n1 0 -1\n1\n',encoding='ascii');paths.append(dict(path=str(path.resolve())))
    rows=[dict(start_frame=1536,frames=4096,hz=750.,slew_hz_per_second=2000.,amplitude=[.3,.2],phase=[.2,.7]),
          dict(start_frame=6144,frames=4096,hz=1500.,slew_hz_per_second=-2000.,amplitude=[.1,.15],phase=[.1,-.3])]
    profile=dict(profiles=paths,envelope=[1.]*9,variation=0.,ridges=rows,reference_frames=12288,ridge_variation=0.,ridge_pitch=1.)
    frames=17280;p0=np.arange(frames)/frames;gate=np.ones(frames,dtype=np.int32)
    pitch=.9+.25*np.sin(np.arange(frames)/frames*np.pi)
    def run(chunk,core=1.,texture=1.,scale=1.,vary=pitch):
        v=ExpressionStarter(a.library,profile,91241)
        try:return np.concatenate([v.expression(p0[n:n+chunk],gate[n:n+chunk],scale,vary[n:n+chunk],core,texture) for n in range(0,frames,chunk)])
        finally:v.close()
    expected=np.zeros((frames,2));position=p0*12288
    for row in rows:
        local=position-row['start_frame'];idx=np.flatnonzero((local>=0)&(local<row['frames']));t=local[idx]/RATE
        hz=(row['hz']+row['slew_hz_per_second']*t)*pitch[idx]
        phase=np.empty(len(idx));phase[0]=2*np.pi*pitch[idx[0]]*(row['hz']*t[0]+.5*row['slew_hz_per_second']*t[0]**2)
        phase[1:]=phase[0]+np.cumsum(np.pi*(hz[1:]+hz[:-1])/RATE)
        window=.5-.5*np.cos(2*np.pi*local[idx]/row['frames'])
        expected[idx]+=window[:,None]*np.array(row['amplitude'])*np.cos(phase[:,None]+row['phase'])
    expected*= (1-np.exp(-(np.arange(frames)+1)/384))[:,None]
    actual=run(217);error=float(np.max(abs(actual-expected)))
    assert error<3e-8,error
    assert np.array_equal(actual,run(479))
    assert np.array_equal(actual*.5,run(479,scale=.5))
    assert np.array_equal(actual,run(479,texture=0.)) # spectral source is explicitly zero
    assert not np.any(run(479,core=0.))
    assert not np.array_equal(actual,run(479,vary=np.ones(frames)))
    bad=ExpressionStarter(a.library,profile,91241)
    try:
        try:bad.expression(p0[:100],gate[:100],pitch=3.);raise AssertionError('Invalid pitch accepted')
        except RuntimeError:pass
    finally:bad.close()
    report=dict(status='pass',dynamic_pitch_independent_phase_error=error,independent_duration_ratio=frames/12288,
        partition_exact=True,source_gain_linear=True,separate_core_texture_controls=True,invalid_pitch_rejected=True,
        previous_noise_and_fixed_pitch_contracts='pass',hearing_acceptance=False)
    (a.output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
