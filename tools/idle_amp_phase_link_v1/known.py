"""Known finite algebra and a short-record noncoupling counterexample."""
import numpy as np
from .observe import feature,fit,predict,covariance


def fixtures():
    t=np.arange(232)/50
    x=np.column_stack((np.sin(2*np.pi*.8*t+.2),np.cos(2*np.pi*1.3*t-.1),
        np.cos(2*np.pi*.8*t+.2),np.sin(2*np.pi*1.3*t-.1)))
    beta=np.array([[.12,-.08,.03],[.02,.11,-.06],[-.04,.02,.09],[.07,-.03,.02]])
    y=np.array([-2.2,-2.3,-3.1])+x@beta
    return x[:116],y[:116],x[116:],y[116:],beta


def run():
    n=144000;t=np.arange(n)/48000
    psi=.2+.15*np.sin(2*np.pi*.7*t);eta=-.4+.2*np.cos(2*np.pi*.9*t)
    theta=np.column_stack((2*2*np.pi*37.5*t+eta/3,3*2*np.pi*37.5*t,
        5*2*np.pi*37.5*t+psi+eta/3))
    z=np.exp(1j*theta);starts=np.arange(12000,122401,960)
    actual=feature(z,starts)
    w=.5-.5*np.cos(2*np.pi*np.arange(9600)/9600)
    truth=np.column_stack((np.cos(psi),np.cos(eta),np.sin(psi),np.sin(eta)))
    expected=np.array([np.average(truth[j:j+9600],axis=0,weights=w) for j in starts])
    error=float(abs(actual-expected).max());assert error<1e-12
    x,y,q,v,b=fixtures();model=fit(x,y)
    regression=float(abs(predict(model,q)-v).max());assert regression<1e-12
    # Rotating the two circular origins changes the feature basis, not predictions.
    angle=np.array([.4,-.8]);c=np.cos(angle);s=np.sin(angle)
    def rotate(a):return np.column_stack((a[:,:2]*c-a[:,2:]*s,a[:,:2]*s+a[:,2:]*c))
    rotated=fit(rotate(x),y)
    rotation=float(abs(predict(rotated,rotate(q))-predict(model,q)).max());assert rotation<1e-12
    values=np.column_stack((y,x));curves,count=covariance(values)
    maximum=0.
    centered=values-values.mean(axis=0)
    for index,lag in enumerate(range(-25,26)):
        origins=range(max(0,-lag),min(len(values),len(values)-lag))
        scalar=np.array([[sum(float(centered[i,j])*float(centered[i+lag,k]) for i in origins)/len(origins)
            for k in range(7)] for j in range(7)])
        maximum=max(maximum,float(abs(curves[index]-scalar).max()))
    assert maximum<1e-12
    short=np.arange(116)/50
    a=np.sin(2*np.pi*.05*short+.3);b=np.sin(2*np.pi*.065*short+.3)
    false=float(np.corrcoef(a,b)[0,1]);assert abs(false)>.95
    return dict(result='known_new_feature_and_regression_controls_passed',
        exact_window_circular_error=error,exact_CHECK_regression_error=regression,
        origin_rotation_prediction_error=rotation,all51x7x7_scalar_covariance_error=maximum,
        short_free_running_tones_correlation=false,
        counterexample='Different free-running frequencies can correlate strongly over a short record; finite correlation is not phase/AM coupling'),dict(
        phasors=z,starts=starts,features=actual,expected_features=expected,
        train_x=x,train_y=y,check_x=q,check_y=v,full_covariance=curves,overlap_counts=count)
