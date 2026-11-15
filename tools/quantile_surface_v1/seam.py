"""One declared negative circular-seam control; no material or random inputs."""
import numpy as np


def fixture():
    edge=np.pi-.01
    return dict(knots=np.array([0.,1.]),cdf=np.array([[0.,.9999,.99995,1.],[0.,.00005,.0001,1.]]),
                low=np.array([-edge,-edge,edge]),high=np.array([-edge,edge,edge]))
