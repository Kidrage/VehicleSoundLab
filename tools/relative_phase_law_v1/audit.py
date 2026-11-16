"""Independent full-entry reductions and scalar anchors for saved law evidence."""
import math
import numpy as np


def verify(data, rows, group_rows, meta, check):
    x, pc, residual, b = (data[key] for key in ('scores', 'pc', 'residual', 'basis'))
    n, d = x.shape
    # Sequential FP64 einsum avoids the producer matrix-multiply/BLAS path.
    def center(value):
        return value-np.array([math.fsum(value[:, j])/len(value) for j in range(value.shape[1])])
    xx = center(x)
    pp = center(np.einsum('nk,dk->nd', pc, b, optimize=False))
    rr = center(residual)
    def cov(a, v, lag):
        return np.einsum('ni,nj->ij', a[lag:], v[:n-lag], optimize=False)/(n-lag)
    c0 = cov(xx, xx, 0)
    scale = float(np.linalg.norm(c0)) or 1.
    trace = math.fsum(np.diag(c0))
    check('meta_C0', meta['empirical_C0_Frobenius'], np.linalg.norm(c0), scale)
    check('meta_trace', meta['empirical_feature_variance_trace'], trace, scale*d)
    if trace:
        check('meta_shared_trace_fraction', meta['shared_feature_variance_fraction'],
            math.fsum(np.diag(cov(pp, pp, 0)))/trace, 1.)
    else: assert meta['shared_feature_variance_fraction'] is None
    assert (meta['rows'],meta['features'],meta['shared_components']) == (n,d,len(data['rho']))
    assert len(rows) == len(data['lags']) and len(group_rows) == 16*len(rows)
    h = d//4
    group = dict(amplitude_L=list(range(0,2*h,2)), amplitude_R=list(range(1,2*h,2)),
        common_phase=list(range(2*h,3*h)), relative_phase=list(range(3*h,4*h)))
    anchors = sorted(set((0, h-1, h, 2*h-1, 2*h, 3*h-1, 3*h, d-1)))
    for at,lag in enumerate(map(int,data['lags'])):
        c = cov(xx,xx,lag)
        p, r = cov(pp,pp,lag), cov(rr,rr,lag)
        cross = cov(pp,rr,lag)+cov(rr,pp,lag)
        mp = np.einsum('ik,jk,k->ij',b,b,np.array([float(v)**lag for v in data['rho']]),optimize=False)
        mr = np.zeros((d,d))
        np.fill_diagonal(mr, [float(s)**2*float(v)**lag for s,v in zip(data['residual_std'],data['residual_rho'])])
        model = mp+mr
        pieces = np.stack((mp-p,mr-r,-cross))
        for key,value in (('observed',c),('model',model),('shared_observed',p),('residual_observed',r),
            ('shared_residual_cross_observed',cross),('error_components',pieces)):
            check(f'lag{lag}_all_entries_'+key, data[f'lag{lag}_{key}'], value, scale)
        for i in anchors:
            for j in anchors:
                direct = math.fsum(float(xx[t+lag,i])*float(xx[t,j]) for t in range(n-lag))/(n-lag)
                check(f'lag{lag}_scalar_cov_{i}_{j}', data[f'lag{lag}_observed'][i,j], direct, scale)
                direct = math.fsum(float(b[i,k])*float(b[j,k])*float(data['rho'][k])**lag for k in range(len(data['rho'])))
                if i == j: direct += float(data['residual_std'][i])**2*float(data['residual_rho'][i])**lag
                check(f'lag{lag}_scalar_law_{i}_{j}', data[f'lag{lag}_model'][i,j], direct, scale)
        check(f'lag{lag}_three_component_closure', pieces.sum(axis=0), model-c, scale)
        gram = np.empty((3,3))
        for i in range(3):
            for j in range(3): gram[i,j] = np.einsum('ij,ij->',pieces[i],pieces[j],optimize=False)
        check(f'lag{lag}_signed_Gram', data[f'lag{lag}_signed_Gram'], gram, scale**2)
        # Derivatives in JSON are from frozen bins, independent of rounding
        # between the BLAS and sequential-einsum paths above.
        observed, fitted = data[f'lag{lag}_observed'], data[f'lag{lag}_model']
        diff = fitted-observed
        skew = (observed-observed.T)/2
        frozen_pieces = data[f'lag{lag}_error_components']
        frozen_scale = float(meta['empirical_C0_Frobenius']) or 1.
        norm = lambda v: math.sqrt(math.fsum((np.asarray(v).ravel()**2)))/frozen_scale
        expected = dict(observed_norm_over_C0=norm(observed), model_norm_over_C0=norm(fitted),
            model_error_over_C0=norm(diff), observed_skew_over_C0=norm(skew),
            shared_error_over_C0=norm(frozen_pieces[0]), residual_error_over_C0=norm(frozen_pieces[1]),
            omitted_cross_error_over_C0=norm(frozen_pieces[2]),
            component_signed_Gram_over_C0_squared=data[f'lag{lag}_signed_Gram']/frozen_scale**2)
        row = rows[at]; assert row['lag_steps'] == lag
        for key,value in expected.items(): check(f'lag{lag}_JSON_'+key,row[key],value,1.)
        err2 = math.fsum((diff.ravel()**2))
        if err2:
            check(f'lag{lag}_JSON_skew_fraction',row['skew_fraction_of_observed_error_squared'],
                math.fsum((skew.ravel()**2))/err2,1.)
        else: assert row['skew_fraction_of_observed_error_squared'] is None
        # Frobenius orthogonality gives an exact lower bound for a symmetric
        # model against this finite observation, NOT population irreversibility.
        check(f'lag{lag}_symmetric_model',fitted,fitted.T,scale)
        check(f'lag{lag}_skew_geometry',math.fsum((diff.ravel()**2)),
            math.fsum((((diff+diff.T)/2).ravel()**2))+math.fsum((skew.ravel()**2)),scale**2)
        for entry in group_rows[16*at:16*(at+1)]:
            assert entry['lag_steps'] == lag
            ii, jj = group[entry['left']],group[entry['right']]
            for key,value in (('observed_RMS_per_entry',observed),('model_error_RMS_per_entry',diff)):
                values = value[np.ix_(ii,jj)]
                expected = math.sqrt(math.fsum(values.ravel()**2)/(len(ii)*len(jj)))
                check(f'lag{lag}_group_{entry["left"]}_{entry["right"]}_{key}',entry[key],expected,1.)
    diag = np.sum(b*b,axis=1)+data['residual_std']**2-np.diag(c0)
    check('meta_maximum_variance_error',meta['maximum_feature_variance_error'],abs(diag).max(),scale)
    return dict(full_entry_covariance_and_model_checked=True, scalar_anchor_indices=anchors,
        all_JSON_fields_and_signed_components_verified=True,
        comparison_gate=2e-11, finite_source_rows_not_physical_causal_evidence=True)
