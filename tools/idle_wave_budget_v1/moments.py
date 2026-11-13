"""Time-origin/innovation-ensemble cumulants, not finite-record estimator expectations."""
import numpy as np

MOMENTS = [(1, 0), (0, 1), (2, 0), (0, 2), (1, 1), (2, 1), (1, 2), (2, 2)]
TERMS = ['main', 'variance_covariance', 'conditional_covariance_variation',
         'main_b_variance_c', 'main_c_variance_b', 'main_covariance', 'innovation']


def covariance(x, y):
    return np.mean((x-x.mean())*(y-y.mean()))


def pooled(m, d, v, w, c, j):
    a, b = m-m.mean(), d-d.mean()
    terms = dict(main=float(np.mean(a*a*b*b)-np.mean(a*a)*np.mean(b*b)-2*np.mean(a*b)**2),
                 variance_covariance=float(covariance(v, w)),
                 conditional_covariance_variation=float(2*covariance(c, c)),
                 main_b_variance_c=float(covariance(a*a, w)),
                 main_c_variance_b=float(covariance(b*b, v)),
                 main_covariance=float(4*covariance(a*b, c)), innovation=float(j.mean()))
    raw = [m.mean(), d.mean(), np.mean(m*m+v), np.mean(d*d+w), np.mean(m*d+c),
           np.mean(m*m*d+d*v+2*m*c), np.mean(m*d*d+m*w+2*d*c),
           np.mean(m*m*d*d+m*m*w+d*d*v+4*m*d*c+v*w+2*c*c+j)]
    return dict(raw=np.asarray(raw), terms=terms, cumulant=sum(terms.values()),
                covariance=float(np.mean(a*b+c)),
                overlap_variance=[float(np.mean(a*a+v)), float(np.mean(b*b+w))])
