"""Known signals distinguish guided matches from oscillator/physical-source identity."""
import numpy as np
from .observe import inventory,correspondence,associate


def controls(plan):
    rate=plan['rate'];n=plan['tile_frames'];tiles=12;time=np.arange(n*tiles)/rate
    moving=np.array([337.31,963.23,1751.73,3189.19]);fixed=np.array([583.41,1357.77,2600.27,4231.14])
    scale=1+.05*time;phase_integral=time+.025*time*time
    centers=(np.arange(tiles)+.5)*n/rate;ratios=(1+.05*centers)/(1+.05*centers[0])
    guides=[dict(ratio=float(r),supported=True) for r in ratios]
    moving_audio=sum((.14/(1+i*.2))*np.cos(2*np.pi*f*phase_integral+.31*i) for i,f in enumerate(moving))
    fixed_audio=sum(.09*np.cos(2*np.pi*f*time-.21*i) for i,f in enumerate(fixed))
    expected_moving=moving*(1+.05*centers[0]);fixtures={};report={}
    def inspect(name,left,right=None):
        audio=np.column_stack((left,.67*left if right is None else right));fixtures[name]=audio
        inventories=[inventory(audio[i*n:(i+1)*n],plan) for i in range(tiles)]
        evidence=correspondence(inventories,guides,plan);report[name]=dict(inventories=inventories,evidence=evidence)
        return evidence
    combined=inspect('moving_and_fixed',moving_audio+fixed_audio)
    def near(result,f):return min(result['classes'],key=lambda row:abs(row['reference_hz']-f))
    for f in expected_moving:assert abs(near(combined,f)['reference_hz']-f)<1 and near(combined,f)['classification']=='moving',(f,near(combined,f))
    for f in fixed:assert abs(near(combined,f)['reference_hz']-f)<1 and near(combined,f)['classification']=='fixed',(f,near(combined,f))
    gain=inspect('global_gain',.031*(moving_audio+fixed_audio))
    assert [x['classification'] for x in gain['classes']]==[x['classification'] for x in combined['classes']]
    stationary=inspect('false_moving_guide',fixed_audio)
    assert stationary['counts']['moving']==0 and stationary['counts']['fixed']==4,stationary['counts']
    lost=.14/1.2*np.cos(2*np.pi*moving[1]*phase_integral+.31)
    missing=moving_audio+fixed_audio;missing[6*n:]-=lost[6*n:]
    missing[6*n:]+=.14/1.2*np.cos(2*np.pi*(moving[1]*phase_integral[6*n:]+30*time[6*n:])+.31)
    removed=inspect('missing_with_neighbour',missing)
    lost_row=near(removed,expected_moving[1]);assert lost_row['classification']=='uncertain',lost_row
    assert all(i<6 for i in lost_row['hypothesis_unique_tiles']['moving']),lost_row
    rng=np.random.default_rng(821931);left=rng.normal(0,.1,len(time));right=rng.normal(0,.1,len(time))
    independent=inspect('independent_noise',left,right);mono=inspect('same_mono_noise',left)
    assert independent['counts']['moving']==mono['counts']['moving']==0
    quiet=inspect('silence',np.zeros(len(time)));assert not quiet['classes']
    graph=associate([1000,1008],[1004],1,4,plan);assert graph['state']==['ambiguous','ambiguous']
    report['ambiguous_graph']=graph
    # Adaptive diagnostic motivated by observe1. All26 partials move, but
    # unrelated partials can intermittently cross a fixed-frequency query.
    orders=np.arange(5,31)
    comb=sum(.1*(o/5)**-.5*np.cos(2*np.pi*(60*o)*phase_integral+.17*o) for o in orders)
    dense=inspect('dense_moving_comb',comb)
    records=[near(dense,60*o*(1+.05*centers[0])) for o in orders]
    uncertain=[row for row in records if row['classification']=='uncertain' and row['support_fraction']['moving']>=.8]
    assert uncertain,'Expected diagnostic limitation was not reproduced; inspect before interpreting recordings'
    report['dense_comb_limitation']=dict(known_moving_partials=len(orders),
        raw_moving_support_at_least80=sum(row['support_fraction']['moving']>=.8 for row in records),
        false_uncertain_despite_moving_support=len(uncertain),
        interpretation='Intermittent alternative matches do not identify a persistent fixed component. Original classes retained; not a physical source classifier.')
    return report,fixtures
