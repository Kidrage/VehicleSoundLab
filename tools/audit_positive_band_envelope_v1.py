"""Rebuild the saved finite-band candidate and its full-period amplitude certificate."""
import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--diagnosis',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from aperture_model_v1.checks import assess
from aperture_model_v1.forward import real_rows
from observed_topology_v1.fixtures import make
from positive_band_envelope_v1.model import BandModel
from positive_band_envelope_v1.basis import basis
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
report=dict(schema='vsl.positive-band-envelope-audit/1',result='running',sources={},
    nonlinear_estimator_rerun=False,real_audio_read=False,real_source_permitted=False)
try:
    parent=load(args.diagnosis/'report.json')
    assert parent['result'] in ('dense_diagnostic_rejected','dense_diagnostic_passed_not_full_qualification')
    report['diagnosis_report_sha256']=sha(args.diagnosis/'report.json')
    sources={Path(__file__)}|{repo/name for name in parent['sources']}
    for name,digest in parent['sources'].items():
        assert sha(repo/name)==sha(args.diagnosis/'exact_sources'/name)==digest
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    settings=load(repo/'research/positive_band_envelope_v1_plan.json')
    guard=load(repo/settings['parent_plan'])
    resolution=load(repo/guard['parent_plan'])
    topology=load(repo/resolution['parent_plan'])
    base=load(repo/topology['base_plan'])
    variant=load(repo/topology['minority_plan'])
    case=next(row for row in topology['added_cases'] if row['id']==settings['diagnostic_case'])
    time,audio,truth,_=make(case,base)
    effective=load(args.diagnosis/'effective_plan.json')
    assert effective['rules']==base['rules']
    saved=np.load(args.diagnosis/'fit.npz')
    parameters=saved['parameters']
    with limit():
        model=BandModel(time,effective,variant,parent['fit']['selected_indices'])
        _,phase,envelope=model.samples(parameters)
        assert np.array_equal(phase,saved['phase_correction'])
        assert np.array_equal(time,saved['time']) and np.array_equal(truth,saved['true_phase_correction'])
        lower,upper=model.bounds(effective,variant)
        assert np.all(parameters>=lower) and np.all(parameters<=upper)
        target=real_rows(model.aperture.apply(audio[:,0]))
        normalized=float(np.linalg.norm(model.prediction(parameters)-target)/max(np.linalg.norm(target),1e-30))
        assert normalized==parent['fit']['normalized_projection_residual']
        assert float(envelope.min())==parent['fit']['minimum_envelope']
        assert float(envelope.max())==parent['fit']['maximum_envelope']
        assert parent['fit']['observation_supported']
        assessment,_,_=assess(audio,time,truth,phase,parameters,{**effective,'heldout_orders':base['heldout_orders']})
        assert assessment==parent['assessment']
        period=model.band_evidence['period_coarse_cycles']
        full_time=np.arange(round(period*effective['samples_per_cycle']))/effective['samples_per_cycle']
        full,evidence=basis(full_time,effective['cycles'],model.orders)
        first=2*model.parts+model.phase_count
        beta=parameters[first:model.base_count].reshape(model.parts,model.envelope_count)
        full_envelope=1+full@beta.T
        power=abs(np.fft.rfft(full_envelope,axis=0))**2
        outside=power[evidence['degree']+1:].sum(axis=0)/power.sum(axis=0)
        assert max(outside)<1e-24
        assert full_envelope.min()>=1-effective['amplitude_control_bound']-1e-12
        assert full_envelope.max()<=1+effective['amplitude_control_bound']+1e-12
    np.savez_compressed(args.out/'certificate.npz',full_time=full_time,full_envelopes=full_envelope,
        outside_band_fraction=outside,phase_correction=phase)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(10,7))
    interior=(time>=5)&(time<35)
    error=phase-truth
    error-=np.median(error[interior])
    axes[0].plot(time[interior],error[interior])
    for sign in (-1,1):
        axes[0].axhline(sign*base['rules']['maximum_point_phase_p95_cycles'],color='black',linestyle='--',linewidth=.6)
    axes[0].set(xlabel='Coarse-cycle coordinate',ylabel='Phase error (cycles)')
    for index in (0,model.parts//2,model.parts-1):
        axes[1].plot(full_time,full_envelope[:,index],label=f'Measured candidate {model.orders[index]:g}')
    axes[1].set(xlabel='Amplitude basis full period (coarse cycles)',ylabel='Real envelope',ylim=(.74,1.26))
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(args.out/'band_certificate.png',dpi=150)
    plt.close(fig)
    report.update(result='reconstructed_band_candidate_not_full_qualification',assessment=assessment,
        bounds_preserved=True,phase_and_projection_residual_exact=True,original_rules_exact=True,
        literal_outside_band_maximum_fraction=float(max(outside)),
        full_period_minimum_envelope=float(full_envelope.min()),full_period_maximum_envelope=float(full_envelope.max()),
        band=evidence,fixture_audio_sha256=hashlib.sha256(audio.tobytes()).hexdigest(),
        plot_sha256=sha(args.out/'band_certificate.png'),full17_qualified=False,full33_replaced=False)
    print(json.dumps(dict(result=report['result'],phase=assessment['point_phase_p95_cycles'],
        qualified=assessment['qualified'],outside_band=report['literal_outside_band_maximum_fraction'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
