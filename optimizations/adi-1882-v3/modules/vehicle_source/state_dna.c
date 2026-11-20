#include "internal.h"
#include "state_assets.h"
#include <math.h>
#include <stdlib.h>
#include "dsp_support/storage.h"
#ifdef VSL_FIXED_V10
/* The fixed production bank has one DNA source and no authored state donors.
   Keep the API explicit: an unsupported import fails before allocating or
   mutating the current assets. Generic builds retain the full state morph. */
void vs_state_assets_release(VsAssets *a){(void)a;}
VsAssets *vs_assets_from_state_dna(const VsStateDnaConfig *c){(void)c;return NULL;}
int vs_state_init(VsEngine *s){return s&&s->assets&&!s->assets->states;}
int vs_state_sample(void *state,SaVoice *main,const HbBand *band,float stereo[2],float body[2]){
    (void)state;(void)main;(void)band;(void)stereo;(void)body;return 0;
}
void vs_state_observe(VsEngine *s,const VslDrive *d){(void)s;(void)d;}
int vs_engine_state_dna(const VsEngine *s,SxTelemetry *out){
    unsigned k;if(!s||!out)return 0;out->available_mask=1;
    for(k=0;k<SX_STATES;++k){
        out->weight[k]=out->target[k]=k==0?1.f:0.f;
        out->coverage[k]=k==0?s->generator.dna.coverage:0;
    }
    return 1;
}
#else
struct VsStateAssets {
    SdProfile profile[SX_STATES-1][SA_MAX_ANCHORS];
    SaBank bank[SX_STATES-1];
    SxBank morph;
};
VSL_STORAGE(vs_state_storage,struct VsStateAssets,1,VSL_DDR)
void vs_state_assets_release(VsAssets *a){vs_state_storage_release(a->states);a->states=NULL;}
VsAssets *vs_assets_from_state_dna(const VsStateDnaConfig *c) {
    VsAssets *a;VsDnaConfig base={0};const SaBank *banks[SX_STATES-1]={0};
    unsigned s,k,available=0;
    if(!c||!isfinite(c->transition_seconds)||c->transition_seconds<.02f||c->transition_seconds>2.6f)return NULL;
    for(s=1;s<SX_STATES;++s){
        if(c->count[s]>SA_MAX_ANCHORS||(c->count[s]&&!c->anchors[s]))return NULL;
        if(c->count[s])available=1;
    }
    if(!available)return NULL;
    base.anchors=c->anchors[0];base.count=c->count[0];base.align_orders=c->align_orders;
    base.seed=c->seed;base.vehicle_profile=c->vehicle_profile;base.root_per_rpm=c->root_per_rpm;
    a=vs_assets_from_dna(&base);if(!a)return NULL;
    a->states=vs_state_storage_acquire();if(!a->states){vs_assets_destroy(a);return NULL;}
    for(s=1;s<SX_STATES;++s)if(c->count[s]){
        const SdProfile *models[SA_MAX_ANCHORS];
        for(k=0;k<c->count[s];++k){
            if(!c->anchors[s][k]){vs_assets_destroy(a);return NULL;}
            a->states->profile[s-1][k]=*c->anchors[s][k];models[k]=&a->states->profile[s-1][k];
        }
        if(!sa_bank_init(&a->states->bank[s-1],models,c->count[s],c->align_orders)||
           a->states->bank[s-1].harmonics!=a->owned.bank.harmonics){vs_assets_destroy(a);return NULL;}
        banks[s-1]=&a->states->bank[s-1];
    }
    if(!sx_bank_init(&a->states->morph,&a->owned.bank,banks,c->align_orders,c->transition_seconds)){
        vs_assets_destroy(a);return NULL;
    }
    return a;
}
int vs_state_init(VsEngine *s) {
    return !s->assets->states||sx_voice_init(&s->state_dna,&s->assets->states->morph,s->assets->owned.config.seed);
}
int vs_state_sample(void *state,SaVoice *main,const HbBand *band,float stereo[2],float body[2]) {
    VsEngine *s=state;return sx_voice_tick(&s->state_dna,main,band,stereo,body);
}
void vs_state_observe(VsEngine *s,const VslDrive *d) {
    unsigned state=SX_BASE;if(!s->assets->states)return;
    if(d->lifecycle==VSL_RUNNING){
        if(d->operating==VSL_IDLE)state=SX_IDLE;
        else if(d->operating==VSL_PULL||d->operating==VSL_FREE_REV||d->operating==VSL_SHIFT_RECOVER||d->operating==VSL_REV_MATCH)state=SX_POWER;
        else if(d->operating==VSL_OVERRUN||d->operating==VSL_SHIFT_CUT)state=SX_OVERRUN;
    }
    sx_voice_select(&s->state_dna,state);
}
int vs_engine_state_dna(const VsEngine *s,SxTelemetry *out) {
    if(!s||!out)return 0;
    if(!s->assets->states){unsigned k;out->available_mask=1;
        for(k=0;k<SX_STATES;++k){out->weight[k]=out->target[k]=k==0?1.f:0.f;out->coverage[k]=k==0?s->generator.dna.coverage:0;}
        return 1;
    }
    return sx_voice_telemetry(&s->state_dna,out);
}
#endif
