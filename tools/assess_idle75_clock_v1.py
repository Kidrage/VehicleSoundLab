"""Explain known inverse rejection, without presenting it as real idle progress in sound."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');audit=load(a.audit/'report.json')
assert audit['result']=='failed_known_inverse_independently_confirmed' and audit['input_sha256']==sha(a.input/'report.json')
known=run['known']['inverse'];target=np.array(known['TRAIN_target']);prediction=np.array(known['TRAIN_prediction'])
fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
path=np.array([row['fraction'] for row in audit['profile']]);cost=np.array([row['scaled_cost'] for row in audit['profile']])
axes[0].plot(path,cost,'o-',color='#25858a',markersize=4)
axes[0].scatter([0],[cost[0]],color='#bd5345',zorder=4,label='Returned point')
axes[0].scatter([1],[cost[-1]],color='#48657b',zorder=4,label='Declared truth')
axes[0].set(title='Fixed line from returned parameters to truth',xlabel='Fraction along the declared line (no new fit)',ylabel='Scaled moment error squared');axes[0].legend(fontsize=8)
axes[1].bar(np.arange(2)-.16,known['parameters'],width=.32,label='Returned',color='#bd5345')
axes[1].bar(np.arange(2)+.16,run['known']['truth'],width=.32,label='Declared truth',color='#25858a')
axes[1].set_xticks(np.arange(2),['Clock factor','Strength']);axes[1].set_ylabel('Dimensionless parameter')
axes[1].set_title('Solver success / rank2; known recovery FAILED');axes[1].legend(fontsize=8)
for ax in axes:ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
fig.suptitle('Known control rejected before real-source fit; no new voice',fontsize=14)
figure=a.out/'evidence.png';fig.savefig(figure,dpi=150);plt.close(fig)
r=dict(result='failed_known_idle75_clock_assessed',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),
    known_returned=known['parameters'],known_truth=run['known']['truth'],known_parameter_error=audit['known_parameter_error'],
    optimizer_reported_success=known['success'],Jacobian_rank=known['rank'],Jacobian_condition=known['condition'],
    returned_scaled_cost=audit['returned_scaled_cost'],truth_scaled_cost=audit['truth_scaled_cost'],
    fixed21point_line_has_uphill_segment_from_returned=bool(cost[1]>cost[0]),
    maximum_fixed_line_cost=float(cost.max()),known_native_analytic_derivative_consistent=True,
    source_models_fitted=len(run['models']),new_audio=False,
    figure=dict(file=figure.name,sha256=sha(figure)),
    next='Qualify expected-ensemble moment fitting through original observation; retain short stochastic takes for validation. Do not rescue this inverse with true start/more seeds/bounds/iterations or present solver success as sound acceptance.')
save(a.out/'report.json',r);print(r)
