"""Read-only fitted trajectories and conditional parameter errors."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','observation','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_plot.py')
report=load(a.observation/'report.json');fig,axes=plt.subplots(3,3,figsize=(14,10),layout='constrained')
for col,summary in enumerate(report['observations']):
    name=summary['segment'];rows=load(a.observation/name/'fits.json');pred=load(a.observation/name/'predictions.json')
    refs=sorted({line['reference_index'] for row in rows for line in row['lines']})
    for k in refs:
        found=[(row,line) for row in rows for line in row['lines'] if line['reference_index']==k and line['eligible']]
        times=[(row['tile']+.5)*.25 for row,line in found]
        axes[0,col].scatter(times,[line['frequency_hz'] for row,line in found],s=5)
        axes[1,col].scatter(times,[line['chirp_hz_per_second'] for row,line in found],s=5)
    for row in rows:
        if not row['success']:
            for ax in axes[:2,col]:ax.axvspan(row['tile']*.25,(row['tile']+1)*.25,color='red',alpha=.08)
    for ax in axes[:2,col]:ax.axvline(len(rows)*.125,color='black',ls=':',lw=1)
    axes[0,col].set(title=name,ylabel='Locally eligible center f (Hz)',xlabel='Local time (s)')
    axes[1,col].set(ylabel='Independent local chirp (Hz/s)',xlabel='Local time (s)')
    used=[row for row in pred if row['status']=='compared']
    axes[2,col].scatter([row['maximum_frequency_error_hz'] for row in used],
        [row['median_absolute_amplitude_error_db'] for row in used],c=['C0' if row['diagnostic_target_met'] else 'C3' for row in used])
    axes[2,col].axvline(4,color='.5',ls=':');axes[2,col].axhline(3,color='.5',ls=':')
    axes[2,col].set(xlabel='Maximum check f error (Hz)',ylabel='Median absolute amplitude error (dB)',title=f"{summary['diagnostic_targets_met']}/{summary['compared']} both targets; not a timbre gate")
fig.suptitle('F3 native independent chirps: red tiles = optimizer failure; dotted time = train/check split\nCheck ratios are observed acoustic coordinates; no phase forecast, actual RPM or engine-source identification',fontsize=11)
fig.savefig(a.out/'F3_chirp_parameters.png',dpi=140);plt.close(fig)
save(a.out/'report.json',dict(result='read_only_parameter_plot_generated',observation_report_sha256=sha(a.observation/'report.json'),
    image_sha256=sha(a.out/'F3_chirp_parameters.png')))
