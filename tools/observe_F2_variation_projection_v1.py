"""Observe both fixed scaling hypotheses on all12 frozen three-line F2 overlap groups."""
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
from drive_evidence_v1.sources import read,sha
from line_motion_v1.variation_projection import frequency_disagreement,observe
from line_motion_v1.variation_projection_controls import controls


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-variation-projection/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False,real_nonlinear_fits=0,shared_phase_clock_fit=False)
try:
    for path in (Path(__file__),repo/'research/F2_variation_projection_v1_plan.json',repo/'references/segments_v1.json',
        repo/'tools/drive_evidence_v1/sources.py',*sorted((repo/'tools/line_motion_v1').glob('*.py'))):
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    report['controls']=controls();assert report['controls']['passed'],'Known contracts/fit numerics failed; no recording read'
    root=args.workspace/'references/analysis/F2_overlap_phase_v1';parent_path=root/'observe2/report.json'
    parent=json.loads(parent_path.read_text(encoding='utf-8'));audit=json.loads((root/'audit1/report.json').read_text(encoding='utf-8'))
    assert audit['actual_report_sha256']==sha(parent_path)
    frozen=parent['sources']
    for module in ('local_precision.py','rate_coordinates.py','local_chirps.py','peaks.py'):
        path='tools/line_motion_v1/'+module;assert sha(repo/path)==frozen[path]
    ancestor=args.workspace/'references/analysis/F2_rate_coordinates_v1/observe1'
    assert parent['parent_report_sha256']==sha(ancestor/'report.json')
    arrays=np.load(ancestor/'observations.npz');assert parent['parent_arrays_sha256']==sha(ancestor/'observations.npz')
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==parent['provenance'] and np.array_equal(audio,arrays['audio'])
    rows=[];saved={k:[] for k in ('disagreement','harmonic_hypothesis','equal_Hz','harmonic_hypothesis_omitted','equal_Hz_omitted')}
    for pair in parent['observations']:
        time=np.arange(pair['first_sample'],pair['stop_sample'])/48000;channels=[];part={k:[] for k in saved}
        for ch,item in enumerate(pair['channels']):
            left=[x['new']['left'] for x in item['comparisons']];right=[x['new']['right'] for x in item['comparisons']]
            d=frequency_disagreement(left,right,time);result,models=observe(d)
            channels.append(dict(channel=ch,left=left,right=right,observations=result));part['disagreement'].append(d)
            for k,v in models.items():part[k].append(v)
        rows.append(dict(left_window=pair['left_window'],right_window=pair['right_window'],first_sample=pair['first_sample'],
            stop_sample=pair['stop_sample'],source_overlap_seconds=pair['source_overlap_seconds'],channels=channels))
        for k in saved:saved[k].append(np.stack(part[k],axis=1))
    np.savez_compressed(args.out/'projections.npz',**{k:np.stack(v) for k,v in saved.items()})
    report.update(result='all12_frozen_variation_projections_observed_NOT_physical_common_source_classification',
        provenance=provenance,parent_report_sha256=sha(parent_path),parent_audit_sha256=sha(root/'audit1/report.json'),
        ancestor_report_sha256=parent['parent_report_sha256'],ancestor_arrays_sha256=parent['parent_arrays_sha256'],
        observations=rows,arrays_sha256=sha(args.out/'projections.npz'),
        counts=dict(overlap_pairs=6,channels=2,three_line_observations=12,predeclared_hypotheses=2,samples_per_group=24000),
        physical_harmonic_orders_verified=False,phase_extracted_real_model_permitted=False,RPM_inferred=False,
        limits=['2/3/5 are a fixed exploratory scaling hypothesis, not verified physical orders or inferred RPM',
            'Projection residual fractions describe squared model disagreement, not separated source energy',
            'Conditional omitted-line comparison shares parent joint fits and samples; not independent heldout validation',
            'Common curvature and independent proportional programs can have the same signature; no physical classifier or clock export'])
    print(json.dumps(dict(result=report['result'],known=[dict(id=x['id'],fractions={k:v['residual_squared_fraction'] for k,v in x['observations'].items()}) for x in report['controls']['cases']],
        rows=[dict(pair=[x['left_window'],x['right_window']],fractions={k:v['residual_squared_fraction'] for k,v in x['channels'][0]['observations'].items()},
            omitted_Hz=x['channels'][0]['observations']['harmonic_hypothesis']['omitted_line_prediction_rms_error_Hz']) for x in rows])),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
