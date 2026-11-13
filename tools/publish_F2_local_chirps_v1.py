"""Review known interference correction and bounded real frequency observations."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha

def load(path):return json.loads(path.read_text(encoding='utf-8'))

args.out.mkdir(parents=True,exist_ok=False)
root=args.workspace/'references/analysis/F2_local_chirps_v1'
actual=load(root/'observe1/report.json');audit=load(root/'audit1/report.json')
old=load(args.workspace/'references/analysis/F2_native_peaks_v1/observe2/report.json')
assert audit['actual_report_sha256']==sha(root/'observe1/report.json')
assert audit['result']=='native_peak_failures_and_all18_local_chirp_fits_independently_audited'
fig,axes=plt.subplots(4,1,figsize=(10,10),layout='constrained')
before=old['controls']['extended_chirp_rows'];after=actual['controls']['extended_chirp_rows']
times=[r['start_seconds']+.5 for r in before]
axes[0].semilogy(times,[r['max_frequency_error_Hz'] for r in before],'o',label='separate local centers')
axes[0].semilogy(times,[max(1e-12,r['max_frequency_error_Hz']) for r in after],'x',label='joint local chirps (floor1e-12 for display)')
axes[0].axhline(.01,color='#af4c35',linestyle='--',label='original0.01Hz gate')
axes[0].set(title='Known synthetic mixture only: local interference correction',xlabel='Synthetic time / s',ylabel='Max error / Hz')
axes[0].legend(fontsize=7)
rows=actual['observations'];centers=np.array([sum(r['source_seconds'])/2 for r in rows]);eligible=np.array([r['all_anchor_fits_eligible'] for r in rows])
for line,order in enumerate((2,3,5)):
    values=np.array([r['measured']['frequency_Hz'][line][0]/order for r in rows])
    axes[1].plot(centers[eligible],values[eligible],'o',label='line / '+str(order))
    axes[1].plot(centers[~eligible],values[~eligible],'x',color='#999999')
axes[1].set(title='Real F2: 5 rows within local model bounds; grey4 rows are excluded',ylabel='Family coordinate / Hz')
axes[1].legend(fontsize=7)
for line in range(3):
    values=np.array([r['measured']['chirp_Hz_per_second'][line][0] for r in rows])
    bounded=np.array([r['measured']['local_chirp_fit'][0]['at_bound'][line] for r in rows])
    axes[2].plot(centers,values,'o',label='line '+str(line+1))
    axes[2].plot(centers[bounded],values[bounded],'x',color='#c73f3b',markersize=9)
axes[2].axhline(2,color='#c73f3b',linestyle='--');axes[2].axhline(-2,color='#c73f3b',linestyle='--')
axes[2].set(ylabel='Local chirp / Hz/s',title='Red crosses mark explicit local-model bounds');axes[2].legend(fontsize=7)
axes[3].plot(centers,[r['original_nominal_Hz'][4] for r in rows],'x',label='prior37/38Hz bin')
axes[3].plot(centers,[r['measured']['selected_native_bin_Hz'][4][0] for r in rows],'o',label='strongest peak in that observation cell')
axes[3].set(title='Cell label does not preserve component identity: one window selects45Hz',ylabel='Selected native bin / Hz',xlabel='Original F2 time / s')
axes[3].legend(fontsize=7)
fig.savefig(args.out/'F2_joint_local_chirps.png',dpi=150);plt.close(fig)
target=args.out/'exact_sources/tools';target.mkdir(parents=True);shutil.copy2(__file__,target/Path(__file__).name)
report=dict(schema='vsl.F2-local-chirps-review/1',result='audited_known_interference_and_real_model_limits_published',
    sources={'tools/'+Path(__file__).name:sha(Path(__file__))},input_report_sha256=sha(root/'observe1/report.json'),
    audit_report_sha256=sha(root/'audit1/report.json'),plot_sha256=sha(args.out/'F2_joint_local_chirps.png'),
    audio_read=False,model_exported=False,runtime_changed=False,
    limits='Bounded local fits and cell winners are not a continuous physical/source phase model or idle timbre acceptance')
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report),flush=True)
