#include "state.h"
#include "modal_texture/voice.h"
#include "spectral_texture/voice.h"
#include <math.h>
#include <stdlib.h>
struct FiState {
    const FiProfile *profile;MtVoice modal;SfBank *bank;SfVoice *detail;
    double position,step,amount,follow;unsigned remaining;int gate;
    MsRamp detail_amount;
};
static int unit(double x){return isfinite(x)&&x>=0&&x<=1;}
void fi_state_destroy(FiState *s){if(s){sf_voice_destroy(s->detail);sf_bank_destroy(s->bank);free(s);}}
FiState *fi_state_create(const FiProfile *p,uint64_t seed,double amount,double motion,double detail) {
    FiState *s;if(!fi_profile_valid(p)||!unit(amount)||!unit(motion)||!unit(detail))return NULL;
    s=calloc(1,sizeof *s);if(!s)return NULL;s->profile=p;s->amount=amount;s->follow=1-exp(-1/(.018*48000));
    s->detail_amount.value=s->detail_amount.target=detail;
    if(!mt_voice_init(&s->modal,p->modal,p->motion,seed,p->modal_ratio,p->modal_gain,motion)||
       !(s->bank=sf_bank_create(p->detail))||!(s->detail=sf_voice_create(s->bank,seed))){fi_state_destroy(s);return NULL;}
    return s;
}
int fi_state_tick(FiState *s,int gate,double amount,double motion,double detail,double envelope,FiFrame *out) {
    FiFrame f;unsigned c;MsRamp *d;
    if(!s||!out||(gate!=0&&gate!=1)||!unit(amount)||!unit(motion)||!unit(detail)||
       !isfinite(envelope)||envelope<0||envelope>8)return 0;
    d=&s->detail_amount;
    if(detail!=d->target){d->target=detail;d->left=MS_RAMP_FRAMES;d->step=(detail-d->value)/MS_RAMP_FRAMES;}
    if(d->left){if(!--d->left)d->value=d->target;else d->value+=d->step;}
    if(gate!=s->gate){s->gate=gate;s->remaining=gate?s->profile->attack_frames:s->profile->release_frames;s->step=(gate-s->position)/s->remaining;}
    if(s->remaining){if(!--s->remaining)s->position=gate;else s->position+=s->step;}
    s->amount+=s->follow*(amount-s->amount);
    if(!mt_voice_set(&s->modal,s->profile->modal_ratio,s->profile->modal_gain,motion)||
       !mt_voice_tick(&s->modal,f.modal)||!sf_voice_tick(s->detail,f.detail,NULL))return 0;
    f.weight=s->position*s->position*(3-2*s->position)*s->amount;f.keep=1-f.weight;
    for(c=0;c<2;++c){f.detail[c]*=s->profile->detail_gain*d->value;f.raw[c]=f.modal[c]+f.detail[c];f.output[c]=f.raw[c]*(envelope*f.weight*s->profile->level_gain);}
    *out=f;return 1;
}
