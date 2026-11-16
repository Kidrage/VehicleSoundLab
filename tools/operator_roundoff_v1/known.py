"""Independent rational controls for both new reduction implementations."""
from fractions import Fraction
import numpy as np
from . import compensated,exact_dyadic


def qualify():
    rng=np.random.default_rng(2026111701);cases=[]
    vectors=[('lost_one',np.array([1e16,1.,-1e16]),np.ones(3)),
        ('zero',np.zeros(5),np.ones(5)),('signed_zero',np.array([-0.,0.]),np.array([1.,-1.])),
        ('exact_product_cancellation',np.array([1.+2.**-27,1.,-2.**-54]),np.array([1.-2.**-27,-1.,-1.]))]
    for n in (1,7,33,257):
        a=np.ldexp(rng.uniform(-1,1,n),rng.integers(-100,100,n))
        b=np.ldexp(rng.uniform(-1,1,n),rng.integers(-100,100,n))
        vectors.append(('mixed_'+str(n),a,b))
        vectors.append(('cancel_'+str(n),np.r_[a,-a,1.],np.r_[b,b,1.]))
    max_ulp=0.
    for label,a,b in vectors:
        exact=sum((Fraction.from_float(float(x))*Fraction.from_float(float(y)) for x,y in zip(a,b)),Fraction())
        expected=float(exact);value=compensated.dot(a,b);independent=exact_dyadic.dot(a,b)
        assert independent==expected
        ulp=abs(np.spacing(expected)) if expected else np.nextafter(0.,1.)
        distance=abs(value-expected)/ulp;assert distance<=1.,(label,distance)
        max_ulp=max(max_ulp,distance);cases.append(dict(label=label,elements=len(a),compensated_ULP_error=distance))
    # The exact audit path supports subnormals; the split-product path rejects
    # them instead of silently applying its normal-product theorem there.
    tiny=np.array([np.nextafter(0.,1.)]);assert exact_dyadic.dot(tiny,np.ones(1))==tiny[0]
    rejects=[]
    for label,a,b in (('too_small',tiny,np.ones(1)),('too_large',np.array([2.**401]),np.ones(1)),
        ('nonfinite',np.array([np.nan]),np.ones(1)),('complex',np.array([1j]),np.ones(1))):
        try:compensated.dot(a,b)
        except ValueError:rejects.append(label)
        else:raise AssertionError('Unsupported product admitted: '+label)
    return dict(passed=True,cases=cases,maximum_ULP_error=max_ulp,rejections=rejects,
        exact_integer_audit_subnormal_control_passed=True,no_longdouble_precision_assumption=True)
