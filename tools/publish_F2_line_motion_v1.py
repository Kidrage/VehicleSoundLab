"""Publish audited bounded observations with unresolved roots visibly separated."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def load(path):return json.loads(path.read_text(encoding='utf-8'))

args.out.mkdir(parents=True,exist_ok=False)
root=args.workspace/'references/analysis/F2_line_motion_v1'
observed=load(root/'observe2/report.json');audit=load(root/'audit1/report.json')
assert audit['result']=='F2_initial_AM_failure_and_all90_local_frequency_observations_independently_replayed'
assert sha(root/'observe2/report.json')==audit['observe2_report_sha256']
rows=observed['observations'];centers=np.array([sum(x['source_seconds'])/2 for x in rows])
fig,axes=plt.subplots(3,1,figsize=(10,8),layout='constrained')
for j,n in enumerate((2,3,5)):
    y=np.array([x['exploratory_group']['anchor_divided_frequencies_Hz'][j][0] for x in rows])
    eligible=np.array([x['all_anchor_roots_resolved'] for x in rows])
    axes[0].plot(centers[eligible],y[eligible],'o',label='resolved family line / '+str(n))
    axes[0].plot(centers[~eligible],y[~eligible],'x',color='#a0a0a0')
axes[0].set(title='F2 local acoustic family: 3 complete rows; grey crosses are NOT qualified',ylabel='Family coordinate / Hz')
axes[0].legend(fontsize=8)
for j in range(3):
    y=np.array([x['exploratory_group']['leave_one_out_base_error_Hz'][j][0] for x in rows])
    axes[1].plot(centers[eligible],y[eligible],'o',label='anchor '+str(j+1))
axes[1].plot(centers[eligible],np.array([x['exploratory_group']['heldout_order1_error_Hz'][0] for x in rows])[eligible],'x',label='withheld37/38Hz')
axes[1].set(ylabel='Prediction mismatch / Hz');axes[1].legend(fontsize=8)
extra=np.array([x['exploratory_group']['extra_11_over_5_error_Hz'][0] for x in rows])
extra_ok=np.array([x['all_anchor_roots_resolved'] and x['measured']['root_resolved'][3][0] for x in rows])
axes[2].plot(centers[extra_ok],extra[extra_ok],'o',label='both roots resolved')
axes[2].plot(centers[~extra_ok],extra[~extra_ok],'x',color='#a0a0a0',label='raw/unqualified comparison')
axes[2].set(xlabel='Original source time / s',ylabel='Extra-line mismatch / Hz');axes[2].legend(fontsize=8)
fig.savefig(args.out/'F2_line_motion_review.png',dpi=150);plt.close(fig)
target=args.out/'exact_sources/tools';target.mkdir(parents=True)
shutil.copy2(__file__,target/Path(__file__).name)
report=dict(schema='vsl.F2-line-motion-publication/1',result='audited_local_line_observations_published_with_unresolved_rows_explicit',
    sources={'tools/'+Path(__file__).name:sha(Path(__file__))},
    input_report_sha256=sha(root/'observe2/report.json'),audit_report_sha256=sha(root/'audit1/report.json'),
    plot_sha256=sha(args.out/'F2_line_motion_review.png'),complete_anchor_rows=3,total_rows=9,
    raw_unqualified_plot=root.joinpath('observe2/F2_line_motion.png').relative_to(args.workspace).as_posix(),
    raw_plot_not_used_for_qualification=True,audio_read=False,model_exported=False,runtime_changed=False)
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report),flush=True)
