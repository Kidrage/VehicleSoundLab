"""Replace low detail shape using projected source residual; accepted voices unchanged."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','observation','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from idle_phase_amplitude_v1.residual import known,project,filters
from idle_phase_recipe_v1.render2 import noise

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},renders=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
try:
    names=['tools/render_idle_separated_residual_v1.py','tools/idle_phase_amplitude_v1/residual.py',
           'tools/idle_phase_recipe_v1/render2.py','tools/idle_texture_v2/spectral.py','tools/research_archive_v1.py',
           'research/idle_phase_amplitude_v1_residual_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    r['known']=known();print(dict(stage='known',result=r['known']),flush=True)
    parent=a.workspace/'baselines';profile=load(track(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    origin=parent/'idle_conditioned_detail_v1/evidence/observe1'
    with np.load(track(origin/'train.npz')) as f:audio=f['audio'];z=f['phasors']
    freq=np.array(profile['modal']['frequencies_hz']);residual,beta=project(audio,freq,z)
    h=filters(residual,[v['band_hz'] for v in profile['kernels'][:2]])
    np.savez_compressed(a.out/'extraction.npz',residual=residual,coefficients=beta,taps=h)
    save(a.out/'model.json',dict(schema='vsl.idle-separated-low-residual/1',taps=h.tolist(),
         gains=[v['gain'] for v in profile['kernels'][:2]],right_over_left=[v['right_over_left'] for v in profile['kernels'][:2]],
         basis='Joint13modal constant-coefficient projection; measured acoustic phase3modes',
         training_seconds=[6,9],trim_seconds=.25,PCM_or_source_trajectory=False,source_coefficients_not_used_at_runtime=True,
         runtime_adopted=False,listening_accepted=False))
    r.update(extraction_sha256=sha(a.out/'extraction.npz'),model_sha256=sha(a.out/'model.json'))
    original=load(track(a.input/'report.json'));assert original['result']=='finite_phase_aware_amplitude_audio_pending_audit'
    frames=24*48000;warm=profile['warmup_frames'];count=frames+warm
    for row in original['renders']:
        seed=row['seed'];delta=np.zeros((frames,2))
        for j,kernel in enumerate(profile['kernels'][:2]):
            excitation=noise(seed,j,count,'gaussian');difference=h[j]-np.array(kernel['taps'])
            y=signal.oaconvolve(excitation,difference)[warm:count]*kernel['gain']
            delta+=y[:,None]*[1.,kernel['right_over_left']]
        old,_=sf.read(track(a.input/row['files']['mix_0.0']['file']),always_2d=True)
        main,_=sf.read(track(a.input/row['files']['main_0.0']['file']),always_2d=True)
        moved_main,_=sf.read(track(a.input/row['files']['main_0.5']['file']),always_2d=True)
        files={};conditions=[('0.0',old,main),('0.5',old+delta,main),('1.0',old+delta+moved_main-main,moved_main)]
        for key,mix,source in conditions:
            for bus,wave in [('mix',mix),('main',source)]:
                assert np.isfinite(wave).all() and abs(wave).max()<.85
                path=a.out/f'{bus}_{key}_{seed}.wav';sf.write(path,wave,48000,subtype='FLOAT')
                files[bus+'_'+key]=dict(file=path.name,sha256=sha(path),peak=float(abs(wave).max()),rms=float(np.sqrt(np.mean(wave**2))))
        r['renders'].append(dict(seed=seed,frames=frames,files=files,
             delta_relative_mix_dB=float(20*np.log10(np.linalg.norm(delta)/np.linalg.norm(old))),
             base_is_frozen_FLOAT=True))
        save(a.out/'report.json',r);print(dict(seed=seed,delta_dB=r['renders'][-1]['delta_relative_mix_dB']),flush=True)
    r.update(result='finite_separated_low_residual_pending_audit',check_used_for_fit=False,
             physical_source_separation=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
