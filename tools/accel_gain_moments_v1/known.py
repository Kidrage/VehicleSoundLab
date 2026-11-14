"""Gaussian quadrature and explicit native covariance before reading source models."""
import numpy as np
from numpy.polynomial.hermite import hermgauss
from .model import finite_moments


def known():
    L = np.array([[.3, 0.], [-.2, .15]])
    G = L @ L.T
    m, blocks, fs, tau = 5, 3, 100, .2
    actual = finite_moments(G, tau, m, blocks, fs)
    x, w = hermgauss(35)
    z = np.sqrt(2)*x
    W = np.outer(w, w)/np.pi
    mu = actual['mean']
    first = np.array([np.sum(w*np.exp(p*(np.sqrt(G[a,a])*z-G[a,a])))/np.sqrt(np.pi)
                      for a,p in zip(actual['coordinate'],actual['powers'])])
    first_error = float(abs(first-mu).max())
    C = np.zeros((m*blocks, m*blocks, 4, 4))
    error = 0.
    for i in range(4):
        a, p = int(actual['coordinate'][i]), actual['powers'][i]
        vi = G[a, a]
        for j in range(4):
            b, q = int(actual['coordinate'][j]), actual['powers'][j]
            for lag in range(m*blocks):
                cov = G[a, b]*np.exp(-lag/(fs*tau))
                left = np.sqrt(vi)*z[:, None]
                right = cov/np.sqrt(vi)*z[:, None] + np.sqrt(max(0., G[b,b]-cov**2/vi))*z[None, :]
                product = np.exp(p*(left-vi)+q*(right-G[b,b]))
                value = np.sum(W*product)-mu[i]*mu[j]
                exact = mu[i]*mu[j]*np.expm1(p*q*cov)
                error = max(error, abs(value-exact))
                aa, bb = np.indices((m*blocks, m*blocks))
                C[:, :, i, j][abs(bb-aa)==lag] = value
    expected = np.zeros_like(actual['full_block_covariance'])
    for a in range(blocks):
        for b in range(blocks):
            expected[a*4:(a+1)*4, b*4:(b+1)*4] = C[a*m:(a+1)*m, b*m:(b+1)*m].sum(axis=(0, 1))/m**2
    matrix_error = float(abs(expected-actual['full_block_covariance']).max())
    run = expected.reshape(blocks,4,blocks,4).sum(axis=(0,2))/blocks**2
    run_error = float(abs(run-actual['continuous_run_covariance']).max())
    assert max(first_error,error,matrix_error,run_error)<1e-12
    assert np.all(actual['block_lag_covariance'][:,0,1]<0)
    assert np.array_equal(mu[:2], np.ones(2))
    zero = finite_moments(np.zeros((2,2)),tau,m,blocks,fs)
    assert not np.any(zero['full_block_covariance']) and np.all(zero['mean']==1)
    independent = finite_moments(np.diag(np.diag(G)),tau,m,blocks,fs)
    assert not np.any(independent['block_lag_covariance'][:,0,1])
    permuted = finite_moments(G[::-1,::-1],tau,m,blocks,fs)
    index = np.array([1,0,3,2])
    permutation_error = float(abs(permuted['block_lag_covariance']-actual['block_lag_covariance'][:,index][:,:,index]).max())
    assert permutation_error<1e-12
    rank = finite_moments(np.array([[.09,-.06],[-.06,.04]]),tau,1,blocks,fs)
    assert np.all(np.linalg.eigvalsh(rank['full_block_covariance'])>-1e-12)
    rejected=0
    for gamma,t,m0 in [(np.ones((2,3)),tau,m),(np.array([[1,2],[2,1]]),tau,m),(G,0,m),(G,tau,1.5)]:
        try:finite_moments(gamma,t,m0,blocks,fs)
        except ValueError:rejected+=1
    assert rejected==4
    return dict(Gaussian_first_quadrature_error=first_error,Gaussian_product_quadrature_error=error,full_window_matrix_error=matrix_error,
                continuous_run_error=run_error,permutation_error=permutation_error,
                zero_variance_exact=True,independent_coordinates_exact=True,negative_crosscovariance_preserved=True,
                singular_covariance=True,invalid_inputs_rejected=rejected), dict(gamma=G,full_quadrature_covariance=expected,
                **{k:v for k,v in actual.items() if k!='gamma'})
