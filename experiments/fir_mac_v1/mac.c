#include "mac.h"
#if !defined(PF_FORCE_SCALAR) && (defined(_M_X64) || defined(__SSE2__) || (defined(_M_IX86_FP) && _M_IX86_FP>=2))
#define PF_USE_SSE2 1
#include <emmintrin.h>
#endif
const char *pf_mac_backend(void) {
#ifdef PF_USE_SSE2
    return "SSE2";
#else
    return "scalar";
#endif
}
void pf_mac_add(PfComplex sum[PF_FFT],const PfComplex x[PF_FFT],const PfComplex h[PF_FFT]) {
    unsigned n;
#ifdef PF_USE_SSE2
    /* Two bins, independent lanes. Separate multiply/subtract/add retain the
       scalar rounding and partition summation order; never use FMA here. */
    for(n=0;n<PF_FFT;n+=2) {
        __m128d x0=_mm_loadu_pd(&x[n].re),x1=_mm_loadu_pd(&x[n+1].re);
        __m128d h0=_mm_loadu_pd(&h[n].re),h1=_mm_loadu_pd(&h[n+1].re);
        __m128d s0=_mm_loadu_pd(&sum[n].re),s1=_mm_loadu_pd(&sum[n+1].re);
        __m128d xr=_mm_unpacklo_pd(x0,x1),xi=_mm_unpackhi_pd(x0,x1);
        __m128d hr=_mm_unpacklo_pd(h0,h1),hi=_mm_unpackhi_pd(h0,h1);
        __m128d re=_mm_sub_pd(_mm_mul_pd(xr,hr),_mm_mul_pd(xi,hi));
        __m128d im=_mm_add_pd(_mm_mul_pd(xr,hi),_mm_mul_pd(xi,hr));
        re=_mm_add_pd(_mm_unpacklo_pd(s0,s1),re);
        im=_mm_add_pd(_mm_unpackhi_pd(s0,s1),im);
        _mm_storeu_pd(&sum[n].re,_mm_unpacklo_pd(re,im));
        _mm_storeu_pd(&sum[n+1].re,_mm_unpackhi_pd(re,im));
    }
#else
    for(n=0;n<PF_FFT;++n) {
        sum[n].re+=x[n].re*h[n].re-x[n].im*h[n].im;
        sum[n].im+=x[n].re*h[n].im+x[n].im*h[n].re;
    }
#endif
}
