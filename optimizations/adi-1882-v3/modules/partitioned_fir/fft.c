#include "fft.h"
#include <math.h>
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX) && defined(VSL_ADSP_21569)
#include <filter.h>
#include <string.h>
#include "dsp_support/storage.h"
#pragma align 8
VSL_SECTION(VSL_L1_STATE)
static complex_float pf_fft_temporary[PF_FFT];
#endif
#define PF_PI 3.14159265358979323846f
void pf_fft_init(PfFft *p) {
    unsigned i;
    for(i=0;i<PF_FFT;++i) {
        unsigned x=i,r=0,n;
        for(n=PF_FFT;n>1;n>>=1){r=(r<<1)|(x&1);x>>=1;}p->reverse[i]=r;
    }
    for(i=0;i<PF_FFT/2;++i){float a=-2*PF_PI*i/PF_FFT;p->root[i].re=cosf(a);p->root[i].im=sinf(a);}
}
void pf_fft(const PfFft *p,PfComplex v[PF_FFT],int inverse) {
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX) && defined(VSL_ADSP_21569)
    /* ADI's SIMD FFT retains all 512 points and original FIR partitions.
       Its butterfly order changes FP32 rounding, so use the opt-in path only.
       Input, temporary and returned result may alias as documented by ADI. */
    complex_float *result;
    (void)p;
    result=inverse?ifft512((complex_float *)(void *)v,pf_fft_temporary):
                   cfft512((complex_float *)(void *)v,pf_fft_temporary);
    if((void *)result!=(void *)v)memcpy(v,result,sizeof(PfComplex)*PF_FFT);
#else
    unsigned i,size;
    for(i=0;i<PF_FFT;++i)if(i<p->reverse[i]){PfComplex t=v[i];v[i]=v[p->reverse[i]];v[p->reverse[i]]=t;}
    for(size=2;size<=PF_FFT;size<<=1) {
        unsigned start,half=size/2,step=PF_FFT/size;
        for(start=0;start<PF_FFT;start+=size)for(i=0;i<half;++i) {
            PfComplex w=p->root[i*step],a=v[start+i],b=v[start+i+half],z;
            if(inverse)w.im=-w.im;
            z.re=b.re*w.re-b.im*w.im;z.im=b.re*w.im+b.im*w.re;
            v[start+i].re=a.re+z.re;v[start+i].im=a.im+z.im;
            v[start+i+half].re=a.re-z.re;v[start+i+half].im=a.im-z.im;
        }
    }
    if(inverse)for(i=0;i<PF_FFT;++i){v[i].re/=PF_FFT;v[i].im/=PF_FFT;}
#endif
}
