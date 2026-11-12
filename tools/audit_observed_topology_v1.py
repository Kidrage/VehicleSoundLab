"""Reconstruct the strict-input pipeline using exactly equivalent executed fits."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--validation',type=Path,required=True)
parser.add_argument('--observations',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from aperture_model_v1.checks import assess
from aperture_model_v1.fit import Model
from aperture_model_v1.forward import real_rows
from minority_phase_v1.model import MinorityModel
from observed_topology_v1.inputs import numerical_inputs,DISCOVERY_KEYS
from observed_topology_v1.discover import discover
from observed_topology_v1.fixtures import make
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.observed-topology-audit/1',result='running',sources={},cases=[],
    real_audio_read=False,optimizer_rerun=False,real_source_permitted=False)
try:
    validation=load(args.validation/'report.json')
    observation=load(args.observations/'report.json')
    assert validation['result'] in ('passed','rejected') and observation['result']=='observed'
    report['validation_report_sha256']=sha(args.validation/'report.json')
    report['observation_report_sha256']=sha(args.observations/'report.json')
    for name,digest in validation['sources'].items():
        assert sha(repo/name)==sha(args.validation/'exact_sources'/name)==digest
    for name,digest in observation['sources'].items():
        assert sha(repo/name)==sha(args.observations/'exact_sources'/name)==digest
    first_observation=args.workspace/'references/analysis/observed_topology_v1/observe1'
    first_report=load(first_observation/'report.json')
    old_source=first_observation/'exact_sources/tools/observed_topology_v1/discover.py'
    assert sha(old_source)==first_report['sources']['tools/observed_topology_v1/discover.py']
    report['initial_observation_report_sha256']=sha(first_observation/'report.json')
    old_tree=ast.parse(old_source.read_text(encoding='utf-8'))
    new_tree=ast.parse((repo/'tools/observed_topology_v1/discover.py').read_text(encoding='utf-8'))
    old_function=next(node for node in old_tree.body if isinstance(node,ast.FunctionDef))
    new_function=next(node for node in new_tree.body if isinstance(node,ast.FunctionDef))
    assert isinstance(new_function.body[0],ast.If)
    assert [ast.dump(node) for node in old_function.body]==[ast.dump(node) for node in new_function.body[1:]]
    accessed={node.slice.value for node in ast.walk(old_function) if isinstance(node,ast.Subscript)
        and isinstance(node.value,ast.Name) and node.value.id=='settings' and isinstance(node.slice,ast.Constant)}
    assert accessed==set(DISCOVERY_KEYS)
    report['input_boundary']=dict(original_catalog_metadata_unread=True,strict_whitelist_now_enforced=True,
        discovery_numerical_body_AST_identical=True,current_callers_source_exact=True)
    settings=load(repo/'research/observed_topology_v1_plan.json')
    base=load(repo/settings['base_plan'])
    variant=load(repo/settings['minority_plan'])
    geometry,discovery_settings=numerical_inputs(base,settings)
    save(args.out/'numerical_inputs.json',dict(geometry=geometry,settings=discovery_settings))
    try:
        discover(np.zeros((5120,2)),np.arange(5120)/128,geometry,{**discovery_settings,'source_orders':[5]})
    except ValueError as exc:
        assert 'numerical input' in str(exc)
        report['input_boundary']['unexpected_truth_field_rejected']=True
    else:
        raise AssertionError('Unexpected source truth admitted')
    sources={Path(__file__)}|{repo/name for name in validation['sources']}|{repo/name for name in observation['sources']}
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    for item in validation['cases']:
        case=item['case']
        name=case['id']
        time,audio,truth,_=make(case,base)
        assert hashlib.sha256(audio.tobytes()).hexdigest()==item['fixture_audio_sha256']
        orders,evidence=discover(audio,time,geometry,discovery_settings)
        observed=next(row for row in observation['cases'] if row['case']==case)
        assert evidence==observed['evidence']==item['topology']
        effective={**geometry,'source_orders':orders}
        assert effective==load(args.validation/name/'effective_plan.json')
        assert sha(args.validation/name/'effective_plan.json')==item['effective_plan_sha256']
        row=dict(id=name,effective_inputs_exact=True,inferred_orders=orders,passed=item['passed'],
            observation_supported=item['observation_supported'],status=item['status'])
        if item['status']=='topology_rejected':
            assert len(orders)<variant['minimum_remaining_carriers'] and case.get('negative')
        else:
            path=args.validation/name/'fit.npz'
            saved=np.load(path)
            assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
            model=MinorityModel(time,effective,variant,item['fit']['selected_indices'])
            parameters=saved['parameters']
            _,phase,envelope=model.samples(parameters)
            assert np.array_equal(phase,saved['fitted_phase_correction'])
            target=real_rows(model.aperture.apply(audio[:,0]))
            residual=float(np.linalg.norm(model.prediction(parameters)-target)/max(np.linalg.norm(target),1e-30))
            assert residual==item['fit']['normalized_projection_residual']
            lower,upper=model.bounds(effective,variant)
            assert np.all(parameters>=lower) and np.all(parameters<=upper)
            assert len(model.selected)<=variant['maximum_departure_partials'] and envelope.min()>0
            amplitudes=np.hypot(parameters[:model.parts],parameters[model.parts:2*model.parts])
            remaining=sum(amplitudes[index]>=effective['rules']['minimum_carrier_amplitude']
                for index in range(model.parts) if index not in model.selected)
            minimum_step=float(np.min(np.diff(time+phase)))
            supported=bool(residual<=variant['maximum_normalized_projection_residual'] and
                remaining>=variant['minimum_remaining_carriers'] and envelope.min()>0 and minimum_step>0)
            assert supported==item['fit']['observation_supported']==item['observation_supported']
            assert minimum_step==item['minimum_coordinate_step']
            if item['status']=='observation_rejected':
                assert not supported and 'assessment' not in item
                assert not (path.parent/'coordinates.npz').exists()
                row.update(no_unsupported_remapping=True,minimum_coordinate_step=minimum_step)
            else:
                assert supported and item['status']=='measured'
                measurement={**effective,'heldout_orders':base['heldout_orders']}
                assessment,_,_=assess(audio,time,truth,phase,parameters,measurement)
                assert assessment==item['assessment']
            row.update(arrays_sha256=sha(path),phase_and_support_exact=True,
                remaining_carriers=item['fit']['remaining_carriers'],
                fitted_amplitudes=amplitudes.tolist())
        report['cases'].append(row)
    fig,axes=plt.subplots(1,3,figsize=(15,4.5))
    name='two_independent_partials'
    item=next(row for row in validation['cases'] if row['case']['id']==name)
    saved=np.load(args.validation/name/'fit.npz')
    effective=load(args.validation/name/'effective_plan.json')
    order=np.asarray(effective['source_orders'])
    evidence=item['topology']
    before=np.asarray(evidence['intervals'][0]['amplitudes'])
    col=[evidence['orders'].index(value) for value in order]
    after=np.hypot(saved['parameters'][:len(order)],saved['parameters'][len(order):2*len(order)])
    axes[0].plot(order,before[col],'o-',label='Constant-line discovery')
    axes[0].plot(order,after,'x-',label='After phase/departure fit')
    axes[0].axhline(evidence['threshold'],color='gray',linestyle='--',label='Discovery threshold')
    axes[0].axvline(6.8,color='gray',linewidth=.6)
    axes[0].set(xlabel='Candidate order',ylabel='Coefficient amplitude',title='Additional6.8 candidate is not a source identity')
    axes[0].legend(fontsize=7)
    time=saved['time']
    truth=saved['true_phase_correction']
    interior=(time>=5)&(time<35)
    for phase,label in ((Model(time,effective).samples(saved['baseline_parameters'])[1],'Before departures'),
                        (saved['fitted_phase_correction'],'After departures')):
        error=phase-truth
        error-=np.median(error[interior])
        axes[1].plot(time[interior],error[interior]*1e3,label=label)
    threshold=base['rules']['maximum_point_phase_p95_cycles']*1e3
    for sign in (-1,1):
        axes[1].axhline(sign*threshold,color='black',linestyle='--',linewidth=.6)
    axes[1].set(xlabel='Coarse-cycle coordinate',ylabel='Error (1e-3 cycles)',title='Common phase with measured15-line topology')
    axes[1].legend(fontsize=7)
    names=['unknown_six','unknown_eighteen','unknown_twenty_six','unknown_thirty_six']
    measured=[len(next(row for row in report['cases'] if row['id']==name)['inferred_orders']) for name in names]
    actual=[len(next(row for row in settings['added_cases'] if row['id']==name)['fixture_orders']) for name in names]
    indices=np.arange(len(names))
    axes[2].bar(indices-.18,actual,.36,label='Independent fixture truth')
    axes[2].bar(indices+.18,measured,.36,label='Discovered')
    axes[2].set_xticks(indices,['6','18','26','36'])
    axes[2].set(xlabel='Fixture line count',ylabel='Line count',title='Different active topologies on one declared grid')
    axes[2].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(args.out/'observed_topology.png',dpi=150)
    plt.close(fig)
    report.update(result='strict_input_pipeline_audited',passed_cases=sum(row['passed'] for row in report['cases']),
        total_cases=len(report['cases']),all_required_cases_passed=validation['result']=='passed',
        plot_sha256=sha(args.out/'observed_topology.png'),full33_and_HF_qualified=False)
    print(json.dumps(dict(result=report['result'],passed=report['passed_cases'],total=report['total_cases'],optimizer_rerun=False)),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
