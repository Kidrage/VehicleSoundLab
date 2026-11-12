"""Inspect executed fits and phase retention without fitting or reading recordings."""
import argparse
import ast
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--validation',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from aperture_model_v1.fit import Model
from minority_phase_v1.model import MinorityModel
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.minority-phase-audit/1',result='running',sources={},
    real_audio_read=False,estimator_rerun=False,real_source_permitted=False)
try:
    path=args.validation/'report.json'
    validation=json.loads(path.read_text(encoding='utf-8'))
    assert validation['result'] in ('passed','rejected')
    report['validation_report_sha256']=sha(path)
    for relative,digest in validation['sources'].items():
        source=repo/relative
        assert sha(source)==sha(args.validation/'exact_sources'/relative)==digest
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative]=digest
    target=args.out/'exact_sources/tools/audit_minority_phase_v1.py'
    shutil.copy2(Path(__file__),target)
    report['sources']['tools/audit_minority_phase_v1.py']=sha(Path(__file__))
    plan=json.loads((repo/'research/aperture_model_v1_plan.json').read_text(encoding='utf-8'))
    variant=json.loads((repo/'research/minority_phase_v1_plan.json').read_text(encoding='utf-8'))
    # The estimator sees neither case labels/truth nor the unfitted10/15 lines.
    for name in ('fit.py','model.py','selection.py'):
        tree=ast.parse((repo/'tools/minority_phase_v1'/name).read_text(encoding='utf-8'))
        keys=[node.slice.value for node in ast.walk(tree) if isinstance(node,ast.Subscript)
              and isinstance(node.slice,ast.Constant) and isinstance(node.slice.value,str)]
        assert not set(keys)&{'cases','case','truth','heldout_orders','contaminated_order','independent_orders','independent_all'}
    assert plan['observed_order_range'][1]<min(plan['heldout_orders'])
    report['selection_input_audit']=dict(no_case_truth_or_heldout_access=True,
        heldout_outside_estimation_band=True,known_topology_still_required=True)
    report['cases']=[]
    for item in validation['cases']:
        name=item['case']['id']
        array_path=args.validation/name/'fit.npz'
        saved=np.load(array_path)
        time=saved['time']
        model=MinorityModel(time,plan,variant,item['fit']['selected_indices'])
        actual=model.samples(saved['parameters'])[1]
        assert np.array_equal(actual,saved['fitted_phase_correction'])
        if not model.selected:
            assert np.array_equal(saved['parameters'],saved['baseline_parameters'])
        assert len(model.selected)<=variant['maximum_departure_partials']
        departures=[]
        for position,index in enumerate(model.selected):
            start=model.base_count+position*model.departure_count
            controls=saved['parameters'][start:start+model.departure_count]
            assert max(abs(controls))<=variant['departure_control_bound_radians']
            motion=model.departure_basis@controls
            departures.append(dict(order=float(model.orders[index]),maximum_control=float(max(abs(controls))),
                peak_to_peak_radians=float(np.ptp(motion))))
        report['cases'].append(dict(id=name,arrays_sha256=sha(array_path),phase_exact=True,
            no_departure_baseline_exact=not model.selected,departures=departures,
            observation_supported=item['fit']['observation_supported'],passed=item['passed']))
    fig,axes=plt.subplots(2,2,figsize=(12,7))
    for row,name in enumerate(('independent_phase_5','two_independent_partials')):
        item=next(item for item in validation['cases'] if item['case']['id']==name)
        saved=np.load(args.validation/name/'fit.npz')
        time=saved['time']
        truth=saved['true_phase_correction']
        interior=(time>=5)&(time<35)
        base=Model(time,plan).samples(saved['baseline_parameters'])[1]
        fitted=saved['fitted_phase_correction']
        for phase,label in ((base,'Original shared phase'),(fitted,'Restricted minority')):
            delta=phase-truth
            delta-=np.median(delta[interior])
            axes[row,0].plot(time[interior],delta[interior]*1e3,label=label)
        threshold=plan['rules']['maximum_point_phase_p95_cycles']*1e3
        for sign in (-1,1):
            axes[row,0].axhline(sign*threshold,color='black',linestyle='--',linewidth=.6)
        axes[row,0].set_title(name+' : common phase error')
        axes[row,0].set_ylabel('Error (1e-3 coarse cycles)')
        axes[row,0].legend(fontsize=8)
        model=MinorityModel(time,plan,variant,item['fit']['selected_indices'])
        for position,index in enumerate(model.selected):
            start=model.base_count+position*model.departure_count
            motion=model.departure_basis@saved['parameters'][start:start+model.departure_count]
            motion-=np.median(motion[interior])
            axes[row,1].plot(time[interior],motion[interior],label='Selected order '+str(model.orders[index]))
        axes[row,1].set_title('Independent phase retained separately')
        axes[row,1].set_ylabel('Partial phase (radians, origin aligned)')
        axes[row,1].legend(fontsize=8)
    for ax in axes.flat:
        ax.set_xlim(5,35)
        ax.set_xlabel('Coarse-cycle coordinate')
    fig.tight_layout()
    fig.savefig(args.out/'minority_phase.png',dpi=150)
    plt.close(fig)
    report.update(result='audited_no_fit_rerun',plot_sha256=sha(args.out/'minority_phase.png'),
        numerical_controls_passed=validation['result']=='passed',full33_and_HF_qualified=False)
    print(json.dumps(dict(result=report['result'],cases=len(report['cases']),
        source_exported=False,numerical_controls_passed=report['numerical_controls_passed'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
