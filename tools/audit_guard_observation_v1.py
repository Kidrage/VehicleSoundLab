"""Reconstruct actual dense candidates and boundary evidence without nonlinear refits."""
import argparse
from contextlib import nullcontext
import hashlib
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
from aperture_model_v1.checks import assess
from aperture_model_v1.forward import real_rows
from minority_phase_v1.model import MinorityModel
from observed_topology_v1.fixtures import make
from smooth_envelope_v1.penalty import build
from guard_observation_v1.checks import controls
from guard_observation_v1.geometry import extend
from envelope_resolution_v1.refine import geometry,transfer
try:
    from threadpoolctl import threadpool_limits
    limit=lambda:threadpool_limits(limits=2)
except ImportError:
    limit=nullcontext


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.guard-observation-audit/1',result='running',sources={},cases=[],
    nonlinear_estimator_rerun=False,real_audio_read=False,real_source_permitted=False)
try:
    guarded=args.workspace/'references/analysis/guard_observation_v1'
    smoothed=args.workspace/'references/analysis/smooth_envelope_v1'
    folders=[smoothed/'dense1',smoothed/'sure1',guarded/'dense1',guarded/'combined1']
    reports=[load(folder/'report.json') for folder in folders]
    assert all(row['result'] in ('dense_diagnostic_rejected','dense_diagnostic_passed_not_full_qualification') for row in reports)
    sources={Path(__file__)}|{repo/name for row in reports for name in row['sources']}
    for folder,row in zip(folders,reports):
        for relative,digest in row['sources'].items():
            assert sha(repo/relative)==sha(folder/'exact_sources'/relative)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    settings=load(repo/'research/guard_observation_v1_plan.json')
    resolution=load(repo/settings['parent_plan'])
    topology=load(repo/resolution['parent_plan'])
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    roughness=load(repo/'research/smooth_envelope_v1_plan.json')
    case=next(row for row in topology['added_cases'] if row['id']==settings['diagnostic_case'])
    time,audio,truth,_=make(case,base)
    audio_hash=hashlib.sha256(audio.tobytes()).hexdigest()
    original=args.workspace/'references/analysis/observed_topology_v1/validate2'
    old=next(row for row in load(original/'report.json')['cases'] if row['case']==case)
    assert old['fixture_audio_sha256']==audio_hash
    rows_for_plot=[]
    with limit():
        report['boundary_control']=controls(base)
        for folder,stored in zip(folders,reports):
            effective=load(folder/'effective_plan.json')
            saved=np.load(folder/'fit.npz')
            parameters=saved['parameters']
            initial=saved['initial_parameters']
            selected=stored['fit']['selected_indices']
            model=MinorityModel(time,effective,variant,selected)
            _,phase,envelope=model.samples(parameters)
            assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
            assert np.array_equal(phase,saved['phase_correction'])
            lower,upper=model.bounds(effective,variant)
            assert np.all(parameters>=lower) and np.all(parameters<=upper)
            target=real_rows(model.aperture.apply(audio[:,0]))
            residual=model.prediction(parameters)-target
            normalized=float(np.linalg.norm(residual)/max(np.linalg.norm(target),1e-30))
            assert normalized==stored['fit']['normalized_projection_residual']
            assert float(envelope.min())==stored['fit']['minimum_envelope']
            assert float(envelope.max())==stored['fit']['maximum_envelope']
            assert stored['fit']['observation_supported']
            assessment,_,_=assess(audio,time,truth,phase,parameters,{**effective,'heldout_orders':base['heldout_orders']})
            assert assessment==stored['assessment']
            item=dict(path=folder.relative_to(args.workspace).as_posix(),report_sha256=sha(folder/'report.json'),
                phase_p95_cycles=assessment['point_phase_p95_cycles'],qualified=assessment['qualified'],
                phase_and_residual_exact=True,original_bounds_preserved=True,assessment_exact=True)
            if (folder/'prior.npz').exists():
                matrix=np.load(folder/'prior.npz')['matrix']
                original_prior,evidence=build(model,initial,target,effective,roughness)
                proxy=evidence['projection_residual_scale_proxy']
                selection=load(folder/'selection.json')
                expected=np.sqrt(selection['weight'])*original_prior/proxy
                assert np.allclose(matrix,expected,rtol=1e-14,atol=0)
                first=2*model.parts+model.phase_count
                assert np.all(matrix[:,:first]==0) and np.all(matrix[:,model.base_count:]==0)
                assert float(np.linalg.norm(matrix@parameters))==stored['fit']['final_prior_norm']
                item['amplitude_only_prior_and_weight_exact']=True
            if folder==guarded/'dense1':
                previous=load(original/case['id']/'effective_plan.json')
                refined,_=geometry(previous)
                predicted,_=extend(refined)
                assert predicted==effective
                parent_saved=np.load(original/case['id']/'fit.npz')
                predicted_initial,_=transfer(time,previous,effective,variant,selected,parent_saved['parameters'],
                    resolution['minimum_envelope_transfer_accuracy'])
                assert np.array_equal(initial,predicted_initial)
                item['observed_geometry_and_nested_initial_exact']=True
            report['cases'].append(item)
            rows_for_plot.append((folder.parent.name+'/'+folder.name,phase.copy()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True,sharey=True)
    interior=(time>=5)&(time<35)
    threshold=base['rules']['maximum_point_phase_p95_cycles']
    for axis,(label,phase) in zip(axes.ravel(),rows_for_plot):
        error=phase-truth
        error-=np.median(error[interior])
        axis.plot(time[interior],error[interior])
        for sign in (-1,1):
            axis.axhline(sign*threshold,color='black',linestyle='--',linewidth=.6)
        axis.set(title=label,xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)')
    fig.tight_layout()
    fig.savefig(args.out/'candidate_audit.png',dpi=150)
    plt.close(fig)
    report.update(result='reconstructed_dense_candidates_not_full_qualification',
        fixture_audio_sha256=audio_hash,plot_sha256=sha(args.out/'candidate_audit.png'),
        full17_qualified=False,full33_replaced=False,individual14kHz_demonstrated=False)
    print(json.dumps(dict(result=report['result'],cases=[dict(path=row['path'],phase=row['phase_p95_cycles'],qualified=row['qualified']) for row in report['cases']])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
