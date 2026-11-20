#ifndef VSL_DNA_ATLAS_WAVETABLE_H
#define VSL_DNA_ATLAS_WAVETABLE_H
/* Private implementation included after magnitude() in voice.c.
   Opt-in approximation for the single serialized DSP engine with an attached
   sample cache. Other voices continue using the original sample sum.
   Every harmonic, anchor, texture draw and phase update is retained. Only the
   coefficient-to-wave conversion uses a 32-sample control grid (0.667 ms),
   followed by a crossfade and cubic phase interpolation. This is not bit exact.
   The two packed channels share an inverse FFT, not a mono projection.
   Static scratch is not reentrant, matching VSL_DSP_STATIC's single engine. */
#include "dsp_support/storage.h"
#ifdef VSL_ADSP_21569
#include <filter.h>
typedef complex_float WtComplex;
#else
typedef struct {float re,im;} WtComplex;
#endif
#define WT_SIZE 2048
#ifndef VSL_DSP_WT_HOP
#define VSL_DSP_WT_HOP 32
#endif
#if VSL_DSP_WT_HOP < 1 || (VSL_DSP_WT_HOP & (VSL_DSP_WT_HOP-1))
#error VSL_DSP_WT_HOP must be a power of two
#endif
VSL_SECTION(VSL_L2_HISTORY)
static WtComplex wt_main[2][WT_SIZE];
VSL_SECTION(VSL_L2_HISTORY)
static WtComplex wt_body[2][WT_SIZE];
#ifdef VSL_ADSP_21569
#pragma align 8
#endif
VSL_SECTION(VSL_L1_STATE)
static WtComplex wt_work[WT_SIZE];
#ifdef VSL_ADSP_21569
#pragma align 8
#endif
VSL_SECTION(VSL_L1_STATE)
static WtComplex wt_temp[WT_SIZE];
static const SaVoice *wt_owner;
static const SaBank *wt_bank;
static const SaSampleCache *wt_cache;
static uint64_t wt_last_frame;
static int wt_ready;
static int wt_has_body;
static void wt_inverse(WtComplex *output){
#ifdef VSL_ADSP_21569
    WtComplex *result=ifft2048(wt_work,wt_temp);
    memcpy(output,result,sizeof wt_work);
#else
    unsigned i,j,size;
    static WtComplex roots[WT_SIZE/2];static int roots_ready;
    if(!roots_ready){for(i=0;i<WT_SIZE/2;++i){float a=2*PI*i/WT_SIZE;roots[i].re=cosf(a);roots[i].im=sinf(a);}roots_ready=1;}
    for(i=1,j=0;i<WT_SIZE;++i){
        unsigned bit=WT_SIZE>>1;
        for(;j&bit;bit>>=1)j^=bit;j^=bit;
        if(i<j){WtComplex t=wt_work[i];wt_work[i]=wt_work[j];wt_work[j]=t;}
    }
    for(size=2;size<=WT_SIZE;size<<=1){unsigned half=size>>1,start;
        for(start=0;start<WT_SIZE;start+=size)for(i=0;i<half;++i){
            WtComplex root=roots[i*(WT_SIZE/size)],a=wt_work[start+i],b=wt_work[start+i+half],z;
            z.re=b.re*root.re-b.im*root.im;z.im=b.re*root.im+b.im*root.re;
            wt_work[start+i].re=a.re+z.re;wt_work[start+i].im=a.im+z.im;
            wt_work[start+i+half].re=a.re-z.re;wt_work[start+i+half].im=a.im-z.im;
        }
    }
    for(i=0;i<WT_SIZE;++i){output[i].re=wt_work[i].re/WT_SIZE;output[i].im=wt_work[i].im/WT_SIZE;}
#endif
}
static float wt_cubic(float a,float b,float c,float d,float u){
    return b+.5f*u*(c-a+u*(2*a-5*b+4*c-d+u*(3*(b-c)+d-a)));
}
static void wt_read(const WtComplex *table,unsigned i,float u,float out[2]){
    const WtComplex *a=table+((i-1)&(WT_SIZE-1)),*b=table+i;
    const WtComplex *c=table+((i+1)&(WT_SIZE-1)),*d=table+((i+2)&(WT_SIZE-1));
    out[0]=wt_cubic(a->re,b->re,c->re,d->re,u);
    out[1]=wt_cubic(a->im,b->im,c->im,d->im,u);
}
static void wt_build(const SaVoice *v,unsigned lo,unsigned hi,float blend,
                     const HbBand *band,const float *shape,float amount,unsigned target){
    const SaBank *b=v->bank;unsigned h,c,kind;
    float coefficients[SD_MAX_HARMONICS][4],weights[SD_MAX_HARMONICS];
    memset(coefficients,0,sizeof coefficients);memset(weights,0,sizeof weights);
    for(h=0;h<b->harmonics;++h){
        float hz=(h+1)*v->root_hz,aa=1;
        if(hz>=21600)break;
        if(hz>19200){float x=(hz-19200)/2400;aa=1-x*x*(3-2*x);}
        weights[h]=band?hb_band_weight_inline(band,hz):0;
        for(c=0;c<2;++c){
            float mag=magnitude(b,v->sample_cache,v->texture,lo,h,c,v->detail,v->texture[lo].fraction);
            const float *unit=v->sample_cache&&lo<v->sample_cache->count?v->sample_cache->unit[lo][h]:b->unit[lo][h];
            float re=unit[2*c],im=unit[2*c+1];
            if(lo!=hi){
                float phase=b->phase[lo][h][c]+blend*b->delta[lo][h][c];
                mag+=blend*(magnitude(b,v->sample_cache,v->texture,hi,h,c,v->detail,v->texture[hi].fraction)-mag);
                if(blend==1){re=b->unit[hi][h][2*c];im=b->unit[hi][h][2*c+1];}
                else if(blend!=0){re=sa_bank_sine(b,phase+PI/2);im=sa_bank_sine(b,phase);}
            }
            mag*=aa;if(shape&&amount>0)mag*=1+amount*(shape[h]-1);
            coefficients[h][2*c]=mag*re;coefficients[h][2*c+1]=mag*im;
        }
    }
    for(kind=0;kind<(band?2u:1u);++kind){
        memset(wt_work,0,sizeof wt_work);
        for(h=0;h<b->harmonics;++h){
            const float *z=coefficients[h];float scale=(WT_SIZE*.5f)*(kind?weights[h]:1);
            unsigned positive=h+1,negative=WT_SIZE-positive;
            wt_work[positive].re=scale*(z[0]-z[3]);wt_work[positive].im=scale*(z[1]+z[2]);
            wt_work[negative].re=scale*(z[0]+z[3]);wt_work[negative].im=scale*(-z[1]+z[2]);
        }
        wt_inverse(kind?wt_body[target]:wt_main[target]);
    }
}
static void wt_sample(const SaVoice *v,unsigned lo,unsigned hi,float blend,
                      float out[2],float body[2],const HbBand *band,const float *shape,float amount){
    unsigned current=(unsigned)(v->frame/VSL_DSP_WT_HOP)&1,previous=current^1,c;
    float position=v->phase*(WT_SIZE/(2*PI));
    unsigned index=((unsigned)position)&(WT_SIZE-1);
    float fraction=position-(unsigned)position,a[2],b[2];
    float u=(float)(v->frame&(VSL_DSP_WT_HOP-1))/VSL_DSP_WT_HOP;
    if(wt_owner!=v||wt_bank!=v->bank||wt_cache!=v->sample_cache||wt_has_body!=(body!=NULL)||!v->frame||v->frame!=wt_last_frame+1)wt_ready=0;
    if(!wt_ready||!(v->frame&(VSL_DSP_WT_HOP-1))){
        wt_build(v,lo,hi,blend,band,shape,amount,current);
        if(!wt_ready){
            memcpy(wt_main[previous],wt_main[current],sizeof wt_main[current]);
            memcpy(wt_body[previous],wt_body[current],sizeof wt_body[current]);wt_ready=1;
        }
    }
    wt_read(wt_main[previous],index,fraction,a);wt_read(wt_main[current],index,fraction,b);
    for(c=0;c<2;++c)out[c]=a[c]+u*(b[c]-a[c]);
    if(body){
        wt_read(wt_body[previous],index,fraction,a);wt_read(wt_body[current],index,fraction,b);
        for(c=0;c<2;++c)body[c]=a[c]+u*(b[c]-a[c]);
    }
    wt_owner=v;wt_bank=v->bank;wt_cache=v->sample_cache;wt_last_frame=v->frame;wt_has_body=body!=NULL;
}
#endif
