#include "fft.h"
#include <math.h>
#define PF_PI 3.14159265358979323846
void pf_fft_init(PfFft *p) {
    unsigned i;
    for(i=0;i<PF_FFT;++i) {
        unsigned x=i,r=0,n;
        for(n=PF_FFT;n>1;n>>=1){r=(r<<1)|(x&1);x>>=1;}p->reverse[i]=r;
    }
    for(i=0;i<PF_FFT/2;++i){double a=-2*PF_PI*i/PF_FFT;p->root[i].re=cos(a);p->root[i].im=sin(a);}
}
void pf_fft(const PfFft *p,PfComplex v[PF_FFT],int inverse) {
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
}
