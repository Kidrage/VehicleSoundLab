#include "voice.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f

static int valid(float hz,float d,float g) {
    return isfinite(hz)&&hz>=0&&hz<=1000&&isfinite(d)&&d>=0&&d<=1.3f&&isfinite(g)&&g>=0&&g<=1;
}
int sa_voice_init(SaVoice *v,const SaBank *b,uint64_t seed,float hz,float d,float g) {
    unsigned a;
    if (!v||!b||!b->count||b->count>SA_MAX_ANCHORS||!valid(hz,d,g)) return 0;
    memset(v,0,sizeof *v);v->bank=b;
    v->root_hz=v->root_target=hz;v->detail=v->detail_target=d;v->gain=v->gain_target=g;
    v->follow=1-expf(-1/(.018f*48000));
    for (a=0;a<b->count;++a) sd_texture_init(&v->texture[a],b->profile[a],seed);
    return 1;
}
void sa_voice_sample_cache(SaVoice *v,SaSampleCache *cache){
    unsigned a,h;if(!v)return;v->sample_cache=NULL;
    if(!cache||!v->bank)return;
    cache->count=v->bank->count<SA_CACHE_ANCHORS?v->bank->count:SA_CACHE_ANCHORS;
    for(a=0;a<cache->count;++a){
      for(h=0;h<v->bank->harmonics;++h){
        memcpy(cache->mean[a][h],v->bank->profile[a]->harmonic[h].mean,sizeof cache->mean[a][h]);
        memcpy(cache->unit[a][h],v->bank->unit[a][h],sizeof cache->unit[a][h]);
      }
      memcpy(cache->left[a],v->texture[a].left,sizeof cache->left[a]);
      memcpy(cache->right[a],v->texture[a].right,sizeof cache->right[a]);
      cache->updates[a]=v->texture[a].updates;
    }
    v->sample_cache=cache;
}
int sa_voice_set(SaVoice *v,float hz,float d,float g) {
    if (!v||!v->bank||!valid(hz,d,g)) return 0;
    v->root_target=hz;v->detail_target=d;v->gain_target=g;return 1;
}
#ifdef VSL_ADSP_21569
#pragma always_inline
#endif
static inline float magnitude(const SaBank *b,const SaSampleCache *cache,const SdTexture *textures,unsigned a,unsigned h,unsigned c,float detail,float fraction) {
    const SdTexture *t=&textures[a];
    const float *m,*left,*right;
    if(cache&&a<cache->count){m=cache->mean[a][h];left=cache->left[a][h];right=cache->right[a][h];}
    else{m=b->profile[a]->harmonic[h].mean;left=t->left[h];right=t->right[h];}
    float re=m[2*c]+detail*(left[2*c]+fraction*(right[2*c]-left[2*c]));
    float im=m[2*c+1]+detail*(left[2*c+1]+fraction*(right[2*c+1]-left[2*c+1]));
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    /* Audio coefficients fit comfortably in this range. Avoid the scaled
       general hypot/division here; retain its overflow/underflow path for
       coefficients outside the ordinary audio range. */
    {float power=re*re+im*im;
     if(power>=1e-36f&&power<=1e36f)return sqrtf(power);}
#endif
    return hypotf(re,im);
}
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
#include "wavetable.h"
#endif
static void sample(SaVoice *v,float out[2],float body[2],const HbBand *band,const float *shape,float amount) {
    const SaBank *b=v->bank;
    unsigned a,h,c,lo=0,hi=0;
    float blend=0;
    v->root_hz+=v->follow*(v->root_target-v->root_hz);
    v->detail+=v->follow*(v->detail_target-v->detail);v->gain+=v->follow*(v->gain_target-v->gain);
    sd_texture_prepare_batch(v->texture,b->profile,b->count);
    if(v->sample_cache){SaSampleCache *cache=v->sample_cache;
        for(a=0;a<cache->count;++a)if(cache->updates[a]!=v->texture[a].updates){
            memcpy(cache->left[a],v->texture[a].left,sizeof cache->left[a]);
            memcpy(cache->right[a],v->texture[a].right,sizeof cache->right[a]);
            cache->updates[a]=v->texture[a].updates;
        }
    }
    /* Followers approach a boundary asymptotically; sub-nanohertz rounding
       must not label a stationary endpoint as uncovered forever. */
    v->coverage=v->root_hz<b->profile[0]->base_hz-1e-8f?-1:v->root_hz>b->profile[b->count-1]->base_hz+1e-8f?1:0;
    if (v->root_hz>=b->profile[b->count-1]->base_hz) lo=hi=b->count-1;
    else if (v->root_hz>b->profile[0]->base_hz) {
        while (lo+1<b->count && v->root_hz>b->profile[lo+1]->base_hz) ++lo;
        hi=lo+1;
        blend=(v->root_hz-b->profile[lo]->base_hz)/(b->profile[hi]->base_hz-b->profile[lo]->base_hz);
    }
    v->lower=lo;v->upper=hi;v->blend=blend;out[0]=out[1]=0;
    if(body)body[0]=body[1]=0;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    if(v->sample_cache)wt_sample(v,lo,hi,blend,out,body,band,shape,amount);
    else {
#endif
    float cl=cosf(v->phase),sl=sinf(v->phase),base_c=cl,base_s=sl;
    /* Model and control values remain fixed throughout this sample. Keep
       these reads outside library calls in the per-harmonic loop. */
    const unsigned harmonics=b->harmonics;
    const float root_hz=v->root_hz,detail=v->detail;
    const float fraction_lo=v->texture[lo].fraction,fraction_hi=v->texture[hi].fraction;
    const SaSampleCache *cache=v->sample_cache;
    const float (*unit_lo)[4]=cache&&lo<cache->count?cache->unit[lo]:b->unit[lo];
    HbBand mask;if(body)mask=*band;
    for (h=0;h<harmonics;++h) {
        float hz=(h+1)*root_hz, aa=1,next,weight=body?hb_band_weight_inline(&mask,hz):0;
        /* Smoothly remove orders before Nyquist; pitch itself is never clamped
           to the training interval. Taper starts19.2k, reaches zero21.6kHz. */
        if (hz>=21600) break;
        if (hz>19200) { float x=(hz-19200)/2400;aa=1-x*x*(3-2*x); }
        for (c=0;c<2;++c) {
            const float *unit=unit_lo[h];
            float mag=magnitude(b,cache,v->texture,lo,h,c,detail,fraction_lo),re=unit[2*c],im=unit[2*c+1];
            if (lo!=hi) {
                float phase=b->phase[lo][h][c]+blend*b->delta[lo][h][c];
                mag+=blend*(magnitude(b,cache,v->texture,hi,h,c,detail,fraction_hi)-mag);
                if (blend==1) { re=b->unit[hi][h][2*c];im=b->unit[hi][h][2*c+1]; }
                else if (blend!=0) { re=sa_bank_sine(b,phase+PI/2);im=sa_bank_sine(b,phase); }
            }
            float contribution=aa*mag*(re*cl-im*sl);
            if(shape&&amount>0)contribution*=1+amount*(shape[h]-1);
            out[c]+=contribution;
            if(body&&weight!=0)body[c]+=weight*contribution;
        }
        next=sl*base_c+cl*base_s;cl=cl*base_c-sl*base_s;sl=next;
    }
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    }
#endif
    out[0]*=v->gain;out[1]*=v->gain;
    if(body){body[0]*=v->gain;body[1]*=v->gain;}
    v->phase+=2*PI*v->root_hz/48000;if (v->phase>=2*PI) v->phase-=2*PI;
    for (a=0;a<b->count;++a) v->texture[a].fraction+=v->root_hz/12000;
    ++v->frame;
}
void sa_voice_tick(SaVoice *v,float out[2]) { sample(v,out,NULL,NULL,NULL,0); }
int sa_voice_tick_body(SaVoice *v,const HbBand *band,float out[2],float body[2]) {
    if(!v||!v->bank||!out||!body||out==body||!hb_band_valid(band))return 0;
    sample(v,out,body,band,NULL,0);return 1;
}
int sa_voice_tick_shaped_body(SaVoice *v,const HbBand *band,const float *gain,float amount,float out[2],float body[2]) {
    if(!v||!v->bank||!out||!body||out==body||!hb_band_valid(band)||!isfinite(amount)||amount<0||amount>1.3f)return 0;
    sample(v,out,body,band,gain,amount);return 1;
}
int sa_voice_tick_shaped(SaVoice *v,const float *gain,float amount,float out[2]){
    if(!v||!v->bank||!out||!isfinite(amount)||amount<0||amount>1.3f)return 0;
    sample(v,out,NULL,NULL,gain,amount);return 1;
}
void sa_voice_process(SaVoice *v,float *out,unsigned frames) {
    unsigned n;for (n=0;n<frames;++n) sa_voice_tick(v,out+2*n);
}
