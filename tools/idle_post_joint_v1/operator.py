"""All even-cumulant columns under actual nonstationary POST responses."""
import numpy as np

PAIRS=[(b,c) for b in range(4) for c in range(b,4)]
DIAGONAL=[0,4,7,9]


def joint_operator(response,epsilon):
    """response[time,output,input,delay], epsilon[output,input]. Diagonal multiplier1."""
    count=response.shape[0];matrix=np.empty((count,10,10));bound=np.empty_like(matrix)
    norm=np.linalg.norm(response,axis=3)
    for row,(b,c) in enumerate(PAIRS):
        x,y=response[:,b],response[:,c]
        F=(x*x)@np.swapaxes(y*y,1,2)
        products=x*y;G=products@np.swapaxes(products,1,2)
        for column,(i,j) in enumerate(PAIRS):
            ni,nj,nk,nl=norm[:,b,i],norm[:,b,j],norm[:,c,i],norm[:,c,j]
            ei,ej,ek,el=epsilon[b,i],epsilon[b,j],epsilon[c,i],epsilon[c,j]
            if i==j:
                matrix[:,row,column]=G[:,i,i]
                delta=ni*ek+nk*ei+ei*ek
                bound[:,row,column]=2*np.sqrt(G[:,i,i])*delta+delta*delta
            else:
                matrix[:,row,column]=F[:,i,j]+F[:,j,i]+4*G[:,i,j]
                d1=ni*el+nl*ei+ei*el;d2=nj*ek+nk*ej+ej*ek
                square_error=2*np.sqrt(F[:,i,j])*d1+d1*d1+2*np.sqrt(F[:,j,i])*d2+d2*d2
                di=ni*ek+nk*ei+ei*ek;dj=nj*el+nl*ej+ej*el
                signed_error=np.sqrt(G[:,i,i])*dj+np.sqrt(G[:,j,j])*di+di*dj
                bound[:,row,column]=square_error+4*signed_error
    return matrix,bound


def family_matrix(matrix,multiplier):
    result=matrix.copy();result[...,DIAGONAL]*=multiplier
    return result
