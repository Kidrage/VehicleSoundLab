"""Post-fit known-component errors and exact-trajectory connection diagnosis."""
import numpy as np


def nearest(rows, truth):
    output=[]
    for i,(fitted,exact) in enumerate(zip(rows,truth)):
        lines=fitted['lines']
        if not lines:
            output.extend(dict(window=i,component=v['index'],status='no_fitted_line') for v in exact['lines'])
            continue
        picks=[int(np.argmin([abs(v['frequency_hz']-e['frequency_hz']) for v in lines])) for e in exact['lines']]
        for e,k in zip(exact['lines'],picks):
            v=lines[k]
            output.append(dict(window=i,component=e['index'],fitted_line=k,
                nearest_is_unique=picks.count(k)==1,eligible=v['eligible'],optimizer_success=fitted['success'],
                frequency_error_hz=v['frequency_hz']-e['frequency_hz'],
                chirp_error_hz_per_second=v['chirp_hz_per_second']-e['chirp_hz_per_second'],
                amplitude_error_db_LR=(20*np.log10(np.maximum(v['amplitude_LR'],1e-300)/e['amplitude_LR'])).tolist()))
    return output


def exact_connection_diagnostics(truth,plan):
    """Same-component truth only, keeping EVERY original failed inequality."""
    dt=plan['hop']/plan['sample_rate']
    out=[]
    for i in range(1,len(truth)):
        for a,b in zip(truth[i-1]['lines'],truth[i]['lines']):
            forward=b['frequency_hz']-a['frequency_hz']-dt*a['chirp_hz_per_second']
            backward=a['frequency_hz']-b['frequency_hz']+dt*b['chirp_hz_per_second']
            dq=b['chirp_hz_per_second']-a['chirp_hz_per_second']
            fail_frequency=max(abs(forward),abs(backward))>plan['link_prediction_error_hz']
            fail_q=abs(dq)>plan['link_chirp_difference_hz_per_second']
            out.append(dict(previous_window=i-1,current_window=i,component=a['index'],
                forward_error_hz=forward,backward_error_hz=backward,chirp_difference=dq,
                fails_frequency_prediction=fail_frequency,fails_chirp_difference=fail_q,
                same_component_passes=not(fail_frequency or fail_q)))
    return out


def summary(case,rows,linked,truth_linked,pairs,inequalities):
    def tracks(obj,low):
        if obj is None:return dict(count=0,longest=0,atleast5=0)
        chosen=[v for v in obj['tracks'] if not low or v['frequencies_hz'][0]<200]
        return dict(count=len(chosen),longest=max((len(v['windows']) for v in chosen),default=0),
                    atleast5=sum(len(v['windows'])>=5 for v in chosen))
    unique=[v for v in pairs if v.get('nearest_is_unique')]
    low_edges=[v for v in inequalities if v['component']<6]
    return dict(case=case,windows=len(rows),successful=sum(v['success'] for v in rows),
        inventories=[len(v['lines']) for v in rows],capacity_or_empty=[i for i,v in enumerate(rows) if v['reason']=='empty_or_overflow'],
        eligible_lines=sum(v['eligible'] for row in rows for v in row['lines']),
        fitted_low_tracks=tracks(linked,True),exact_low_tracks=tracks(truth_linked,True),
        fitted_all_tracks=tracks(linked,False),exact_all_tracks=tracks(truth_linked,False),
        maximum_unique_frequency_error_hz=max((abs(v['frequency_error_hz']) for v in unique),default=None),
        maximum_unique_chirp_error_hzs=max((abs(v['chirp_error_hz_per_second']) for v in unique),default=None),
        exact_low_same_component_edges=len(low_edges),exact_low_frequency_failures=sum(v['fails_frequency_prediction'] for v in low_edges),
        exact_low_rate_difference_failures=sum(v['fails_chirp_difference'] for v in low_edges))
