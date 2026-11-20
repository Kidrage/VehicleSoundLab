#include "modules/partitioned_fir/filter.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "dsp_support/storage.h"
/* Real inputs/kernels have conjugate spectra. Keep the nonnegative half,
   preserve partition summation order, then rebuild the inverse FFT input. */
#define PF_BINS (PF_FFT/2+1)
/* Independent frequency bins can use the two SIMD lanes without changing
   the partition accumulation order. Pad each plane to keep it 8-byte aligned. */
#define PF_PADDED_BINS (PF_BINS+1)
typedef struct {float re[PF_PADDED_BINS],im[PF_PADDED_BINS];} PfBins;
struct PfKernel {
#ifdef VSL_DSP_STATIC
    const PfFft *plan;
#else
    PfFft plan;
#endif
    unsigned parts;PfBins *spectrum;
};
struct PfState {
    const PfKernel *kernel;unsigned ring;
    PfBins *history;
#ifndef VSL_DSP_STATIC
    PfComplex work[PF_FFT],sum[PF_FFT];
    PfBins accum;
#endif
    float overlap[PF_BLOCK];
};
#ifdef VSL_DSP_STATIC
/* DSP block processing is serialized. Only history/overlap persist per FIR;
   both FFT arrays are overwritten before use on every call. */
typedef struct {PfComplex work[PF_FFT],sum[PF_FFT];PfBins accum;} PfScratch;
#ifdef VSL_ADSP_21569
#pragma align 8
#endif
VSL_SECTION(VSL_L1_STATE)
static PfScratch pf_scratch;
/* Keep the plan in block 0 so block 1 can reserve 128 KiB for DM cache.
   The per-voice buffers still fit in its remaining 64 KiB of L1 RAM. */
VSL_SECTION(VSL_L1_STATE)
static PfFft pf_plan;
static int pf_plan_ready;
#define PF_WORK(s) (pf_scratch.work)
#define PF_SUM(s) (pf_scratch.sum)
#define PF_ACCUM(s) (pf_scratch.accum)
#define PF_PLAN(k) ((k)->plan)
#else
#define PF_WORK(s) ((s)->work)
#define PF_SUM(s) ((s)->sum)
#define PF_ACCUM(s) ((s)->accum)
#define PF_PLAN(k) (&(k)->plan)
#endif
typedef struct {PfBins data[(PF_MAX_TAPS+PF_BLOCK-1)/PF_BLOCK];} PfBuffer;
VSL_STORAGE(pf_kernels,PfKernel,VSL_DSP_FIR_SLOTS,VSL_L1_VOICE)
VSL_STORAGE(pf_states,PfState,VSL_DSP_FIR_SLOTS,VSL_L1_STATE)
#ifdef VSL_ADSP_21569
#pragma align 8
#endif
VSL_STORAGE(pf_spectra,PfBuffer,VSL_DSP_FIR_SLOTS,VSL_L1_FIR)
#ifdef VSL_ADSP_21569
#pragma align 8
#endif
VSL_STORAGE(pf_histories,PfBuffer,VSL_DSP_FIR_SLOTS,VSL_L1_FIR)
static void store_bins(PfBins *to,const PfComplex *from){
    unsigned n;for(n=0;n<PF_BINS;++n){to->re[n]=from[n].re;to->im[n]=from[n].im;}
}
static void mac_bins(const float *restrict xr,const float *restrict xi,
                     const float *restrict hr,const float *restrict hi,
                     float *restrict sr,float *restrict si){
    unsigned n;
#ifdef VSL_ADSP_21569
#pragma SIMD_for
#endif
    for(n=0;n<PF_BLOCK;++n){
        sr[n]+=xr[n]*hr[n]-xi[n]*hi[n];
        si[n]+=xr[n]*hi[n]+xi[n]*hr[n];
    }
    /* The Nyquist bin remains scalar; SIMD never reads a following buffer. */
    sr[PF_BLOCK]+=xr[PF_BLOCK]*hr[PF_BLOCK]-xi[PF_BLOCK]*hi[PF_BLOCK];
    si[PF_BLOCK]+=xr[PF_BLOCK]*hi[PF_BLOCK]+xi[PF_BLOCK]*hr[PF_BLOCK];
}
PfKernel *pf_kernel_create(const float *taps,unsigned count) {
    PfKernel *k;PfBuffer *buffer;unsigned i,p;PfComplex work[PF_FFT];
    if(!taps||!count||count>PF_MAX_TAPS)return NULL;
    /* Bounded length/coefficient/input keep every FFT/product/sum far below
       DBL_MAX. No extra spectral/L1 restriction is needed for this purpose. */
    for(i=0;i<count;++i)if(!isfinite(taps[i])||fabsf(taps[i])>64)return NULL;
    k=pf_kernels_acquire();if(!k)return NULL;k->parts=(count+PF_BLOCK-1)/PF_BLOCK;
    buffer=pf_spectra_acquire();k->spectrum=buffer?buffer->data:NULL;
    if(!k->spectrum){pf_kernels_release(k);return NULL;}
#ifdef VSL_DSP_STATIC
    if(!pf_plan_ready){pf_fft_init(&pf_plan);pf_plan_ready=1;}k->plan=&pf_plan;
#else
    pf_fft_init(&k->plan);
#endif
    for(p=0;p<k->parts;++p) {
        memset(work,0,sizeof work);
        for(i=0;i<PF_BLOCK&&p*PF_BLOCK+i<count;++i)work[i].re=taps[p*PF_BLOCK+i];
        pf_fft(PF_PLAN(k),work,0);
        store_bins(k->spectrum+p,work);
    }
    return k;
}
void pf_kernel_destroy(PfKernel *k){if(k){pf_spectra_release((PfBuffer *)(void *)k->spectrum);pf_kernels_release(k);}}
PfState *pf_state_create(const PfKernel *k) {
    PfState *s;PfBuffer *buffer;if(!k)return NULL;s=pf_states_acquire();if(!s)return NULL;
    buffer=pf_histories_acquire();s->history=buffer?buffer->data:NULL;
    if(!s->history){pf_states_release(s);return NULL;}s->kernel=k;return s;
}
void pf_state_destroy(PfState *s){if(s){pf_histories_release((PfBuffer *)(void *)s->history);pf_states_release(s);}}
int pf_filter_block(PfState *s,const float *input,float *output) {
    unsigned n,p,index;const PfKernel *k;PfBins *slot;
    if(!s||!input||!output)return 0;
    for(n=0;n<PF_BLOCK;++n)if(!isfinite(input[n])||fabsf(input[n])>1e20f)return 0;
    k=s->kernel;memset(PF_WORK(s),0,sizeof PF_WORK(s));memset(PF_SUM(s),0,sizeof PF_SUM(s));
    memset(&PF_ACCUM(s),0,sizeof PF_ACCUM(s));
    for(n=0;n<PF_BLOCK;++n)PF_WORK(s)[n].re=input[n];
    pf_fft(PF_PLAN(k),PF_WORK(s),0);slot=s->history+s->ring;
    store_bins(slot,PF_WORK(s));index=s->ring;
    for(p=0;p<k->parts;++p) {
        const PfBins *x=s->history+index,*h=k->spectrum+p;
        mac_bins(x->re,x->im,h->re,h->im,PF_ACCUM(s).re,PF_ACCUM(s).im);
        index=index?index-1:k->parts-1;
    }
    for(n=0;n<PF_BINS;++n){PF_SUM(s)[n].re=PF_ACCUM(s).re[n];PF_SUM(s)[n].im=PF_ACCUM(s).im[n];}
    for(n=1;n<PF_FFT/2;++n){PF_SUM(s)[PF_FFT-n].re=PF_SUM(s)[n].re;PF_SUM(s)[PF_FFT-n].im=-PF_SUM(s)[n].im;}
    pf_fft(PF_PLAN(k),PF_SUM(s),1);
    for(n=0;n<PF_BLOCK;++n){output[n]=PF_SUM(s)[n].re+s->overlap[n];s->overlap[n]=PF_SUM(s)[n+PF_BLOCK].re;}
    if(++s->ring==k->parts)s->ring=0;return 1;
}

