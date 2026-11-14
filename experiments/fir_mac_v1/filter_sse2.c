#include "partitioned_fir/filter.h"
#include "mac.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
struct PfKernel {PfFft plan;unsigned parts;PfComplex *spectrum;};
struct PfState {
    const PfKernel *kernel;unsigned ring;
    PfComplex *history,work[PF_FFT],sum[PF_FFT];double overlap[PF_BLOCK];
};
PfKernel *pf_kernel_create(const double *taps,unsigned count) {
    PfKernel *k;unsigned i,p;
    if(!taps||!count||count>PF_MAX_TAPS)return NULL;
    /* Bounded length/coefficient/input keep every FFT/product/sum far below
       DBL_MAX. No extra spectral/L1 restriction is needed for this purpose. */
    for(i=0;i<count;++i)if(!isfinite(taps[i])||fabs(taps[i])>64)return NULL;
    k=calloc(1,sizeof *k);if(!k)return NULL;k->parts=(count+PF_BLOCK-1)/PF_BLOCK;
    k->spectrum=calloc((size_t)k->parts*PF_FFT,sizeof *k->spectrum);
    if(!k->spectrum){free(k);return NULL;}pf_fft_init(&k->plan);
    for(p=0;p<k->parts;++p) {
        PfComplex *block=k->spectrum+(size_t)p*PF_FFT;
        for(i=0;i<PF_BLOCK&&p*PF_BLOCK+i<count;++i)block[i].re=taps[p*PF_BLOCK+i];
        pf_fft(&k->plan,block,0);
    }
    return k;
}
void pf_kernel_destroy(PfKernel *k){if(k){free(k->spectrum);free(k);}}
PfState *pf_state_create(const PfKernel *k) {
    PfState *s;if(!k)return NULL;s=calloc(1,sizeof *s);if(!s)return NULL;
    s->history=calloc((size_t)k->parts*PF_FFT,sizeof *s->history);
    if(!s->history){free(s);return NULL;}s->kernel=k;return s;
}
void pf_state_destroy(PfState *s){if(s){free(s->history);free(s);}}
int pf_filter_block(PfState *s,const double *input,double *output) {
    unsigned n,p;const PfKernel *k;PfComplex *slot;
    if(!s||!input||!output)return 0;
    for(n=0;n<PF_BLOCK;++n)if(!isfinite(input[n])||fabs(input[n])>1e100)return 0;
    k=s->kernel;memset(s->work,0,sizeof s->work);memset(s->sum,0,sizeof s->sum);
    for(n=0;n<PF_BLOCK;++n)s->work[n].re=input[n];
    pf_fft(&k->plan,s->work,0);slot=s->history+(size_t)s->ring*PF_FFT;
    memcpy(slot,s->work,sizeof s->work);
    for(p=0;p<k->parts;++p) {
        unsigned index=(s->ring+k->parts-p)%k->parts;
        const PfComplex *x=s->history+(size_t)index*PF_FFT,*h=k->spectrum+(size_t)p*PF_FFT;
        pf_mac_add(s->sum,x,h);
    }
    pf_fft(&k->plan,s->sum,1);
    for(n=0;n<PF_BLOCK;++n){output[n]=s->sum[n].re+s->overlap[n];s->overlap[n]=s->sum[n+PF_BLOCK].re;}
    s->ring=(s->ring+1)%k->parts;return 1;
}
