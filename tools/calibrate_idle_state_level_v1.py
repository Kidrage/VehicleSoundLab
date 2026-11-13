"""One fixed monitoring trim from the first complete idle hold, then observe the next."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_calibrate.py')
plan=repo/'research/idle_state_level_v1_plan.json';shutil.copy2(plan,a.out/'plan.json')
report=json.loads((a.input/'report.json').read_text(encoding='utf-8'))
assert report['result']=='continuous_idle_state_and_all84_legacy_WAVs_verified'
trace=np.fromfile(a.input/'enabled/C_trace.f64',dtype='<f8').reshape((-1,6))
on,rate=sf.read(a.input/'enabled/C_mix.wav',always_2d=True);off,rate2=sf.read(a.input/'disabled/C_mix.wav',always_2d=True)
assert rate==rate2==48000 and len(on)==len(off)==len(trace)
full=(trace[:,4]==1);starts=np.flatnonzero(full&~np.r_[False,full[:-1]])
stops=np.flatnonzero(full&~np.r_[full[1:],False])+1
assert len(starts)==len(stops)==2
first=slice(starts[0],stops[0]);gain=float(np.sqrt(np.mean(off[first]**2)/np.mean(on[first]**2)))
assert 0<gain<=8
holds=[]
for index,(start,stop) in enumerate(zip(starts,stops)):
    x=on[start:stop];y=off[start:stop]
    a_rms=float(np.sqrt(np.mean(x*x)));b_rms=float(np.sqrt(np.mean(y*y)))
    holds.append(dict(use='trim_fit' if index==0 else 'unfit_monitoring_check',frames=[int(start),int(stop)],
        seconds=[float(start/48000),float(stop/48000)],candidate_RMS=a_rms,original_RMS=b_rms,
        old_difference_db=float(20*np.log10(a_rms/b_rms)),after_fixed_trim_db=float(20*np.log10(gain*a_rms/b_rms))))
text='#ifndef VSL_IDLE_STATE_STUDY_H\n#define VSL_IDLE_STATE_STUDY_H\n'
text+='/* Fixed monitoring trim from render1 first full idle hold; not measured\n   SPL/RPM. Raw F2 timbre unchanged. See idle_state_level_v1 calibration. */\n'
text+=f'#define IS_IDLE_LEVEL_GAIN {gain:.17g}\n#define IS_IDLE_FADE_FRAMES 3840u\n#endif\n'
(a.out/'study.h').write_text(text,encoding='utf-8',newline='\n')
result=dict(result='one_fixed_monitoring_trim_derived',level_gain=gain,holds=holds,
    input_report_sha256=sha(a.input/'report.json'),plan_sha256=sha(plan),source_sha256=sha(Path(__file__)),
    generated_header_sha256=sha(a.out/'study.h'),source_timbre_changed=False,real_SPL_or_RPM_calibrated=False)
(a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result),flush=True)
