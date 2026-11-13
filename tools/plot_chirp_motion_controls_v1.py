"""Plot the whole declared mechanism study, including truth and noise failures."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
report=load(a.input/'report.json')
audit=load(a.audit/'report.json')
assert audit['result']=='all60_known_native_signals_inventories_observed_initials_fits_truth_connections_verified'
assert sha(a.input/'report.json')==audit['input_report_sha256']
a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_plot.py')
plan=report['plan']
fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
t=np.linspace(0,3,1801)
for position,case in enumerate(plan['cases']):
    ax=axes.flat[position]
    rows=load(a.input/case/'fits.json')
    truth=load(a.input/case/'truth.json')
    if truth['rows']:
        for k,base in enumerate(plan['base_hz'][:6]):
            moving=plan['moving'][k]
            dev=base/plan['FM']['reference_hz']*plan['FM']['deviation_at_reference_hz']*moving*(case in ['fm_only','am_fm'])
            f=base*(1+.05*t*moving)+dev*np.sin(2*np.pi*plan['FM']['modulation_hz']*t)
            ax.plot(t,f,color='C'+str(k),lw=1,alpha=.75)
            pairs=[v for v in truth['pairs'] if v['component']==k and v.get('nearest_is_unique')]
            for pair in pairs:
                line=rows[pair['window']]['lines'][pair['fitted_line']]
                ax.scatter((pair['window']+.5)*.25,line['frequency_hz'],s=13,
                    color='C'+str(k),marker='o' if pair['eligible'] else 'x')
        failures=[v for v in truth['inequalities'] if v['component']==5 and not v['same_component_passes']]
        for edge in failures:
            ax.axvline((edge['current_window']+.0)*.25,color='red',lw=.6,alpha=.35)
        item=next(v for v in audit['true_components'] if v['case']==case)
        spans=[v['longest_exact_track'] for v in item['components'] if v['moving'] and v['base_hz']<200]
        ax.set_title(case+' / moving low longest exact tracks '+','.join(map(str,spans)),fontsize=10)
        ax.set_ylim(25,215)
    else:
        for i,row in enumerate(rows):
            if not row['success']:ax.axvspan(i*.25,(i+1)*.25,color='red',alpha=.1)
            for line in row['lines']:
                ax.scatter((i+.5)*.25,line['frequency_hz'],color='C0' if line['eligible'] else '.65',
                    marker='o' if line['eligible'] else 'x',s=22)
        ax.set_title('Band-limited mono noise / 9 eligible lines, no track >=5',fontsize=10)
        ax.set_ylim(25,215)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Frequency (Hz)')
    ax.grid(alpha=.2)
ax=axes.flat[5]
truth=load(a.input/'fm_only/truth.json')
edges=[v for v in truth['inequalities'] if v['component']==5]
tt=[v['current_window']*.25 for v in edges]
ax.plot(tt,[max(abs(v['forward_error_hz']),abs(v['backward_error_hz']))/.5 for v in edges],'.-',label='Exact prediction error / original 0.5Hz')
ax.plot(tt,[abs(v['chirp_difference'])/8 for v in edges],'.-',label='Exact rate difference / original 8Hz/s')
ax.axhline(1,color='red',ls='--',label='Original limit')
ax.set_title('Continuous 179.3Hz component / exact parameters',fontsize=10)
ax.set_xlabel('Boundary time (s)')
ax.set_ylabel('Ratio to original connection limit')
ax.grid(alpha=.2)
ax.legend(fontsize=8)
fig.suptitle('Known controls on the current native acceleration path; no real recording\nCurves: exact continuous frequency; dots: eligible fit; crosses: rejected; red cuts: exact 179.3Hz rule failures; all cases retained',fontsize=11)
fig.savefig(a.out/'mechanisms.png',dpi=150)
plt.close(fig)
save(a.out/'report.json',dict(result='all5_cases_and_exact_connection_failures_plotted',input_report_sha256=sha(a.input/'report.json'),
    audit_report_sha256=sha(a.audit/'report.json'),images={'mechanisms.png':sha(a.out/'mechanisms.png')}))
