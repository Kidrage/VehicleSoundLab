"""Known recoverable weak lines plus explicit noise/numerical-tail counterexamples."""
import numpy as np
from .observe import measure


def fixtures(plan):
    n=plan['frames'];t=np.arange(n)/plan['sample_rate'];rng=np.random.default_rng(149921)
    noise=rng.normal(size=(n,2))*1e-6
    base=.4*np.cos(2*np.pi*300*t+.23)
    upper=1e-4*np.cos(2*np.pi*5132*t+.7)+8e-5*np.cos(2*np.pi*10012*t-.3)
    positive=np.column_stack((base+upper,.67*(base+upper)))+noise
    output={'quiet_upper':positive,'quiet_upper_gain':positive*.013,
            'moving_upper':np.column_stack((base+1e-4*np.cos(2*np.pi*(5132*t+80*t*t/2)+.7),
                                            .67*(base+1e-4*np.cos(2*np.pi*(5132*t+80*t*t/2)+.7))))+noise,
            'missing_with_neighbor':np.column_stack((base+1e-4*np.cos(2*np.pi*5192*t+.7),
                                                     .67*(base+1e-4*np.cos(2*np.pi*5192*t+.7))))+noise,
            'pure_low_numerical_tail':np.column_stack((base,.67*base)),
            'silence':np.zeros((n,2))}
    for seed in [149921,277139,381611]:
        random=np.random.default_rng(seed).normal(size=(n,2))*.01
        output[f'noise_independent_{seed}']=random
        output[f'noise_mono_{seed}']=np.column_stack((random[:,0],random[:,0]*.67))
    return output


def check(rows):
    positive=rows['quiet_upper']['peaks']
    for f in [5132,10012]:
        found=[v for v in positive if v['local_candidate'] and abs(v['frequency_hz']-f)<4]
        assert len(found)==1 and not found[0]['old_floor_ok']
    a=[v for v in positive if v['local_candidate']]
    b=[v for v in rows['quiet_upper_gain']['peaks'] if v['local_candidate']]
    assert [v['bin'] for v in a]==[v['bin'] for v in b]
    assert max(abs(x['frequency_hz']-y['frequency_hz']) for x,y in zip(a,b))<1e-7
    moving=[v for v in rows['moving_upper']['peaks'] if v['local_candidate'] and abs(v['frequency_hz']-5142)<4]
    assert len(moving)==1
    assert not any(v['local_candidate'] and abs(v['frequency_hz']-5132)<4 for v in rows['missing_with_neighbor']['peaks'])
    assert not rows['silence']['peaks']
    noise={name:sum(v['local_candidate'] for v in row['peaks']) for name,row in rows.items() if name.startswith('noise_')}
    assert all(v>0 for v in noise.values())
    return dict(quiet_lines_recovered=2,old_floor_rejects_both=True,gain_invariant=True,
                moving_line_recovered=True,no_forced_missing_slot=True,noise_candidate_counts=noise,
                numerical_tail_candidates=sum(v['local_candidate'] for v in rows['pure_low_numerical_tail']['peaks']),
                local_peak_inventory_is_NOT_source_detector=True)
