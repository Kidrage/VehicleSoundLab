"""Observe fixed harmonic-relation hypotheses without selecting a fundamental or fitting PCM."""
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
from drive_evidence_v1.sources import sha
from period_relation_v1.intervals import compatible
from period_relation_v1.checks import controls


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-period-relation/1',result='running',sources={},real_audio_read=False,
    real_recording_observations_read=True,phase_estimator_run=False,model_exported=False,runtime_changed=False)
try:
    plan=load(repo/'research/F2_period_relation_v1_plan.json')
    prior_path=args.workspace/'references/analysis/F2_idle_observation_v1/audit1/report.json'
    prior=load(prior_path)
    assert prior['result']=='reviewed_F_source_permissions_exact_clips_and_F2_Fourier_observations_independently_verified'
    assert prior['all7_source_clips_exact'] and not prior['phase_or_RPM_inferred']
    catalogue=load(args.workspace/'references/segments_v1.json')
    assert 'fixed_window_spectral_observation' in catalogue['segments']['F2_tailpipe']['allowed_uses']
    assert sha(repo/'references/segments_v1.json')==sha(args.workspace/'references/segments_v1.json')
    for path in (Path(__file__),repo/'research/F2_period_relation_v1_plan.json',repo/'references/segments_v1.json',
        repo/'tools/drive_evidence_v1/sources.py',*sorted((repo/'tools/period_relation_v1').glob('*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    checks=controls();assert checks['passed']
    rows=[]
    for row in prior['display_only_low_band_peaks']:
        frequencies=row['L_native1Hz_peak_bins_Hz'];assert len(frequencies)==5
        values={name:compatible(frequencies[:3],value['anchor_orders'],frequencies[3:],plan['bin_half_width_Hz'])
                for name,value in plan['hypotheses'].items()}
        rows.append(dict(source_seconds=row['source_seconds'],all5_observed_peak_bins_Hz=frequencies,
            first3_exploratory_anchors_Hz=frequencies[:3],retained_extra_peak_bins_Hz=frequencies[3:],hypotheses=values))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for axis,(name,hypothesis) in zip(axes,plan['hypotheses'].items()):
        scale=1 if name=='bank_pattern' else 5
        for index,row in enumerate(rows):
            value=row['hypotheses'][name]
            interval=value['anchor_interval_Hz']
            if interval:
                axis.plot([x*scale for x in interval],[index,index],color='#a5a5a5',linewidth=7)
            for branch in value['branches']:
                axis.plot([x*scale for x in branch['base_interval_Hz']],[index,index],color='#137a58',linewidth=3)
            if not value['branches'] and interval:
                axis.plot(sum(interval)*scale/2,index,'rx')
        axis.set(title=name+' (base x'+str(scale)+')',xlabel='Illustrative compatible base / Hz',
            yticks=range(3),yticklabels=[str(row['source_seconds'])+'s' for row in rows])
    figure.suptitle('Native-bin boxes only: grey=3 anchors, green=all5 lines, red=extra lines incompatible')
    figure.savefig(args.out/'F2_period_relations.png',dpi=150);plt.close(figure)
    report.update(result='F2_native_bin_relations_explored_no_fundamental_or_RPM_identified',controls=checks,cases=rows,
        prior_observation_report_sha256=sha(prior_path),all_five_peaks_retained=True,
        selected_fundamental=None,RPM_inferred=False,phase_extracted_real_model_permitted=False,
        plot_sha256=sha(args.out/'F2_period_relations.png'),
        limits=['Hypotheses chosen after viewing prior F2 bins, not independent validation or an automatic peak selector',
            'Half-bin boxes assume isolated stationary-tone rounding; they are not frequency confidence intervals for drifting mixed recordings',
            'Smaller subharmonics can always explain integer lines; compatibility does not identify physical engine period',
            'No clock trajectory, true RPM, physical source attribution, new DNA or changed original extraction gates'])
    print(json.dumps(dict(result=report['result'],cases=rows)),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
