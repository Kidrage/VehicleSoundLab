"""Set-valued root/RPM mapping under a shared unknown display-time offset."""
import numpy as np


def evaluate(times,root,readings,offsets,frequency_fraction=0):
    times=np.asarray(times,float);root=np.asarray(root,float)
    if len(times)<2 or times.shape!=root.shape or np.any(np.diff(times)<=0) or np.any(root<=0):
        raise ValueError('Strictly increasing finite positive acoustic observations required')
    if not np.isfinite(times).all() or not np.isfinite(root).all() or not 0<=frequency_fraction<1:
        raise ValueError('Finite observations and bounded sensitivity required')
    result=[]
    for offset in offsets:
        rows=[]
        for reading in readings:
            stamp=reading['seconds']-offset;lo,hi=reading['rpm_interval']
            if lo<=0 or hi<lo:raise ValueError('Positive ordered RPM intervals required')
            if stamp<times[0] or stamp>times[-1]:
                rows.append(dict(display_seconds=reading['seconds'],audio_seconds=float(stamp),status='outside_acoustic_support'))
                continue
            f=float(np.interp(stamp,times,root))
            rows.append(dict(display_seconds=reading['seconds'],audio_seconds=float(stamp),status='measured',
                acoustic_root_hz=f,root_per_rpm_interval=[f*(1-frequency_fraction)/hi,f*(1+frequency_fraction)/lo]))
        complete=all(v['status']=='measured' for v in rows)
        if complete:
            lower=max(v['root_per_rpm_interval'][0] for v in rows)
            upper=min(v['root_per_rpm_interval'][1] for v in rows)
            feasible=lower<=upper
        else:lower=upper=None;feasible=False
        result.append(dict(display_minus_audio_seconds=float(offset),all_readings_supported=complete,
            feasible=bool(feasible),root_per_rpm_interval=[lower,upper] if feasible else None,rows=rows))
    return result


def known_controls():
    times=np.arange(0,8.01,.01);rpm=6000+1000*times
    readings=[dict(seconds=t+.25,rpm_interval=[6000+1000*t]*2) for t in (1,2,4,6)]
    result=evaluate(times,rpm/120,readings,[.2,.25,.3])
    truth=result[1]
    assert truth['feasible'] and max(abs(v-1/120) for v in truth['root_per_rpm_interval'])<1e-15
    assert not result[0]['feasible'] and not result[2]['feasible']
    unsupported=evaluate(times,rpm/120,readings,[-2])[0]
    assert not unsupported['all_readings_supported'] and not unsupported['feasible']
    # Interval arithmetic independently checked by a dense ratio membership
    # test. Every candidate must satisfy every original RPM inequality.
    wide=[dict(v,rpm_interval=[v['rpm_interval'][0]-100,v['rpm_interval'][1]+100]) for v in readings]
    row=evaluate(times,rpm/120,wide,[.25],.01)[0]
    lower,upper=row['root_per_rpm_interval']
    grid=np.linspace(lower*.99,upper*1.01,10001)
    direct=np.ones(len(grid),bool)
    for reading in wide:
        f=(6000+1000*(reading['seconds']-.25))/120;lo,hi=reading['rpm_interval']
        direct &= (grid*hi>=f*.99)&(grid*lo<=f*1.01)
    assert np.array_equal(direct,(grid>=lower)&(grid<=upper))
    return dict(shared_offset_sign=True,known_exact_mapping=True,unsupported_not_extrapolated=True,
                dense_membership_candidates=len(grid),interval_membership_exact=True)
