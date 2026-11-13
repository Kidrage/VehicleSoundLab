"""Independent adoption-state reconstruction; solver failure is never absence."""
import copy
from native_chirp_audit_v1.wave import near


def check(native,raw,postfit,selected,proposal,verification,actual):
    tests=[]
    m=len(proposal['inventory']['bin'])
    for cell in proposal['added_bins']:
        index=proposal['inventory']['bin'].index(cell)
        present=verification['present']
        deleted=verification['deleted'][str(cell)]
        success=all(v['success'] for v in [raw,present,deleted])
        rank_ok=present.get('rank')==2*m+1 and deleted.get('rank')==2*m-1
        a=present.get('check_cost_LR',[0.,0.])
        b=deleted.get('check_cost_LR',[0.,0.])
        gains=[1-x/y if y>0 else 0. for x,y in zip(a,b)]
        parameter_ok=bool(present['lines'] and present['lines'][index]['training_parameter_gate_ok'])
        prediction=bool(success and rank_ok and parameter_ok and all(v>=.8 for v in gains))
        local=bool(postfit['lines'] and postfit['lines'][index]['eligible'])
        supported=bool(prediction and local)
        state='supported' if supported else 'unknown_solver_failure' if not success else 'unsupported_by_verification'
        tests.append(dict(native_bin=cell,index=index,present_check_cost_LR=a,deleted_check_cost_LR=b,
            prediction_gain_LR=gains,all_hypotheses_successful=success,training_ranks_ok=rank_ok,
            training_parameter_gate_ok=parameter_ok,prediction_passed=prediction,postfit_eligible=local,supported=supported,state=state))
    assert len(tests)==len(actual['tests'])
    for expected,stored in zip(tests,actual['tests']):
        assert expected.keys()==stored.keys()
        for key in expected:
            if key=='prediction_gain_LR':near(expected[key],stored[key],1e-12)
            else:assert expected[key]==stored[key]
    adopted=bool(tests and all(v['supported'] for v in tests))
    reason='all_added_supported' if adopted else 'no_added_candidate' if not tests else (
        'augmentation_unknown' if any(v['state']=='unknown_solver_failure' for v in tests) else 'augmentation_unsupported')
    assert actual['augmented_adopted']==adopted and actual['reason']==reason
    assert actual['native_observation_preserved_not_absence_claim']==(not adopted)
    assert actual['whole_window_candidate_conditioned_not_pristine_holdout']
    if adopted:expected=postfit
    else:
        expected=copy.deepcopy(native)
        for line in expected['lines']:line.update(raw_eligible=line['eligible'],candidate_origin='native_peak')
    assert selected==expected
    return dict(added=len(tests),supported=sum(v['supported'] for v in tests),
        unknown=sum(v['state']=='unknown_solver_failure' for v in tests),adopted=adopted)
