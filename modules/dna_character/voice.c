#include "voice.h"
#include "modal_texture/voice.h"
#include "spectral_texture/voice.h"
#include <math.h>
#include <stdlib.h>
struct DchVoice {
    const FiProfile *profile;MtVoice modal;SfBank *bank;SfVoice *texture;
    DchControl control;double follow,line,air,idle_weight,air_weight;
    uint64_t frame;
};
static double clamp(double x,double lo,double hi){return fmin(hi,fmax(lo,x));}
void dch_destroy(DchVoice *v){if(v){sf_voice_destroy(v->texture);sf_bank_destroy(v->bank);free(v);}}
DchVoice *dch_create(const FiProfile *p,uint64_t seed,const DchControl *c) {
    DchVoice *v;if(!seed||!dch_control_valid(c)||(p&&!fi_profile_valid(p)))return NULL;
    v=calloc(1,sizeof *v);if(!v)return NULL;v->profile=p;v->control=*c;
    v->follow=1-exp(-1/(.080*48000));v->line=c->line;v->air=c->air;
    /* No hidden high-speed extrapolation in the fixed measured filters. The
       retained air amount is explicit; modal pitch-follow is bounded below. */
    if(p&&(!mt_voice_init(&v->modal,p->modal,p->motion,seed,p->modal_ratio,p->modal_gain,c->motion)||
        !(v->bank=sf_bank_create(p->detail))||!(v->texture=sf_voice_create(v->bank,seed)))){dch_destroy(v);return NULL;}
    return v;
}
int dch_set(DchVoice *v,const DchControl *c){
    if(!v||!dch_control_valid(c))return 0;v->control=*c;
    /* Adopt the host's initial recipe before sample zero. During playback all
       edits retain the follower, including a smooth fade toward zero. */
    if(!v->frame){v->line=c->line;v->air=c->air;}return 1;
}
int dch_tick(DchVoice *v,const DchContext *ctx,const double line[2],const double air[2],DchFrame *out) {
    double modal[2]={0},texture[2]={0},w=0,a=0;unsigned k;
    if(!v||!ctx||!line||!air||!out||ctx->state>=DCH_STATES||!isfinite(ctx->rpm)||ctx->rpm<0||
       !isfinite(ctx->idle_rpm)||ctx->idle_rpm<=0||!isfinite(ctx->envelope)||ctx->envelope<0)return 0;
    if(v->profile){
        double x=clamp((ctx->rpm/ctx->idle_rpm-1)/3,0,1),near=1-x*x*(3-2*x);
        double ratio=clamp(ctx->rpm/ctx->idle_rpm,.75,2);
        ratio=v->profile->modal_ratio*(1+v->control.pitch_follow*(ratio-1));
        if(!mt_voice_set(&v->modal,ratio,v->profile->modal_gain,v->control.motion)||
           !mt_voice_tick(&v->modal,modal)||!sf_voice_tick(v->texture,texture,NULL))return 0;
        w=v->control.idle_blend*near;
        a=v->control.idle_blend*(near+(1-near)*v->control.air_continuity);
    }
    v->idle_weight+=v->follow*(w-v->idle_weight);v->air_weight+=v->follow*(a-v->air_weight);
    v->line+=v->follow*(v->control.line*v->control.line_state[ctx->state]-v->line);
    v->air+=v->follow*(v->control.air*v->control.air_state[ctx->state]-v->air);
    for(k=0;k<2;++k){
        double level=v->profile?v->profile->level_gain*ctx->envelope:0;
        double detail_gain=v->profile?v->profile->detail_gain:0;
        /* Beyond the nominal replacement endpoint, increase the fingerprint
           without introducing a negative, phase-inverted base contribution. */
        double keep=fmax(0,1-v->idle_weight);
        out->line[k]=v->line*(keep*line[k]+v->idle_weight*level*modal[k]);
        out->air[k]=v->air*(keep*air[k]+v->air_weight*level*detail_gain*texture[k]);
        if(!isfinite(out->line[k])||!isfinite(out->air[k]))return 0;
    }
    out->idle_weight=v->idle_weight;out->air_weight=v->air_weight;++v->frame;return 1;
}
