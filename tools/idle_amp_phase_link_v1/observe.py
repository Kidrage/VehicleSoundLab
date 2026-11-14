"""Branch-free, analysis-only relative-phase to window-magnitude evidence."""
import numpy as np

SELECTED=np.array([1,2,4])
FRAMES=9600


def feature(phasors,starts):
    z=np.asarray(phasors)
    w=np.column_stack((z[:,2]*z[:,1].conj()*z[:,0].conj(),z[:,0]**3*z[:,1].conj()**2))
    weight=.5-.5*np.cos(2*np.pi*np.arange(FRAMES)/FRAMES)
    mean=np.array([np.sum(weight[:,None]*w[j:j+FRAMES],axis=0)/sum(weight) for j in starts])
    return np.column_stack((mean.real,mean.imag))


def target(coefficients):
    magnitude=abs(np.asarray(coefficients)[:,SELECTED])
    if np.any(magnitude<=0):raise ValueError('Undefined log magnitude; no floor')
    return np.log(magnitude)


def fit(x,y):
    mean=x.mean(axis=0);std=x.std(axis=0)
    if np.any(std<=0):return dict(available=False,reason='zero feature variance')
    design=np.column_stack((np.ones(len(x)),(x-mean)/std))
    beta,_,rank,singular=np.linalg.lstsq(design,y,rcond=None)
    condition=float(singular[0]/singular[-1])
    if rank!=5 or condition>1e6:
        return dict(available=False,reason='rank or condition',rank=int(rank),condition=condition)
    return dict(available=True,mean=mean.tolist(),std=std.tolist(),coefficients=beta.tolist(),
        TRAIN_target_mean=y.mean(axis=0).tolist(),rank=int(rank),condition=condition,
        source_trajectory_exported=False)


def predict(model,x):
    assert model['available']
    return np.column_stack((np.ones(len(x)),(x-model['mean'])/model['std']))@model['coefficients']


def evaluate(model,x,y):
    prediction=predict(model,x)
    mse=np.mean((prediction-y)**2,axis=0)
    base=np.mean((y-model['TRAIN_target_mean'])**2,axis=0)
    if np.any(base<=0):raise ValueError('Undefined relative MSE')
    return dict(MSE=mse.tolist(),TRAIN_constant_MSE=base.tolist(),
        fractional_MSE_reduction=(1-mse/base).tolist(),prediction=prediction)


def covariance(values,maximum=25):
    v=values-values.mean(axis=0);result=[];count=[]
    for lag in range(-maximum,maximum+1):
        if lag>=0:left,right=v[:len(v)-lag or None],v[lag:]
        else:left,right=v[-lag:],v[:len(v)+lag]
        result.append(left.T@right/len(left));count.append(len(left))
    return np.array(result),np.array(count)
