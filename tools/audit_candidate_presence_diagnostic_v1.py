"""Verify post-fit forecasts without changing any original estimator result."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','diagnostic','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load,save,sha
from native_chirp_audit_v1.wave import near
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',forecasts=0,conditional_tests=0,cases=0,maximum_forecast_error=0.)
for name in ['tools/audit_candidate_presence_diagnostic_v1.py','tools/native_chirp_audit_v1/wave.py','tools/research_archive_v1.py']:
    dest=a.out/'exact_sources'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(repo/name,dest)
try:
    diag=load(a.diagnostic/'report.json')
    audit=load(a.audit/'report.json')
    assert diag['input_report_sha256']==audit['input_report_sha256']==sha(a.input/'report.json')
    assert diag['audit_report_sha256']==sha(a.audit/'report.json')
    for name,h in diag['sources'].items():assert sha(repo/name)==h==sha(a.diagnostic/'exact_sources'/name)
    original=load(a.input/'report.json')
    assert len(diag['cases'])==len(original['summaries'])==9
    extra_proposals=[]
    for case,item in zip([v['case'] for v in original['summaries']],diag['cases']):
        folder=a.input/case
        native=load(folder/'native_fits.json')
        raw=load(folder/'raw_fits.json')
        accepted=load(folder/'fits.json')
        proposals=load(folder/'proposals.json')
        presence=load(folder/'presence.json')
        truth=load(folder/'truth.json')['rows']
        scores=load(folder/'scores.json')
        assert item['case']==case
        for tag,rows in [('native',native),('augmented',raw)]:
            assert item[tag+'_success']==sum(v['success'] for v in rows)
            assert item[tag+'_failed_windows']==[i for i,v in enumerate(rows) if not v['success']]
        assert item['newly_failed_windows']==sorted(set(item['augmented_failed_windows'])-set(item['native_failed_windows']))
        assert item['newly_successful_windows']==sorted(set(item['native_failed_windows'])-set(item['augmented_failed_windows']))
        assert item['native_evaluations']==[v.get('evaluations',0) for v in native]
        assert item['extra_evaluations']==[v.get('evaluations',0) if prop['added_bins'] else 0 for v,prop in zip(raw,proposals)]
        for key,score in scores.items():assert item['low_correct_runs'][key]==[v['longest_correct_contiguous'] for v in score['components'][:6]]
        labels={(v['window'],v['index']):v['component'] for v in scores['augmented_boundary']['assignments']}
        forecasts=[v for v in diag['all_forecasts'] if v['case']==case]
        assert len(forecasts)==sum(len(v['provenance']) for v in proposals)
        count=0
        for i,prop in enumerate(proposals):
            for observation in prop['provenance']:
                value=forecasts[count]
                count+=1
                assert value['case']==case and value['window']==i and value['posterior_diagnostic_only']
                for key in observation:assert observation[key]==value[key]
                line=accepted[i-1]['lines'][observation['previous_line_index']]
                assert line['eligible']
                expected=line['frequency_hz']+(line['chirp_hz_per_second']+line['curvature_hz_per_second2']/8)/4
                r['maximum_forecast_error']=max(r['maximum_forecast_error'],near(expected,value['predicted_frequency_hz']))
                identity=labels.get((i-1,line['index']))
                assert identity==value['previous_scored_component']
                target=next((v for v in truth[i]['lines'] if v['index']==identity),None) if truth else None
                if target:
                    assert value['current_truth_visible']==target['visible']
                    near(value['forecast_error_hz'],expected-target['frequency_hz'])
                    near(value['added_native_bin_to_truth_hz'],value['native_bin']*4-target['frequency_hz'])
                    assert value['true_current_outside_original2Hz_box']==(abs(value['native_bin']*4-target['frequency_hz'])>2)
                else:
                    for key in ['current_truth_visible','forecast_error_hz','added_native_bin_to_truth_hz','true_current_outside_original2Hz_box']:assert value[key] is None
                if value['state']=='proposed':extra_proposals.append(value)
                r['forecasts']+=1
        expected_tests=[]
        for i,check in enumerate(presence):
            for test in check['tests']:
                row=raw[i]
                line=row['lines'][test['index']]
                expected_tests.append(dict(case=case,window=i,**test,optimizer_success=row['success'],
                    raw_eligible=line['eligible'],frequency_hz=line['frequency_hz'],bound_contact=line['bound_contact'],
                    relative_power_ok=line['relative_power_ok'],local_support_LR=line['local_explained_fraction_LR']))
        assert expected_tests==[v for v in diag['all_conditional_tests'] if v['case']==case]
        for flag,key in [(True,'accepted_added'),(False,'rejected_added')]:
            assert item[key]==[dict(window=v['window'],native_bin=v['native_bin']) for v in expected_tests if v['accepted']==flag]
        r['conditional_tests']+=len(expected_tests)
        r['cases']+=1
    r.update(result='all_postfit_forecasts_native_augmented_and_conditional_diagnostics_verified',
        input_report_sha256=sha(a.input/'report.json'),audit_report_sha256=sha(a.audit/'report.json'),
        diagnostic_report_sha256=sha(a.diagnostic/'report.json'),proposed_known_forecasts=extra_proposals,
        truth_conditioned_diagnostic_not_estimation=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:save(a.out/'report.json',r)
print({key:r[key] for key in ['result','cases','forecasts','conditional_tests','maximum_forecast_error']})
