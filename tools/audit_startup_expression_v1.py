"""Audit saved PCM/stems/timing and freeze the candidate's actual sources."""
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RATE=48000
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def read(p):
    x,rate=sf.read(p,always_2d=True,dtype='float32');assert rate==RATE and x.shape[1]==2 and np.isfinite(x).all() and np.max(abs(x))<.95
    return x

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input;repo=Path(__file__).resolve().parents[1]
    v=json.loads((root/'verification.json').read_text());recipe=json.loads((root/'recipe.json').read_text())
    audio={p.name:read(p) for p in root.glob('*.wav')}
    mixed=np.zeros_like(audio['Candidate-96337.wav'])
    for name in ('prelude.wav','crank.wav','catch.wav','idle_handoff.wav'):mixed+=audio[name]
    assert np.array_equal(mixed,audio['Candidate-96337.wav'])
    end=round(v['handoff_complete_seconds']*RATE)
    assert np.array_equal(mixed[end:],audio['Continuous-DNA.wav'][end:])
    assert np.array_equal(audio['Alternate-seed-107071.wav'][end:],audio['Continuous-DNA.wav'][end:])
    previous=Path('E:/VehicleSoundLab/references/analysis/startup_rhythm_v1/listen1/Candidate-45943.wav')
    assert sha(root/'Previous.wav')==sha(previous)
    assert v['main_native_sha256']=='1865e6963c7667a5f163eea5a0ece18ac8e471f33ae6ebb313e9a23e83598418'
    assert sha(repo/'build-vehicle-source-v13/bin/Release/vsl_source_bridge.dll')==v['main_native_sha256']
    native=repo/'build-startup-character-v3/Release/startup_character_bridge.dll'
    assert sha(native)==sha(root/'startup_character_bridge.dll')==v['native_sha256']
    for name,info in v['outputs'].items():assert sha(root/name)==info['sha256']
    # listen1 was explicitly retained as an internal energy check. No model
    # refit or per-seed gain change occurred between the two level recipes.
    first=root.parent/'listen1'
    assert np.array_equal(read(first/'Continuous-DNA.wav'),audio['Continuous-DNA.wav'])
    assert np.array_equal(read(first/'Reference-exterior-full.wav'),audio['Reference-exterior-full.wav'])
    firstrecipe=json.loads((first/'recipe.json').read_text())
    scale_error={}
    for name in ('prelude','crank','catch'):
        expected=read(first/(name+'.wav')).astype(float)*(recipe[name]['level']/firstrecipe[name]['level'])
        scale_error[name]=float(np.max(abs(audio[name+'.wav']-expected)));assert scale_error[name]<3e-8
    states=json.loads((root/'telemetry.json').read_text())
    assert max(x['event_started'] for x in states)==0
    peak_rpm=max(x['rpm'] for x in states);assert abs(peak_rpm-2150)<1
    assert all(x['lifecycle']==4 and abs(x['rpm']-850)<1 for x in states if x['frame']/RATE>4.1)
    # Inspect source and saved synthesized action without normalizing each file.
    fig,axes=plt.subplots(4,1,figsize=(12,10),layout='constrained')
    for ax,name in zip(axes[:2],('Reference-exterior-full.wav','Candidate-96337.wav')):
        x=audio[name].mean(axis=1).astype(float);f,t,z=signal.stft(x,RATE,nperseg=2048,noverlap=1792,boundary=None)
        keep=(f>=40)&(f<=5000);ax.pcolormesh(t,f[keep],20*np.log10(np.maximum(abs(z[keep]),1e-8)),shading='auto',vmin=-80,vmax=-30)
        ax.set_ylim(40,5000);ax.set_yscale('log');ax.set_ylabel('Acoustic Hz');ax.set_title(name)
    for name in ('prelude.wav','crank.wav','catch.wav','idle_handoff.wav'):
        x=audio[name].astype(float);n=1440;hop=480
        pos=np.arange(0,len(x)-n+1,hop);r=np.array([np.sqrt(np.mean(x[i:i+n]**2)) for i in pos])
        axes[2].plot((pos+n/2)/RATE,20*np.log10(np.maximum(r,1e-7)),label=name[:-4])
    axes[2].set_ylim(-65,-15);axes[2].set_ylabel('RMS dBFS');axes[2].legend(ncol=4)
    for name,(lo,hi) in v['sections_seconds'].items():
        row=recipe[name];axes[3].plot(lo+(hi-lo)*np.array(row['pitch_knots']),row['pitch'],'.-',label=name+' pitch controls')
    axes[3].set_ylabel('OSC pitch multiplier');axes[3].legend();axes[3].set_xlabel('Output seconds')
    for ax in axes:ax.set_xlim(0,7);ax.grid(alpha=.15)
    fig.savefig(root/'action-audit.png',dpi=140);plt.close(fig)
    exact=root/'exact_sources';exact.mkdir()
    files=['tools/author_startup_expression_v1.py','tools/render_startup_expression_v1.py','tools/verify_startup_expression_v1.py','tools/audit_startup_expression_v1.py']
    for folder in ('modules/startup_character','modules/spectral_texture','modules/partitioned_fir','modules/resonant_detail','tools/startup_character_v1','experiments/startup_character_v1'):
        files.extend(str(p.relative_to(repo)) for p in (repo/folder).rglob('*') if p.is_file() and p.suffix in ('.c','.h','.py','.txt'))
    manifest={}
    for name in files:
        source=repo/name;dest=exact/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);manifest[name]=sha(source)
    report=dict(status='pass',saved_PCM_sum_exact=True,late_idle_exact_from_seconds=end/RATE,
        separate_seeds_same_idle=True,initial_pass_same_DNA_and_reference_PCM=True,initial_pass_only_named_levels_changed=scale_error,
        previous_file_exact=True,engineering_lifecycle_peak_rpm=peak_rpm,zero_legacy_triggers=True,
        all_saved_audio_finite_and_unclipped=True,main_binary_unchanged=True,starter_binary_matches_frozen=True,
        algorithmic_phase_and_partition_checks='startup_expression_v1/known1/verification.json',
        no_room_DSP=True,human_accepted=False,app_integrated=False,
        inspected_figure='action-audit.png',exact_sources=manifest)
    save(root/'audio-audit.json',report)
    hashes={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
    save(root/'final_verification.json',dict(schema='vsl.startup-expression-freeze/1',status='candidate_pending_hearing',files=hashes))
    print(json.dumps({k:report[k] for k in ('status','saved_PCM_sum_exact','late_idle_exact_from_seconds','engineering_lifecycle_peak_rpm','initial_pass_only_named_levels_changed','main_binary_unchanged')}),flush=True)
if __name__=='__main__':main()
