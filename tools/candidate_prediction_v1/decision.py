"""Explicit all-candidate model adoption with unknown distinct from unsupported."""
import copy
import numpy as np


def decide(native,raw,postfit,proposal,training,deleted):
    tests=[]
    count=len(proposal['inventory']['bin'])
    for cell in proposal['added_bins']:
        index=proposal['inventory']['bin'].index(cell)
        null=deleted[cell]
        all_success=bool(raw['success'] and training['success'] and null['success'])
        dimensions=bool(training.get('rank')==2*count+1 and null.get('rank')==2*(count-1)+1)
        present_cost=np.asarray(training.get('check_cost_LR',[0.,0.]))
        null_cost=np.asarray(null.get('check_cost_LR',[0.,0.]))
        gain=1-np.divide(present_cost,null_cost,out=np.ones(2),where=null_cost>0)
        parameter_ok=bool(training['lines'] and training['lines'][index]['training_parameter_gate_ok'])
        predicted=bool(all_success and dimensions and parameter_ok and min(gain)>=.8)
        accepted=bool(predicted and postfit['lines'] and postfit['lines'][index]['eligible'])
        state='supported' if accepted else 'unknown_solver_failure' if not all_success else 'unsupported_by_verification'
        tests.append(dict(native_bin=cell,index=index,present_check_cost_LR=present_cost.tolist(),
            deleted_check_cost_LR=null_cost.tolist(),prediction_gain_LR=gain.tolist(),
            all_hypotheses_successful=all_success,training_ranks_ok=dimensions,training_parameter_gate_ok=parameter_ok,
            prediction_passed=predicted,postfit_eligible=bool(postfit['lines'] and postfit['lines'][index]['eligible']),
            supported=accepted,state=state))
    adopted=bool(tests and all(v['supported'] for v in tests))
    if adopted:chosen=copy.deepcopy(postfit)
    else:
        chosen=copy.deepcopy(native)
        for line in chosen['lines']:
            line['raw_eligible']=line['eligible']
            line['candidate_origin']='native_peak'
    reason='all_added_supported' if adopted else 'no_added_candidate' if not tests else (
        'augmentation_unknown' if any(v['state']=='unknown_solver_failure' for v in tests) else 'augmentation_unsupported')
    return chosen,dict(augmented_adopted=adopted,reason=reason,tests=tests,
        native_observation_preserved_not_absence_claim=not adopted,
        whole_window_candidate_conditioned_not_pristine_holdout=True)
