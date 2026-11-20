#include "voice.h"
#include "envelope.h"
#include <math.h>
#include <string.h>
#include "dsp_support/storage.h"
#ifdef VSL_DSP_FAST_TRIG
/* Single serialized DSP: cache the last initialized immutable profile.
   Other profiles keep the general path. Phase-dependent amplitude remains
   applied between the original source and post filters, at every sample. */
#define RDT_ENV_POINTS 256
VSL_SECTION(VSL_L1_STATE)
static float rdt_amplitude_table[RDT_MAX_BANDS][RDT_ENV_POINTS+1];
static const RdtProfile *rdt_amplitude_profile;
static void rdt_amplitude_prepare(const RdtProfile *p){
    unsigned b,n;
    for(b=0;b<p->count;++b)for(n=0;n<=RDT_ENV_POINTS;++n)
        rdt_amplitude_table[b][n]=rdt_envelope_amplitude(p->band+b,(float)n/RDT_ENV_POINTS);
    rdt_amplitude_profile=p;
}
static float rdt_amplitude_lookup(unsigned b,float phase){
    float position=phase*RDT_ENV_POINTS;unsigned i=(unsigned)position;
    float u=position-i;
    return rdt_amplitude_table[b][i]+u*(rdt_amplitude_table[b][i+1]-rdt_amplitude_table[b][i]);
}
#endif
int rdt_voice_init(RdtVoice *v,const RdtProfile *p,uint64_t seed) {
    unsigned b;
    if(!v||!rdt_profile_valid(p))return 0;
    memset(v,0,sizeof *v);v->profile=p;
#ifdef VSL_DSP_FAST_TRIG
    rdt_amplitude_prepare(p);
#endif
    for(b=0;b<p->count;++b)rdt_excitation_init(v->excitation+b,seed^(UINT64_C(0x9E3779B97F4A7C15)*(b+1)));
    return 1;
}
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
int rdt_voice_prepare(RdtVoice *v,float *out,unsigned frames){
    unsigned b,n;
    if(!v||!v->profile||!out||!frames||v->prepared_frames)return 0;
    for(b=0;b<v->profile->count;++b)
        if(v->profile->band[b].envelope_order)return 1;
    memset(out,0,2*frames*sizeof *out);
    for(b=0;b<v->profile->count;++b){
        const RdtBand *m=v->profile->band+b;
        for(n=0;n<frames;++n){
            float x=rdt_filter_source(v->filter+b,m,rdt_excitation_next(v->excitation+b));
            x*=sqrtf(1);x=rdt_filter_post(v->filter+b,m,x);
            out[2*n]+=x*m->gain;out[2*n+1]+=x*(m->gain*m->right_over_left);
        }
    }
    v->prepared=out;v->prepared_frames=frames;return 1;
}
#endif
int rdt_voice_tick(RdtVoice *v,float phase,float out[2],float bands[RDT_MAX_BANDS]) {
    unsigned b,k,order=0;float left=0,right=0;
    float cosine[RDT_MAX_ENVELOPE],sine[RDT_MAX_ENVELOPE];
    if(!v||!v->profile||!out||!isfinite(phase)||phase<0||phase>=1)return 0;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    if(v->prepared_frames){
        if(bands)return 0;
        out[0]=v->prepared[0];out[1]=v->prepared[1];
        v->prepared+=2;--v->prepared_frames;++v->frame;return 1;
    }
#endif
    /* Every band sees the same phase. Evaluate each exact libm argument once,
       retaining the original cosine-then-sine accumulation order per band. */
    for(b=0;b<v->profile->count;++b)if(v->profile->band[b].envelope_order>order)order=v->profile->band[b].envelope_order;
    #ifdef VSL_DSP_FAST_TRIG
    if(v->profile!=rdt_amplitude_profile)
#endif
    for(k=0;k<order;++k){cosine[k]=cosf(2*3.14159265358979323846f*(k+1)*phase);sine[k]=sinf(2*3.14159265358979323846f*(k+1)*phase);}
    for(b=0;b<v->profile->count;++b) {
        const RdtBand *m=v->profile->band+b;
        float power=1;
        float x=rdt_filter_source(v->filter+b,m,rdt_excitation_next(v->excitation+b));
#ifdef VSL_DSP_FAST_TRIG
        if(v->profile==rdt_amplitude_profile)x*=rdt_amplitude_lookup(b,phase);
        else {
#endif
        for(k=0;k<m->envelope_order;++k)power+=cosine[k]*m->beta[k];
        for(k=0;k<m->envelope_order;++k)power+=sine[k]*m->beta[m->envelope_order+k];
        x*=sqrtf(power);
#ifdef VSL_DSP_FAST_TRIG
        }
#endif
        x=rdt_filter_post(v->filter+b,m,x);
        if(bands)bands[b]=x;
        left+=x*m->gain;right+=x*(m->gain*m->right_over_left);
    }
    out[0]=left;out[1]=right;++v->frame;return 1;
}
