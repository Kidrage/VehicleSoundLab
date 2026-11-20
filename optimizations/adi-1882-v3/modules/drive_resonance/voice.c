#include "dsp/perf.h"
#include "voice.h"
#include <math.h>
#include <string.h>
#include "dsp_support/storage.h"
#define DRS_PI 3.14159265358979323846f
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_FIR_TAPS) && VSL_DSP_FIR_TAPS <= 512
VSL_SECTION(VSL_L1_STATE)
static RdtVoice drs_rdt_runtime[SA_MAX_ANCHORS];
VSL_SECTION(VSL_L2_HISTORY)
static RdtProfile drs_first_profile;
#define DRS_RDT(v,a) (drs_rdt_runtime+(a))
#else
#define DRS_RDT(v,a) ((v)->voice+(a))
#endif
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
int drs_voice_prepare(DrsVoice *v,unsigned frames);
int drs_voice_prepare_impl(DrsVoice *v,unsigned frames){
    /* Phase-dependent current V10 cannot use the prepared path. Keep all
       sleeping voices partition invariant, including other profile kinds. */
    (void)frames;return v&&v->bank;

}
int drs_voice_prepare(DrsVoice *v,unsigned frames){vsl_perf_enter(3);int result=drs_voice_prepare_impl(v,frames);vsl_perf_leave();return result;}

#endif
static int unit(float x){return isfinite(x)&&x>=0&&x<=1;}
static int amount_valid(float x){return isfinite(x)&&x>=0&&x<=1.3f;}
static float cycle(float x) {
    float phase=fmodf(x,1);if(phase<0)phase+=1;
    /* A tiny negative remainder can round to1 when adding1. */
    return phase>=1?0:phase;
}
static float smooth(float x){return x*x*(3-2*x);}
static float support(const DrsBank *b,unsigned a,float hz) {
    float x=hz/b->root[a];
    if(x<=b->outer_low||x>=b->outer_high)return 0;
    if(x<b->inner_low)return smooth((x-b->outer_low)/(b->inner_low-b->outer_low));
    if(x>b->inner_high)return smooth((b->outer_high-x)/(b->outer_high-b->inner_high));
    return 1;
}
int drs_voice_init(DrsVoice *out,const DrsBank *b,const SaBank *dna,uint64_t seed,float amount) {
    VSL_SECTION(VSL_DDR)
    VSL_INIT_WORK DrsVoice v;unsigned a,n;
    if(!out||!amount_valid(amount)||!drs_bank_valid(b,dna))return 0;
    memset(&v,0,sizeof v);v.bank=b;v.amount=v.target=amount;v.follow=1-expf(-1/(.018f*48000));
    for(a=0;a<b->count;++a)if(b->enabled[a]) {
        if(b->kind[a]==DRS_STEREO) {
            if(!rvs_voice_init(v.stereo+a,b->stereo+a,seed^(UINT64_C(0x9e3779b97f4a7c15)*a),1))return 0;
            continue;
        }
        const RdtProfile *p=b->profile+a;float unused[2];
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_FIR_TAPS) && VSL_DSP_FIR_TAPS <= 512
        if(a==0){drs_first_profile=*p;p=&drs_first_profile;}
#endif
        if(!rdt_voice_init(DRS_RDT(&v,a),p,seed^(UINT64_C(0x9e3779b97f4a7c15)*a)))return 0;
        for(n=0;n<p->warmup_frames;++n) {
            float phase=cycle(((float)n-p->warmup_frames)*p->base_hz/48000+dna->offset[a]/(2*DRS_PI));
            if(!rdt_voice_tick(DRS_RDT(&v,a),phase,unused,NULL))return 0;
        }
    }*out=v;return 1;
}
int drs_voice_set(DrsVoice *v,float amount){if(!v||!v->bank||!amount_valid(amount))return 0;v->target=amount;return 1;}
int drs_voice_tick(DrsVoice *v,const SaVoice *dna,float sampled_phase,DrsFrame *f);
int drs_voice_tick_impl(DrsVoice *v,const SaVoice *dna,float sampled_phase,DrsFrame *f){
    unsigned a,c;const DrsBank *b;
    if(!v||!v->bank||!dna||!dna->bank||!f||!isfinite(sampled_phase)||sampled_phase<0||sampled_phase>=2*DRS_PI||
       dna->bank->count!=v->bank->count||dna->lower>=v->bank->count||dna->upper>=v->bank->count||!unit(dna->blend))return 0;
    b=v->bank;memset(f,0,sizeof *f);
    for(a=0;a<b->count;++a)if(b->enabled[a]) {
        float x[2],weight=0,phase=cycle((sampled_phase+dna->bank->offset[a])/(2*DRS_PI));
        if(dna->lower==dna->upper){if(a==dna->lower)weight=1;}
        else if(a==dna->lower)weight=1-dna->blend;else if(a==dna->upper)weight=dna->blend;
        weight=sqrtf(weight)*support(b,a,dna->root_hz);f->support+=weight*weight;
        v->awake[a]=weight!=0;
        if(weight==0){
            v->wake_gain[a]=0;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
            /* Drain an already prepared block; never leave a stale cache. */
            if(b->kind[a]==DRS_STEREO){
                if(v->stereo[a].prepared_frames&&!rvs_voice_tick(v->stereo+a,x,NULL))return 0;
            }else if(DRS_RDT(v,a)->prepared_frames&&!rdt_voice_tick(DRS_RDT(v,a),phase,x,NULL))return 0;
#endif
            continue;
        }
        if(b->kind[a]==DRS_STEREO) {if(!rvs_voice_tick(v->stereo+a,x,NULL))return 0;}
        else if(!rdt_voice_tick(DRS_RDT(v,a),phase,x,NULL))return 0;
        v->wake_gain[a]=fminf(1,v->wake_gain[a]+1.f/480);
        weight*=v->wake_gain[a];
        for(c=0;c<2;++c)f->raw[c]+=x[c]*weight;
    }
    v->amount+=v->follow*(v->target-v->amount);
    for(c=0;c<2;++c)f->output[c]=f->raw[c]*v->amount;++v->frame;return 1;
}
int drs_voice_tick(DrsVoice *v,const SaVoice *dna,float sampled_phase,DrsFrame *f){vsl_perf_enter(3);int result=drs_voice_tick_impl(v,dna,sampled_phase,f);vsl_perf_leave();return result;}

