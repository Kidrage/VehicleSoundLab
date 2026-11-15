"""Lexicographic inverse-CDF density and P-gradient LPs, fixed circular moment."""
import numpy as np
import warnings
from decimal import Decimal, localcontext
from scipy.optimize import linprog, OptimizeWarning
from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack


def system(product, row_mass, moments, column_mass, target, moment_allowance):
    rows, cells = len(product), len(moments)
    interior = cells-1
    if cells<2 or rows<1 or np.any(row_mass<=0) or np.any(column_mass<=0):
        raise ValueError('Positive row/cell masses and at least two cells are required')
    n = rows*interior
    ridx=[];cidx=[];value=[]
    for i in range(rows):
        for j in range(cells):
            if j<interior:ridx.append(i*cells+j);cidx.append(i*interior+j);value.append(1.)
            if j>0:ridx.append(i*cells+j);cidx.append(i*interior+j-1);value.append(-1.)
    delta=coo_matrix((value,(ridx,cidx)),shape=(rows*cells,n)).tocsr()
    end=np.tile(np.r_[np.zeros(interior),1.],rows)
    marginal=coo_matrix((np.repeat(row_mass,interior),
        (np.tile(np.arange(interior),rows),np.arange(n))),shape=(interior,n)).tocsr()
    mean=np.dot(product,row_mass);centered=(product-mean)*row_mass
    coefficient=(centered[:,None]*(moments[:-1]-moments[1:])[None,:]).ravel()
    residual=target-mean*np.dot(column_mass,moments)-centered.sum()*moments[-1]
    matrix=[];rhs=[];allowances=[];scales=[];active=[]
    for component,goal in [(coefficient.real,residual.real),(coefficient.imag,residual.imag)]:
        scale=np.sum(abs(component));scales.append(float(scale))
        if scale==0:
            if abs(goal)>moment_allowance:raise ValueError('Fixed marginal cannot attain the target moment')
            active.append(False)
        else:
            active.append(True);matrix.append(csr_matrix(component[None,:]/scale));rhs.append(goal/scale);allowances.append(moment_allowance/scale)
    moment_matrix=vstack(matrix).tocsr() if matrix else csr_matrix((0,n))
    return dict(delta=delta,end=end,equality=marginal,rhs=np.cumsum(column_mass)[:-1],
                moment_matrix=moment_matrix,moment_rhs=np.array(rhs),moment_allowances=np.array(allowances),
                rows=rows,cells=cells,n=n,moment_scales=np.array(scales),active=np.array(active))


def run_lp(s, inequality, bound, objective, last_upper, tolerance):
    equality=hstack([s['equality'],csr_matrix((len(s['rhs']),1))]).tocsr()
    limits=[(0,1)]*s['n']+[(0,last_upper)]
    moment=hstack([s['moment_matrix'],csr_matrix((len(s['moment_rhs']),1))]).tocsr()
    inequality=vstack([inequality,moment,-moment]).tocsr()
    bound=np.r_[bound,s['moment_rhs']+s['moment_allowances'],-s['moment_rhs']+s['moment_allowances']]
    # HiGHS defaults to dropping |a|<1e-9. Two2.917e-10 coefficients in the
    # frozen source produced a1.2e-3 dual defect despite feasible primal output.
    # Forward the documented native precision option; retain canonical matrices
    # for strict independent certificates rather than certifying a truncated LP.
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='Unrecognized options detected:.*small_matrix_value.*',category=OptimizeWarning)
        result=linprog(objective,A_ub=inequality,b_ub=bound,A_eq=equality,b_eq=s['rhs'],bounds=limits,
            method='highs',options={'primal_feasibility_tolerance':tolerance,'dual_feasibility_tolerance':tolerance,
                                    'small_matrix_value':1e-12})
    if not result.success:raise RuntimeError(f'LP status{result.status}: {result.message}')
    interior=result.x[:-1].reshape(s['rows'],s['cells']-1)
    cdf=np.column_stack([np.zeros(s['rows']),interior,np.ones(s['rows'])])
    reduced=objective-equality.T@result.eqlin.marginals-inequality.T@result.ineqlin.marginals
    finite_upper=np.r_[np.ones(s['n']),0 if last_upper is None else last_upper]
    dual=np.dot(s['rhs'],result.eqlin.marginals)+np.dot(bound,result.ineqlin.marginals)+np.dot(finite_upper,result.upper.marginals)
    # Near an active density boundary, large signed dual terms can cancel down
    # to an O(1) objective. Preserve the float64 diagnostic but evaluate the
    # certificate gap with high-precision products and accumulation, not a
    # relaxed gate. This is offline fitting, not a realtime decimal kernel.
    with localcontext() as context:
        context.prec=100
        exact_dual=Decimal(0)
        for rhs,multipliers in [(s['rhs'],result.eqlin.marginals),
                                (bound,result.ineqlin.marginals),(finite_upper,result.upper.marginals)]:
            exact_dual+=sum((Decimal.from_float(float(a))*Decimal.from_float(float(b))
                            for a,b in zip(rhs,multipliers)),Decimal(0))
        accurate_gap=float(Decimal.from_float(float(result.fun))-exact_dual)
    return dict(cdf=cdf,x=result.x,equality_dual=result.eqlin.marginals,
        inequality_dual=result.ineqlin.marginals,lower_dual=result.lower.marginals,upper_dual=result.upper.marginals,
        objective=float(result.fun),primal_dual_gap=accurate_gap,
        primal_dual_gap_raw_float64=float(result.fun-dual),
        scaled_equality_error=float(abs(equality@result.x-s['rhs']).max()),
        scaled_inequality_error=float(max(0,np.max(inequality@result.x-bound))),
        stationarity_error=float(abs(reduced-result.lower.marginals-result.upper.marginals).max()),
        small_matrix_value=1e-12)


def optimize(product,row_mass,moments,column_mass,target,low,high,knots,floor,tolerance,moment_allowance=1e-9):
    s=system(product,row_mass,moments,column_mass,target,moment_allowance)
    width=high-low
    if np.max(width)<=0:
        raise ValueError('Fixed phase has no finite density objective; use its exact constant decoder')
    floor_bound=s['end']-np.tile(floor*column_mass,s['rows'])
    base=hstack([-s['delta'],csr_matrix((len(s['end']),1))]).tocsr()
    density=hstack([-s['delta'],csr_matrix(np.tile(width,s['rows'])[:,None])]).tocsr()
    objective=np.r_[np.zeros(s['n']),-1.]
    first=run_lp(s,vstack([base,density]).tocsr(),np.r_[floor_bound,s['end']],objective,None,tolerance)
    kappa=float(first['x'][-1])
    required=max(0,kappa-max(2e-10,abs(kappa)*1e-8))
    if s['rows']>1:
        gradient=np.max(abs(np.diff(first['cdf'],axis=0))/np.diff(knots)[:,None])
    else:gradient=0.
    scale=max(1.,float(gradient))
    lower=np.tile(np.maximum(floor*column_mass,required*width),s['rows'])
    constraints=[base];bounds=[s['end']-lower]
    ri=[];ci=[];vv=[];bb=[];index=0
    for i,gap in enumerate(np.diff(knots)):
        normalizer=max(1.,scale*gap)
        for j in range(s['cells']-1):
            for sign in (1.,-1.):
                ri.extend([index]*3);ci.extend([i*(s['cells']-1)+j,(i+1)*(s['cells']-1)+j,s['n']])
                vv.extend([-sign/normalizer,sign/normalizer,-scale*gap/normalizer]);bb.append(0.);index+=1
    if index:
        constraints.append(coo_matrix((vv,(ri,ci)),shape=(index,s['n']+1)).tocsr());bounds.append(np.array(bb))
    second=run_lp(s,vstack(constraints).tocsr(),np.concatenate(bounds),
                  np.r_[np.zeros(s['n']),1.],1.,tolerance)
    return dict(density=first,variation=second,kappa=kappa,kappa_required=required,
                gradient_scale=scale,moment_scales=s['moment_scales'],moment_active=s['active'])
