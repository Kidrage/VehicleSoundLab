"""Observe separate reviewed F2 spectral line motions without extracting a phase clock."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--method',choices=('raw','center'),default='raw')
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from line_motion_v1.moments import observe,group_observation
from line_motion_v1.controls import controls
from line_motion_v1.center import centered


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def serial(value):return {k:v.tolist() for k,v in value.items()}


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-line-motion/1',result='running',sources={},real_audio_read=False,
            phase_estimator_run=False,model_exported=False,runtime_changed=False)
try:
    plan=load(repo/'research/F2_line_motion_v1_plan.json')
    parent_path=args.workspace/'references/analysis/F2_idle_observation_v1/audit1/report.json'
    parent=load(parent_path)
    for path in (Path(__file__),repo/'research/F2_line_motion_v1_plan.json',repo/'tools/drive_evidence_v1/sources.py',
                 repo/'research/F2_line_motion_center_v1_plan.json',
                 repo/'references/segments_v1.json',*sorted((repo/'tools/line_motion_v1').glob('*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    observer=observe if args.method=='raw' else centered
    checked=controls(observer=observer);report['controls']=checked;report['method']=args.method
    assert checked['passed'],'Local observation controls failed; no recording read permitted'
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation')
    report['real_audio_read']=True
    assert audio.shape==(6*48000,2)
    rows=[];numeric=[]
    for block,previous in enumerate(parent['display_only_low_band_peaks']):
        nominal=previous['L_native1Hz_peak_bins_Hz']
        for offset in (0,24000,48000):
            start=block*96000+offset
            part=audio[start:start+48000]
            measured=observer(part,48000,nominal)
            grouped=group_observation(measured['frequency_Hz'])
            rows.append(dict(source_seconds=[6+start/48000,7+start/48000],nominal_Hz=nominal,
                measured=serial({k:measured[k] for k in measured if k not in ('moment','derivative_moment')}),
                exploratory_group=serial(grouped),
                all_anchor_roots_resolved=bool(measured.get('root_resolved',np.ones((5,2),dtype=bool))[:3].all())))
            numeric.append(measured)
    np.savez_compressed(args.out/'observations.npz',audio=audio,
        **{key:np.stack([x[key] for x in numeric]) for key in numeric[0]})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(10,8),layout='constrained')
    centers=[sum(x['source_seconds'])/2 for x in rows]
    for i,order in enumerate((2,3,5)):
        values=[x['exploratory_group']['anchor_divided_frequencies_Hz'][i][0] for x in rows]
        axes[0].plot(centers,values,'o-',label='measured line / '+str(order))
    axes[0].plot(centers,[x['measured']['frequency_Hz'][4][0] for x in rows],'x--',label='withheld37/38Hz line')
    axes[0].set(ylabel='Acoustic family coordinate / Hz',title='F2 raw left-channel local line observations; no RPM or phase clock')
    axes[0].legend(fontsize=8)
    for i in range(3):axes[1].plot(centers,[x['exploratory_group']['leave_one_out_base_error_Hz'][i][0] for x in rows],'o-',label='anchor '+str(i+1))
    axes[1].plot(centers,[x['exploratory_group']['heldout_order1_error_Hz'][0] for x in rows],'x--',label='withheld order1')
    axes[1].set(ylabel='Prediction mismatch / Hz');axes[1].legend(fontsize=8)
    axes[2].plot(centers,[x['exploratory_group']['extra_11_over_5_error_Hz'][0] for x in rows],'o-',color='#a54b36')
    axes[2].set(xlabel='Original source time / s',ylabel='82/81Hz line minus11/5 prediction / Hz')
    fig.savefig(args.out/'F2_line_motion.png',dpi=150);plt.close(fig)
    report.update(result='separate_F2_line_frequency_moments_observed_not_period_or_DNA_qualification',
        provenance=provenance,parent_report_sha256=sha(parent_path),observations=rows,
        arrays_sha256=sha(args.out/'observations.npz'),plot_sha256=sha(args.out/'F2_line_motion.png'),
        selected_fundamental=None,RPM_inferred=False,phase_extracted_real_model_permitted=False,
        limits=['Local derivatives in mixed audio can be biased by neighboring lines, drift, AM and noise; no calibrated frequency confidence',
                'Orders chosen after viewing prior spectrum; heldout line is independent of the3-line mean, not independent hypothesis discovery',
                'Shared motion cannot select physical period or distinguish slower fundamental/sidebands/microphone effects',
                'No source separation, new audio/DNA/model/runtime/C changes'])
    print(json.dumps(dict(result=report['result'],controls=checked['cases'],observations=rows)),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
