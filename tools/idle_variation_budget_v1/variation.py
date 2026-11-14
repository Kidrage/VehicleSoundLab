"""Descriptive signed variation budget; no latent-source or log-variance inference."""
import numpy as np

LAGS=np.arange(-25,26)
BANDS=np.array([[0,1],[1,3],[3,8],[8,25.000001]])


def vector(coefficients,reference):
    z=np.asarray(coefficients)/np.asarray(reference)
    return np.column_stack((z.real,z.imag))


def covariance(left,right):
    a=np.asarray(left)-np.mean(left,axis=0);b=np.asarray(right)-np.mean(right,axis=0)
    result=[]
    for lag in LAGS:
        l,r=(a[:len(a)-lag or None],b[lag:]) if lag>=0 else (a[-lag:],b[:len(b)+lag])
        result.append(l.T@r/len(l))
    return np.array(result)


def temporal(values):
    a=np.asarray(values)-np.mean(values,axis=0);n=len(a);w=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    f=np.fft.rfftfreq(n,1/50);psd=abs(np.fft.rfft(a*w[:,None],axis=0))**2/(n*np.dot(w,w))
    psd[1:-1]*=2
    powers=np.array([psd[(f>=lo)&(f<hi)].sum(axis=0) for lo,hi in BANDS])
    parseval=float(abs(psd.sum(axis=0)-np.sum((a*w[:,None])**2,axis=0)/np.dot(w,w)).max())
    assert parseval<1e-12
    return powers,psd,parseval


def summarize(coefficients,reference):
    v=vector(coefficients,reference);c=covariance(v,v);p,psd,pe=temporal(v)
    variance=np.diag(c[25]);rho=[]
    for lag in [5,10,25]:rho.append(np.diag(c[25+lag])/variance)
    magnitude=abs(coefficients)
    if np.any(magnitude<=0):raise ValueError('Undefined log magnitude')
    return dict(covariance=c,temporal_power=p,temporal_psd=psd,
        coefficient_mean=coefficients.mean(axis=0),normalized_mean=v.mean(axis=0),
        std=np.sqrt(variance),rho_100_200_500ms=np.array(rho),
        log_std=np.std(np.log(magnitude),axis=0),temporal_parseval_error=pe)


def budget(coefficients,reference):
    v=[vector(coefficients[:,j],reference) for j in range(3)]
    total=covariance(v[0],v[0]);main=covariance(v[1],v[1]);detail=covariance(v[2],v[2])
    md=covariance(v[1],v[2]);dm=covariance(v[2],v[1]);cross=md+dm
    identity=float(abs(total-main-detail-cross).max())
    assert identity<1e-10
    return dict(main_covariance=main,detail_covariance=detail,main_detail_covariance=md,
        detail_main_covariance=dm,cross_covariance=cross,budget_identity_error=identity,
        main_std=np.sqrt(np.diag(main[25])),detail_std=np.sqrt(np.diag(detail[25])),
        lag0_signed_variance_ratios=np.array([np.diag(item[25])/np.diag(total[25]) for item in [main,detail,cross]]))


def known():
    t=np.arange(116)/50
    main=np.column_stack([np.sin(2*np.pi*(.7+j*.31)*t+j*.2) for j in range(6)])
    detail=-.8*main+.13*np.cos(t[:,None]*[2.,3.,5.,7.,11.,13.])
    mix=main+detail;c=[covariance(x,x) for x in [mix,main,detail]]
    cross=covariance(main,detail)+covariance(detail,main)
    error=float(abs(c[0]-c[1]-c[2]-cross).max());assert error<1e-12
    assert np.all(np.diag(cross[25])<0) and np.all(np.diag(c[1][25])>np.diag(c[0][25]))
    power,psd,parseval=temporal(mix)
    return dict(negative_cross_preserved=True,marginal_variance_can_exceed_mix=True,
        signed_identity_error=error,temporal_parseval_error=parseval),dict(main=main,detail=detail,mix=mix,
            total_covariance=c[0],main_covariance=c[1],detail_covariance=c[2],cross_covariance=cross,
            temporal_power=power,temporal_psd=psd)
