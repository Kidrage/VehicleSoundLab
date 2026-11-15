"""Declared source-independent inverse controls, including extreme scales."""
import numpy as np


def inverse_fixtures():
    rng=np.random.default_rng(963714)
    for label,m,n in (('wide',5,8),('tall',9,4),('rank_deficient',6,8),('zero',5,8),
                      ('all_large',4,4),('all_small',4,4),('mixed_aligned',4,4),('mixed_rotated',6,8)):
        X=rng.normal(size=(m,n))
        if label=='rank_deficient':X[:,-3:]=X[:,:3];X[-1]=X[0]
        if label=='zero':X[:]=0
        if label in ('all_large','all_small','mixed_aligned'):
            scales={'all_large':[1e8,2e8,3e8,4e8],'all_small':[1e-8,2e-8,3e-8,4e-8],
                    'mixed_aligned':[1e8,1.,1e-8,0.]}[label]
            X=np.diag(scales)
        if label=='mixed_rotated':
            U=np.linalg.qr(rng.normal(size=(m,m)))[0]
            V=np.linalg.qr(rng.normal(size=(n,n)))[0]
            D=np.zeros((m,n));np.fill_diagonal(D,[1e8,1e4,1.,1e-4,1e-8,0.])
            X=U@D@V.T
        rhs=np.column_stack((np.eye(n),rng.normal(size=(n,2)),np.zeros(n)))
        yield label,X,rhs
