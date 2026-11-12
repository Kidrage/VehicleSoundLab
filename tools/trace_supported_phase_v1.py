"""Trace fixed hierarchy stages of a declared analytic rapid case, no retries."""
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
from fractional_clock_v1.fixtures import make
from fractional_clock_v1.phase import refine_once
from exterior_clock_v1.warp import render_positions
from fractional_residue_v1.observations import aperture,residue_summary


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.supported-phase-trace/1',result='running',sources={},stages=[],
    real_source_evaluated=False,model_exported=False,runtime_modified=False)
try:
    prior_path=args.workspace/'references/analysis/supported_root_v1/rapid3/report.json'
    prior=json.loads(prior_path.read_text(encoding='utf-8'))
    frozen_plan=prior_path.parent/'exact_sources/research/supported_root_v1_plan.json'
    plan=json.loads(frozen_plan.read_text(encoding='utf-8'))
    assert prior['subset'] and prior['result']=='rejected' and len(prior['cases'])==1
    for name,digest in prior['sources'].items():
        assert sha(prior_path.parent/'exact_sources'/name)==digest
    sources=[Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/exterior_clock_v1/warp.py',
        repo/'tools/multicarrier_clock_v1/fixtures.py']
    sources+=list((repo/'tools/fractional_clock_v1').glob('*.py'))
    sources+=list((repo/'tools/fractional_residue_v1').glob('*.py'))
    for source in sources:
        name=source.relative_to(repo).as_posix()
        if name in prior['sources']:
            assert sha(source)==prior['sources'][name]
        target=args.out/'exact_sources'/source.relative_to(repo)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][source.relative_to(repo).as_posix()]=sha(source)
    shutil.copy2(frozen_plan,args.out/'replayed_plan.json')
    report['replayed_plan_sha256']=sha(frozen_plan)
    report['original_rapid3_report_sha256']=sha(prior_path)
    case=prior['cases'][0]['case']
    audio,time,truth,frequency=make(case,plan['seconds'])
    saved=prior_path.parent/case['id']/'initial_coordinates.npz'
    with np.load(saved,allow_pickle=False) as archive:
        positions=archive['source_seconds']
    cutoff=plan['coordinate']['source_lowpass_hz']
    normalized=render_positions(audio,0,positions,cutoff)
    report['initial_coordinates_sha256']=sha(saved)
    for index,orders in enumerate(plan['phase']['fit_order_stages']):
        local=dict(plan['phase'],fit_orders=orders)
        observed=aperture(normalized,positions,time,truth,plan['coordinate'],local)
        item=dict(stage=index+1,orders=orders,
            input_residue=residue_summary(positions,time,truth,frequency,plan['coordinate']['samples_per_coarse_cycle']),
            aperture=observed['rows'])
        np.savez_compressed(args.out/f'stage{index+1}_aperture.npz',**{key:value for key,value in observed.items() if key!='rows'})
        if index==0:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            figure,axis=plt.subplots(figsize=(11,5),layout='constrained')
            centered=observed['point_residual_cycles']-np.median(observed['point_residual_cycles'])
            axis.plot(observed['source_seconds'],centered,color='black',label='Known instantaneous phase residue',lw=2)
            for column,order in enumerate(orders):
                axis.plot(observed['source_seconds'],centered+observed['aperture_bias_cycles'][:,column],label=f'10-cycle window, order{order}')
            axis.set(xlim=(1.3,2.5),xlabel='Source seconds',ylabel='Coarse cycles',
                title='Supported coarse path: finite-window phase differs from instantaneous phase')
            axis.legend(fontsize=8)
            axis.grid(alpha=.2)
            figure.savefig(args.out/'aperture_point_mismatch.png',dpi=160)
            plt.close(figure)
            report['plot_sha256']=sha(args.out/'aperture_point_mismatch.png')
        try:
            normalized,positions,evidence=refine_once(audio,0,normalized,positions,cutoff,plan['coordinate'],local)
            cutoff=evidence['source_cutoff_hz']
            item.update(status='measured',evidence=evidence,
                output_residue=residue_summary(positions,time,truth,frequency,plan['coordinate']['samples_per_coarse_cycle']))
            np.savez_compressed(args.out/f'stage{index+1}_coordinates.npz',source_seconds=positions)
        except ValueError as exc:
            item.update(status='rejected',reason=str(exc))
            report['stages'].append(item)
            break
        report['stages'].append(item)
    assert report['stages'][-1]['status']=='rejected'
    report['result']='traced_rejection_no_algorithm_change'
    print(json.dumps(dict(result=report['result'],stages=[dict(stage=row['stage'],status=row['status']) for row in report['stages']])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
