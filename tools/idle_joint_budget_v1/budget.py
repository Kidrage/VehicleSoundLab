"""Full even-cumulant filter map and sufficient positive-factor certificate."""
import numpy as np

PAIRS=[(b,c) for b in range(4) for c in range(b,4)]


def operator(h,diagonal_multiplier):
    result=np.empty((10,10))
    for row,(b,c) in enumerate(PAIRS):
        for column,(i,j) in enumerate(PAIRS):
            if i==j:
                result[row,column]=diagonal_multiplier*np.sum((h[b,i]*h[c,i])**2)
            else:
                result[row,column]=np.sum((h[b,i]*h[c,j])**2+(h[b,j]*h[c,i])**2+
                    4*h[b,i]*h[b,j]*h[c,i]*h[c,j])
    return result


def pack(matrix):
    return np.array([matrix[b,c] for b,c in PAIRS])


def unpack(values):
    result=np.empty((4,4))
    for value,(b,c) in zip(values,PAIRS):
        result[b,c]=result[c,b]=value
    return result


def solve(matrix,target,row_scale,family,tolerance=1e-10):
    scaled=matrix/row_scale[:,None]
    column_scale=np.linalg.norm(scaled,axis=0)
    if np.any(column_scale==0):
        return dict(status='rank_deficient_UNKNOWN',rank=0,reason='zero_column')
    normalized=scaled/column_scale
    singular=np.linalg.svd(normalized,compute_uv=False)
    cutoff=np.finfo(float).eps*10*singular[0]
    rank=int(np.sum(singular>cutoff))
    result=dict(rank=rank,singular_values=singular.tolist(),rank_cutoff=float(cutoff),
        column_scale=column_scale.tolist(),condition=float(singular[0]/singular[-1]) if singular[-1]>0 else None)
    if rank<10:
        return dict(result,status='rank_deficient_UNKNOWN')
    values=np.linalg.solve(normalized,target/row_scale)/column_scale
    latent=unpack(values)
    prediction=matrix@values
    residual=float(np.max(abs((prediction-target)/row_scale)))
    eigen=np.linalg.eigvalsh(latent)
    norm=float(np.linalg.norm(latent,2))
    margin=tolerance*norm
    result.update(latent=latent.tolist(),eigenvalues=eigen.tolist(),spectral_norm=norm,
        numeric_margin=margin,minimum_entry=float(latent.min()),normalized_residual=residual,
        prediction=prediction.tolist(),factor=None)
    if residual>tolerance:
        return dict(result,status='linear_residual_UNKNOWN')
    if eigen[0]<-margin:
        return dict(result,status='latent_indefinite_REJECTED')
    if latent.min()<-margin:
        return dict(result,status='negative_entry_REJECTED_for_positive_factors')
    try:
        factor=np.linalg.cholesky(latent)
    except np.linalg.LinAlgError:
        return dict(result,status='Cholesky_UNKNOWN')
    error=float(np.linalg.norm(factor@factor.T-latent,2)/norm)
    result.update(Cholesky=factor.tolist(),factor_error=error)
    if np.min(factor)<0 or error>tolerance:
        return dict(result,status='nonnegative_factor_UNKNOWN')
    bound=float(1/max(np.sum(factor,axis=1))**2)
    result.update(status='nonnegative_factor_CERTIFIED',factor=factor.tolist(),
        rate_selected=False,
        existence_upper_bound=bound/(1+bound) if family=='variance_factors' else bound,
        existence_parameter='common_Bernoulli_p' if family=='variance_factors' else 'common_Poisson_lambda_per_frame')
    return result
