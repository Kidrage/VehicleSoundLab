"""Post-fit diagnosis only: native versus augmented and known forecast errors."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},cases=[],all_conditional_tests=[],all_forecasts=[],
    truth_used_only_after_frozen_estimation=True,new_fits=False,real_source_read=False)
for name in ['tools/diagnose_candidate_presence_v1.py','tools/research_archive_v1.py']:
    dest=a.out/'exact_sources'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(repo/name,dest)
    r['sources'][name]=sha(repo/name)
try:
    source=load(a.input/'report.json')
    audit=load(a.audit/'report.json')
    assert audit['result']=='all108_native_augmented_waveforms_proposals_conditional_nulls_graphs_scores_verified'
    assert audit['input_report_sha256']==sha(a.input/'report.json') and audit['qualified'] is False
    for item in source['summaries']:
        case=item['case']
        folder=a.input/case
        native=load(folder/'native_fits.json')
        raw=load(folder/'raw_fits.json')
        rows=load(folder/'fits.json')
        props=load(folder/'proposals.json')
        tests=load(folder/'presence.json')
        scores=load(folder/'scores.json')
        truth=load(folder/'truth.json')['rows']
        result=dict(case=case,native_success=sum(v['success'] for v in native),
            augmented_success=sum(v['success'] for v in raw),
            native_failed_windows=[i for i,v in enumerate(native) if not v['success']],
            augmented_failed_windows=[i for i,v in enumerate(raw) if not v['success']],
            newly_failed_windows=[i for i,(u,v) in enumerate(zip(native,raw)) if u['success'] and not v['success']],
            newly_successful_windows=[i for i,(u,v) in enumerate(zip(native,raw)) if not u['success'] and v['success']],
            native_evaluations=[v.get('evaluations',0) for v in native],
            extra_evaluations=[v.get('evaluations',0) if prop['added_bins'] else 0 for v,prop in zip(raw,props)],
            low_correct_runs={key:[v['longest_correct_contiguous'] for v in value['components'][:6]] for key,value in scores.items()},
            rejected_added=[],accepted_added=[])
        assignments={(v['window'],v['index']):v['component'] for v in scores['augmented_boundary']['assignments']}
        for i,prop in enumerate(props):
            for forecast in prop['provenance']:
                identity=assignments.get((i-1,forecast['previous_line_index']))
                current=next((v for v in truth[i]['lines'] if v['index']==identity),None) if truth else None
                value=dict(case=case,window=i,**forecast,previous_scored_component=identity,
                    current_truth_visible=current['visible'] if current else None,
                    forecast_error_hz=forecast['predicted_frequency_hz']-current['frequency_hz'] if current else None,
                    added_native_bin_to_truth_hz=forecast['native_bin']*4-current['frequency_hz'] if current else None,
                    true_current_outside_original2Hz_box=abs(forecast['native_bin']*4-current['frequency_hz'])>2 if current else None,
                    posterior_diagnostic_only=True)
                r['all_forecasts'].append(value)
            for test in tests[i]['tests']:
                line=raw[i]['lines'][test['index']]
                record=dict(case=case,window=i,**test,optimizer_success=raw[i]['success'],
                    raw_eligible=line['eligible'],frequency_hz=line['frequency_hz'],
                    bound_contact=line['bound_contact'],relative_power_ok=line['relative_power_ok'],
                    local_support_LR=line['local_explained_fraction_LR'])
                r['all_conditional_tests'].append(record)
                result['accepted_added' if test['accepted'] else 'rejected_added'].append(dict(window=i,native_bin=test['native_bin']))
        r['cases'].append(result)
    r.update(result='all108_native_augmented_and22_conditional_tests_postfit_diagnostics_recorded',
        input_report_sha256=sha(a.input/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
        no_real_source_or_runtime_promotion=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],cases=[{k:v[k] for k in ['case','native_success','augmented_success','newly_failed_windows']} for v in r['cases']]))
