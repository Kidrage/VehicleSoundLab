"""Direct frame FFT and sample audit, independent of the producer helper."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
root=a.workspace/'references/analysis/D_flame_audio_v1';r=dict(result='running')
try:
    plan=load(repo/'research/D_flame_audio_v1_plan.json');original=load(root/'audio1/report.json')
    assert original['result']=='fixed_window_observed' and original['known_before_source']['steady_false_candidates']==0
    source=load(repo/'references/segments_v1.json')['sources']['D'];master=a.workspace/source['master']
    assert sha(master)==source['master_sha256'] and sha(a.workspace/source['raw'])==source['raw_sha256']
    with sf.SoundFile(master) as f:
        assert f.samplerate==48000 and f.channels==2;f.seek(36*48000);audio=f.read(8*48000,always_2d=True)
    native,rate=sf.read(root/'audio1/native_reference.wav',always_2d=True);assert rate==48000 and np.array_equal(native,audio)
    for row in original['clips']:
        lo,hi=row['source_seconds'];expected=audio[(lo-36)*48000:(hi-36)*48000].copy()*.5
        f=(1-np.cos(np.pi*np.arange(240)/240))/2;expected[:240]*=f[:,None];expected[-240:]*=f[::-1,None]
        actual,rate=sf.read(root/'audio1'/row['file'],always_2d=True)
        assert rate==48000 and np.array_equal(actual,expected.astype('float32').astype('float64')) and sha(root/'audio1'/row['file'])==row['sha256']
    size,hop=960,240;w=.5-.5*np.cos(2*np.pi*np.arange(size)/size);hz=np.arange(481)*50
    powers=[];cross=[];rms=[];crest=[]
    for start in range(0,len(audio)-size+1,hop):
        frame=audio[start:start+size];z=np.fft.rfft(frame*w[:,None],axis=0)
        density=abs(z)**2/(48000*np.dot(w,w));c=z[:,1]*z[:,0].conj()/(48000*np.dot(w,w))
        density[1:-1]*=2;c[1:-1]*=2
        powers.append([[np.sum(density[(hz>=lo)&(hz<hi),ch])*50 for ch in range(2)] for lo,hi in plan['bands_hz']])
        cross.append([np.sum(c[(hz>=lo)&(hz<hi)])*50 for lo,hi in plan['bands_hz']])
        energy=np.sqrt(np.mean(frame**2,axis=0));rms.append(energy);crest.append(np.max(abs(frame),axis=0)/energy)
    powers=np.array(powers);cross=np.array(cross);v=np.load(root/'audio1/observations.npz')
    power_error=float(np.max(abs(powers-v['bands'])));cross_error=float(np.max(abs(cross-v['cross'])))
    assert power_error<2e-15 and cross_error<2e-15
    assert np.max(abs(rms-v['rms']))<2e-15 and np.max(abs(crest-v['crest']))<2e-14
    mono=powers.mean(axis=2);padded=np.pad(mono,((50,50),(0,0)),mode='edge')
    baseline=np.array([np.sort(padded[i:i+101],axis=0)[50] for i in range(len(mono))])
    excess=10*np.log10(mono/baseline);error=float(np.max(abs(excess-v['excess'])))
    assert error<1e-11
    score=np.sort(excess[:,[3,4,5]],axis=1)[:,1]
    assert score.max()<6 and len(v['peaks'])==0 and original['candidates']==[]
    frames=load(root/'frames1/report.json')['sources']['D']['frames'];times=[v['source_seconds'] for v in frames]
    assert len(frames)==35 and min(np.diff(times))>.232 and max(np.diff(times))<.235
    for row in frames:assert sha(root/'frames1/D'/row['file'])==row['sha256']
    protected=a.workspace/'baselines/catalog_decel_v1/inputs'
    old=load(protected/'C_files_sha256.json');voices=load(protected/'voice_files_sha256.json')
    assert len(old)==646 and len(voices)==74 and all(sha(repo/n)==h for n,h in {**old,**voices}.items())
    for n in ['experiments/modal_idle_v1/F2_fixed_idle.msource','experiments/modal_texture_v1/F2_amplitude.mtexture','experiments/spectral_texture_v1/F2_fine_static.sfir']:
        assert sha(repo/n)==sha(a.workspace/'baselines/catalog_decel_v1/source'/n)
    r.update(result='passed',native_samples_exact=True,all_four_clips_exact=True,all1597_frames_checked=len(powers),
        maximum_band_power_error_FS2=power_error,maximum_cross_power_error_FS2=cross_error,maximum_excess_error_db=error,
        maximum_two_band_excess_db=float(score.max()),fixed_gate_candidates=0,original_PTS_frames=35,
        protected_C_H=646,protected_voices=74,F2_exact=True,physical_backfire_proven=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
