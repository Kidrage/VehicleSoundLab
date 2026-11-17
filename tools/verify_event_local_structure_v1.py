"""Known-first local structure accuracy and confound controls; no real source reads."""
import argparse
from pathlib import Path
import shutil

import numpy as np
from scipy import signal

from audit_event_local_structure_v1 import finite_oracle,check_rows
from event_local_structure.spectrum import WINDOWS,observe
from event_local_structure.inspect import inspect
from event_local_structure.links import graph
from research_archive_v1 import save,sha


def fixtures():
    count=38400;t=np.arange(count)/48000
    tone=sum(.12/(1+i*.3)*np.cos(2*np.pi*f*t+.3*i) for i,f in enumerate([147.13,563.41,1713.19,6991.31]))
    def stereo(x):return np.column_stack((x,.7*x))
    rng=np.random.default_rng(892713)
    white=rng.normal(0,.12,(count,2))
    w=2*np.pi*730.31/48000;q=60;alpha=np.sin(w)/(2*q)
    b=np.array([alpha,0,-alpha])/(1+alpha);a=np.array([1,-2*np.cos(w)/(1+alpha),(1-alpha)/(1+alpha)])
    noise=signal.lfilter(b,a,rng.normal(size=count+48000))[48000:]
    noise*=.12/np.sqrt(np.mean(noise*noise))
    gap=np.cos(2*np.pi*600.31*t+.2)*.12;gap[(t>=.25)&(t<.55)]=0
    u=np.maximum(t-.15,0)
    ring=np.where(t>=.15,.4*np.exp(-u/.08)*np.cos(2*np.pi*1800.31*u+.3),0)
    impulse=np.zeros(count);impulse[9600]=.5;impulse[19200]=-.35
    return dict(off_grid_tones=stereo(tone),am_tones=stereo(tone*(1+.25*np.sin(2*np.pi*6*t))),
        on_bin_tone=stereo(.12*np.cos(2*np.pi*500*t+.4)),
        moving_chirp=stereo(.15*np.cos(2*np.pi*(600*t+.5*800*t*t)+.2)),
        damped_ringing=stereo(ring),impulses=stereo(impulse),independent_white_noise=white,
        stochastic_resonance=stereo(noise),missing_interval=stereo(gap),silence=np.zeros((count,2))),t


def run(out):
    waves,t=fixtures();np.savez_compressed(out/'known-fixtures.npz',**waves)
    report=dict(result='running',observations=[],known_frequency_checks=[],
        goal_complete=False,timbre_accepted=False,physical_classifier_qualified=False)
    for name,x in waves.items():
        for n in WINDOWS:
            for hop in (n,n//4):
                result,observed=inspect(x,n,hop)
                expected,c=finite_oracle(x,n,hop)
                np.testing.assert_allclose(observed['power'],expected,atol=2e-14,rtol=2e-12)
                check_rows(result,expected,c)
                report['observations'].append(dict(fixture=name,window_frames=n,hop_frames=hop,
                    windows=result['windows'],summaries=result['summaries']))
                if name=='silence':assert not result['links'] and all(not row['peaks'] for row in result['inventories'])
                if name=='on_bin_tone':
                    peaks=[min(row['peaks'],key=lambda p:abs(p['hz']-500)) for row in result['inventories']]
                    assert max(abs(p['hz']-500) for p in peaks)<1e-6
                    assert max(abs(p['half_power_width_hz']/(48000/n)-4/3) for p in peaks)<1e-6
                if name=='off_grid_tones':
                    errors=[]
                    for row in result['inventories']:
                        for f in (563.41,1713.19,6991.31):
                            peak=min(row['peaks'],key=lambda p:abs(p['hz']-f))
                            errors.append(abs(peak['hz']-f))
                    maximum=max(errors);assert maximum<.04*48000/n,(n,maximum)
                    selected=[link for link in result['links'] if link['state']=='unique' and link['left_hz']>500]
                    residual=np.array([link['phase_residual_cycles_LR'] for link in selected])
                    assert abs(residual).max()<.04,(n,hop,abs(residual).max())
                    report['known_frequency_checks'].append(dict(window_frames=n,hop_frames=hop,
                        maximum_off_grid_error_hz=maximum,maximum_phase_residual_cycles=float(abs(residual).max())))
                if name=='moving_chirp':
                    errors=[]
                    for row in result['inventories']:
                        truth=600+800*row['centre_seconds']
                        errors.append(min(abs(p['hz']-truth) for p in row['peaks']))
                    assert max(errors)<2*48000/n,(n,max(errors))
                if name=='missing_interval':
                    empty=[row for row in result['inventories'] if row['first_sample']/48000>=.25 and (row['first_sample']+n)/48000<=.55]
                    assert empty and all(not row['peaks'] for row in empty)
                    assert all(link['right_frame']==link['left_frame']+1 for link in result['links'])
            print(name,n,'native/phase/width/graph checks pass',flush=True)
    # Gain and antiphase checks are independent of waveform folding.
    for n in WINDOWS:
        plain,po=inspect(waves['off_grid_tones'],n,n)
        gain,go=inspect(.001*waves['off_grid_tones'],n,n)
        np.testing.assert_allclose(go['power'],1e-6*po['power'],atol=1e-20,rtol=2e-10)
        for left,right in zip(plain['inventories'],gain['inventories']):
            np.testing.assert_allclose([p['hz'] for p in left['peaks']],[p['hz'] for p in right['peaks']],atol=1e-7)
        mono=waves['off_grid_tones'][:,0]
        same=observe(np.column_stack((mono,mono)),n,n)
        anti=observe(np.column_stack((mono,-mono)),n,n)
        np.testing.assert_array_equal(same['power'],anti['power'])
        assert np.mean(np.column_stack((mono,-mono)).mean(axis=1)**2)==0
    assert [r['state'] for r in graph([1000,1008],[1004],20)]==['ambiguous','ambiguous']
    invalid=0
    for call in (lambda:observe(np.zeros((100,2)),768,768),lambda:observe(np.zeros((8000,2)),1024,256),
                 lambda:observe(np.zeros((8000,1)),768,192),lambda:graph([np.nan],[1],1)):
        try:call()
        except ValueError:invalid+=1
        else:raise AssertionError('Invalid observer input accepted')
    report.update(result='passed',invalid_inputs_refused=invalid,antiphase_power_preserved=True,
        no_gap_bridge=True,direct_DFT_and_Parseval=True,
        width_scope='Finite interpolated Hann peak width. On-bin isolated tone is4/3 native bins; not deconvolved physical damping.',
        noise_controls_are_descriptive_not_classes=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    sources=[*sorted((repo/'tools/event_local_structure').glob('*.py')),
        repo/'tools/event_local_structure/README.md',repo/'research/event_local_structure_v1_plan.json',
        Path(__file__),repo/'tools/audit_event_local_structure_v1.py']
    bindings={}
    for source in sources:
        name=source.relative_to(repo);dest=out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);bindings[name.as_posix()]=sha(source)
    save(out/'report.json',dict(result='running',source_bindings=bindings))
    try:report=run(out)
    except Exception as error:
        save(out/'report.json',dict(result='failed',error=repr(error),source_bindings=bindings));raise
    report['source_bindings']=bindings;save(out/'report.json',report)
    print('known local observer passes; noise/chirp confounds retained without physical labels',flush=True)


if __name__=='__main__':main()
