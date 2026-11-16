"""Original node-curvature prior using only the small node-axis matrix."""
import numpy as np
from scipy.linalg import cho_factor,cho_solve


class Prior:
    def __init__(self,source):
        self.source=source;p=source.positions.astype(float);self.d=np.zeros((len(p)-2,len(p)))
        for j in range(len(self.d)):
            left,right=np.diff(p[j:j+3]);s=2*256**2/(left+right)
            self.d[j,j:j+3]=[s/left,-s/left-s/right,s/right]
        self.r=.001*self.d.T@self.d+1e-6*np.eye(len(p));self.factor=cho_factor(self.r,lower=True)

    def apply(self,x):
        nodes=self.source.nodes(x)
        return self.source.vector((self.r@nodes.reshape(len(nodes),-1)).reshape(nodes.shape))

    def inverse(self,x):
        nodes=self.source.nodes(x)
        return self.source.vector(cho_solve(self.factor,nodes.reshape(len(nodes),-1)).reshape(nodes.shape))

    def cost(self,x):return float(.5*x@self.apply(x))
