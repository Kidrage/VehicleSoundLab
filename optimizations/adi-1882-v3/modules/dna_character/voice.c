#include "dsp/perf.h"
#include "dsp/diagnostics.h"
#include "voice.h"
#include "modal_texture/voice.h"
#include "spectral_texture/voice.h"
#include <math.h>
#include <stdlib.h>
#include "dsp_support/storage.h"
struct DchVoice {
    const FiProfile *profile;MtVoice modal;SfBank *bank;SfVoice *texture;
    DchControl control;float follow,line,air,idle_weight,air_weight;
    float cached_rpm,cached_idle,cached_w,cached_a;
    float tint_target,tint_amount,tint_weight[MT_MAX_MODES];
    int geometry_ready;
    uint64_t frame;
};
VSL_STORAGE(dch_storage,DchVoice,1,VSL_L1_VOICE)
static float clamp(float x,float lo,float hi){return fminf(hi,fmaxf(lo,x));}
void dch_destroy(DchVoice *v){if(v){sf_voice_destroy(v->texture);sf_bank_destroy(v->bank);dch_storage_release(v);}}
DchVoice *dch_create(const FiProfile *p,uint64_t seed,const DchControl *c) {
    DchVoice *v;if(!seed||!dch_control_valid(c)||(p&&!fi_profile_valid(p)))return NULL;
    v=dch_storage_acquire();if(!v)return NULL;v->profile=p;v->control=*c;
    v->follow=1-expf(-1/(.080f*48000));v->line=c->line;v->air=c->air;
    /* No hidden high-speed extrapolation in the fixed measured filters. The
       retained air amount is explicit; modal pitch-follow is bounded below. */
    if(p&&(!mt_voice_init(&v->modal,p->modal,p->motion,seed,p->modal_ratio,p->modal_gain,c->motion)||
        !(v->bank=sf_bank_create(p->detail))||!(v->texture=sf_voice_create(v->bank,seed)))){dch_destroy(v);return NULL;}
    if(p){unsigned i;for(i=0;i<p->modal->count;++i){
        float hz=p->modal->mode[i].hz;
        float a=(hz-1760)/700,b=(hz-3100)/1000;
        v->tint_weight[i]=.12f*expf(-a*a)+.08f*expf(-b*b);
    }}
    return v;
}
void dch_mechanical_amount(DchVoice *v,float amount){if(v)v->tint_target=amount;}
void dch_character_amounts(const DchVoice *v,float *line,float *air){if(v){*line=v->line;*air=v->air;}}
int dch_set(DchVoice *v,const DchControl *c){
    if(!v||!dch_control_valid(c))return 0;
    if(c->motion!=v->control.motion||c->idle_blend!=v->control.idle_blend||
       c->air_continuity!=v->control.air_continuity||c->pitch_follow!=v->control.pitch_follow)v->geometry_ready=0;
    v->control=*c;
    /* Adopt the host's initial recipe before sample zero. During playback all
       edits retain the follower, including a smooth fade toward zero. */
    if(!v->frame){v->line=c->line;v->air=c->air;}return 1;
}
int dch_tick_split(DchVoice *v,const DchContext *ctx,const float line[2],const float air[2],float air_envelope,DchFrame *out);
int dch_tick_split_impl(DchVoice *v,const DchContext *ctx,const float line[2],const float air[2],float air_envelope,DchFrame *out){
    float modal[2]={0},texture[2]={0},w=0,a=0,level,air_level,detail_gain,keep,modal_weight,air_keep,texture_weight;unsigned k;
    if(!v||!ctx||!line||!air||!out||ctx->state>=DCH_STATES||!isfinite(ctx->rpm)||ctx->rpm<0||
       !isfinite(ctx->idle_rpm)||ctx->idle_rpm<=0||!isfinite(ctx->envelope)||ctx->envelope<0||
       !isfinite(air_envelope)||air_envelope<0)return 0;
    if(v->profile){
        /* Driver geometry changes on its 200 Hz clock. Reuse the exact value
           between updates; all modal/texture RNG and ramps still tick at 48k. */
        if(!v->geometry_ready||ctx->rpm!=v->cached_rpm||ctx->idle_rpm!=v->cached_idle){
            float x=clamp((ctx->rpm/ctx->idle_rpm-1)/3,0,1),near=1-x*x*(3-2*x);
            float ratio=clamp(ctx->rpm/ctx->idle_rpm,.75f,2);
            ratio=v->profile->modal_ratio*(1+v->control.pitch_follow*(ratio-1));
            if(!mt_voice_set(&v->modal,ratio,v->profile->modal_gain,v->control.motion))return 0;
            v->cached_w=v->control.idle_blend*near;
            v->cached_a=v->control.idle_blend*(near+(1-near)*v->control.air_continuity);
            v->cached_rpm=ctx->rpm;v->cached_idle=ctx->idle_rpm;v->geometry_ready=1;
        }
        if(!(v->frame&63)&&v->tint_amount!=v->tint_target){
            unsigned i,j;float next=v->tint_amount+.08f*(v->tint_target-v->tint_amount);
            if(fabsf(next-v->tint_target)<1e-5f)next=v->tint_target;
            for(i=0;i<v->profile->modal->count;++i){
                float ratio=(1+next*v->tint_weight[i])/(1+v->tint_amount*v->tint_weight[i]);
                for(j=0;j<2;++j){v->modal.source.re[i][j]*=ratio;v->modal.source.im[i][j]*=ratio;}
            }v->tint_amount=next;
        }
        if(!mt_voice_tick(&v->modal,modal))return 0;
        /* Muted independent air may sleep; the shared air follower fades its
           resumed stationary filter state in over80ms. */
        if(v->air>1e-7f||v->control.air*v->control.air_state[ctx->state]>0)
            {if(!sf_voice_tick(v->texture,texture,NULL))return 0;}
        w=v->cached_w;a=v->cached_a;
    }
    v->idle_weight+=v->follow*(w-v->idle_weight);v->air_weight+=v->follow*(a-v->air_weight);
    v->line+=v->follow*(v->control.line*v->control.line_state[ctx->state]-v->line);
    v->air+=v->follow*(v->control.air*v->control.air_state[ctx->state]-v->air);
    level=v->profile?v->profile->level_gain*ctx->envelope:0;
    air_level=v->profile?v->profile->level_gain*air_envelope:0;
    detail_gain=v->profile?v->profile->detail_gain:0;
    keep=sqrtf(fmaxf(0,1-v->idle_weight));
    modal_weight=sqrtf(fmaxf(0,v->idle_weight));
    air_keep=sqrtf(fmaxf(0,1-v->air_weight));
    texture_weight=sqrtf(fmaxf(0,v->air_weight));
    for(k=0;k<2;++k){
        /* Beyond the nominal replacement endpoint, increase the fingerprint
           without introducing a negative, phase-inverted base contribution. */
        out->line[k]=v->line*(keep*line[k]+modal_weight*level*modal[k]);
        out->air[k]=v->air*(air_keep*air[k]+texture_weight*air_level*detail_gain*texture[k]);
        if(!isfinite(out->line[k])||!isfinite(out->air[k]))return 0;
    }
    {float m[2],q[2],base[2];for(k=0;k<2;++k){
        m[k]=v->line*modal_weight*level*modal[k];
        q[k]=v->air*texture_weight*air_level*detail_gain*texture[k];
        base[k]=v->air*air_keep*air[k];}
        vsl_diag_put(3,m);vsl_diag_put(4,q);vsl_diag_put(6,base);}
    out->idle_weight=v->idle_weight;out->air_weight=v->air_weight;++v->frame;return 1;
}
int dch_tick_split(DchVoice *v,const DchContext *ctx,const float line[2],const float air[2],float air_envelope,DchFrame *out){vsl_perf_enter(9);int result=dch_tick_split_impl(v,ctx,line,air,air_envelope,out);vsl_perf_leave();return result;}

int dch_tick(DchVoice *v,const DchContext *ctx,const float line[2],const float air[2],DchFrame *out) {
    return ctx?dch_tick_split(v,ctx,line,air,ctx->envelope,out):0;
}
