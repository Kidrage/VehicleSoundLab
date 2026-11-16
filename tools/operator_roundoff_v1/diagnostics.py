"""Read-only complete small-known decomposition; no new solver or source fit."""
import numpy as np
from constrained_source_operator_v1 import oracle
from .compensated import matvec


def describe(error,reference):
    error,reference=np.asarray(error),np.asarray(reference)
    peak=float(np.max(np.abs(reference)));absolute=float(np.max(np.abs(error)))
    norm=float(np.linalg.norm(reference));enorm=float(np.linalg.norm(error))
    return dict(reference_peak=peak,error_peak=absolute,reference_norm=norm,error_norm=enorm,
        peak_relative=absolute/peak if peak else (0. if not np.count_nonzero(error) else None),
        norm_relative=enorm/norm if norm else (0. if not np.count_nonzero(error) else None))


def variants(z):
    """Separate rounded hat evaluation and one-column FFT carrier evaluation.

    These are specified finite-grid counterfactuals, not new audio methods.
    """
    frames=int(z['frames']);p=z['positions'];orders=z['orders'];n=np.arange(frames)
    m,h=len(p),len(orders);size=4*m*h;half=size//2
    hats=np.zeros((m,frames))
    for j in range(m-1):
        samples=np.arange(p[j],p[j+1]+1)
        hats[j,samples]=(p[j+1]-samples)/(p[j+1]-p[j])
        hats[j+1,samples]=(samples-p[j])/(p[j+1]-p[j])
    scalar=oracle.table(orders)[n%1024]
    cosine=[];negative_sine=[]
    for order in orders:
        bins=np.zeros(513,complex);bins[order]=1.
        cosine.append(np.fft.irfft(bins,n=1024)*512)
        bins[order]=1j;negative_sine.append(np.fft.irfft(bins,n=1024)*512)
    cos=np.asarray(cosine).T[n%1024];neg=np.asarray(negative_sine).T[n%1024]
    a=np.zeros((frames*2,size));b=np.zeros_like(a)
    for j in range(m):
        for k in range(h):
            for c in (0,1):
                index=(j*h+k)*2+c
                a[c::2,index]=hats[j]*scalar[:,k].real*z['scale'][k,0]
                a[c::2,index+half]=-hats[j]*scalar[:,k].imag*z['scale'][k,0]
                b[c::2,index]=hats[j]*cos[:,k]*z['scale'][k,0]
                b[c::2,index+half]=hats[j]*neg[:,k]*z['scale'][k,0]
    return a,b


def analyze(z):
    phi,b,groups,r=oracle.dense(z);x=z['x'];frames=int(z['frames'])
    saved=z['wave'];naive=(phi@x).reshape(frames,2);compensated=matvec(phi,x).reshape(frames,2)
    hat,carrier=variants(z);hat_wave=matvec(hat,x).reshape(frames,2);carrier_wave=matvec(carrier,x).reshape(frames,2)
    rows=oracle.target(z,naive);saved_rows=tuple(z['target_'+str(g)] for g in range(7))
    delta_rows=oracle.target(z,naive-saved)
    arrays=dict(dense_source_naive=naive,dense_source_compensated=compensated,
        declared_hat_source_compensated=hat_wave,fft_carrier_source_compensated=carrier_wave)
    report=dict(source=dict(naive=describe(naive-saved,saved),compensated=describe(compensated-saved,saved),
        declared_hats=describe(hat_wave-saved,saved),declared_hats_fft_carriers=describe(carrier_wave-saved,saved)),groups=[])
    for g in range(7):
        dense=groups[g]@x;accurate=matvec(groups[g],x)
        total=dense-saved_rows[g];source=rows[g]-saved_rows[g];column=dense-rows[g]
        observation=source-delta_rows[g];identity=total-(source+column)
        report['groups'].append(dict(group=g,total=describe(total,saved_rows[g]),
            source_evaluation_component=describe(source,saved_rows[g]),
            column_and_reduction_component=describe(column,saved_rows[g]),
            observation_subtraction_linearity=describe(observation,saved_rows[g]),
            compensated_dense=describe(accurate-saved_rows[g],saved_rows[g]),
            signed_decomposition_identity_error_peak=float(np.max(abs(identity)))))
        for key,value in (('dense',dense),('compensated',accurate),('total',total),('source',source),
            ('column',column),('observation',observation)):arrays['group_'+str(g)+'_'+key]=value
    residual=oracle.full(z,saved)-oracle.full(z,z['audio'])
    gradient_matrix=np.column_stack((b.T,r));gradient_rhs=np.r_[residual,x]
    gradient=matvec(gradient_matrix,gradient_rhs);naive_gradient=b.T@residual+r@x
    arrays.update(gradient_compensated=gradient,gradient_dense_naive=naive_gradient,objective_residual=residual)
    report['gradient']=dict(FFT_vs_compensated=describe(z['gradient']-gradient,gradient),
        dense_naive_vs_compensated=describe(naive_gradient-gradient,gradient),
        absolute_product_sum_max=float(np.max(np.abs(gradient_matrix)@np.abs(gradient_rhs))),
        reference_norm=float(np.linalg.norm(gradient)),
        operator_Frobenius_norm=float(np.linalg.norm(b)),residual_norm=float(np.linalg.norm(residual)),
        normalized_backward_discrepancy=float(np.linalg.norm(z['gradient']-gradient)/max(np.linalg.norm(b)*np.linalg.norm(residual)+np.linalg.norm(r)*np.linalg.norm(x),1e-300)),
        backward_number_is_diagnostic_not_replacement_for_original_check=True)
    return arrays,report
