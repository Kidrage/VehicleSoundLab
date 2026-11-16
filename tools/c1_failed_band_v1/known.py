"""New interval-extremum and optimality-restriction controls only."""
import numpy as np
from .clock import bounds


def qualify():
    d=1/65536.;curvature=1e-8
    affine=np.array([[0.],[0.],[d],[0.]])
    curved=np.array([[curvature/3],[-4*curvature],[d+16*curvature],[0.]])
    expected=((d,d),(d,d+16*curvature),(d,d+9*curvature))
    actual=(bounds(np.array([0.,8.]),affine,0.,8.),bounds(np.array([0.,8.]),curved,0.,8.),
        bounds(np.array([0.,8.]),curved,1.,5.))
    assert np.max(abs(np.array(actual)-expected))<2e-18
    rejects=[]
    for label,c,lo,hi in (('outside',affine,-1.,4.),('reversed',affine,5.,1.),('negative',-affine,0.,8.)):
        try:bounds(np.array([0.,8.]),c,lo,hi)
        except ValueError:rejects.append(label)
        else:raise AssertionError('Invalid clock accepted')
    design=np.array([[1.,.2,-.4],[.1,1.3,.5],[.8,.2,.6],[-.3,.4,1.2],
        [.2,-.5,.7],[1.1,-.8,.2],[-.1,.7,-.3],[.6,.5,.9]])
    y=np.array([1.,-.4,.8,.3,-.2,.9,.1,-.7]);m=design.shape[1]
    optimum=np.linalg.lstsq(np.vstack((design,np.eye(m))),np.r_[y,np.zeros(m)],rcond=None)[0]
    dual=y-design@optimum;rows=np.array([1,3,6]);results=[]
    for label,shift,du in (('near',1e-5,0.),('offset',.02,.01),('large',.2,-.1)):
        q=optimum+shift*np.array([1.,-2.,.5]);u=dual+du*np.arange(1.,9.)
        gap=float(np.sum((design@q-y+u)**2)+np.sum((q-design.T@u)**2))
        distance=float(np.linalg.norm((design@(q-optimum))[rows]))
        lower=max(0.,float(np.linalg.norm((design@q-y)[rows]))-np.sqrt(gap))/np.linalg.norm(y[rows])
        true=float(np.linalg.norm((design@optimum-y)[rows])/np.linalg.norm(y[rows]))
        assert distance<=np.sqrt(gap)+2e-12 and lower<=true+2e-12
        results.append(dict(label=label,gap=gap,restricted_distance=distance,lower_band_ratio=lower,true_optimal_band_ratio=true))
    return dict(clock_cases=3,clock_rejections=rejects,optimality_cases=results,
        only_new_diagnostic_equations=True,known_before_actual=True)
