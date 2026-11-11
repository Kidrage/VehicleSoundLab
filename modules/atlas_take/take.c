#include "take.h"
#include "parameters.h"
#include "atlas_take_build.h"
#include <stdlib.h>
#include <string.h>
const char *at_render_id(void) {return AT_RENDER_ID;}
int at_take_allocate(AtTake *t,unsigned capacity) {
    if(!t||t->events||t->assets||!capacity||capacity>AT_MAX_EVENTS)return 0;
    t->events=calloc(capacity,sizeof *t->events);t->assets=calloc(1,sizeof *t->assets);
    if(!t->events||!t->assets){at_take_free(t);return 0;}t->capacity=capacity;return 1;
}
void at_take_free(AtTake *t) {if(t){free(t->events);free(t->assets);memset(t,0,sizeof *t);}}
int at_take_begin(AtTake *t,const AdConfig *config,const AdControl *initial) {
    AtAssets *candidate;
    if(!t||!t->events||!t->assets||!config||!ad_control_valid(initial,config->channels)||
        (!config->residual_bank&&initial->mix.residual_gain>0))return 0;
    candidate=calloc(1,sizeof *candidate);if(!candidate)return 0;
    if(!at_assets_copy(candidate,config)){free(candidate);return 0;}
    free(t->assets);t->assets=candidate;
    t->initial=*initial;t->count=0;t->frames=0;t->stop_frame=UINT64_MAX;
    t->audio_hash=t->source_hash=AT_HASH_INITIAL;t->overflow=0;return 1;
}
int at_take_event(AtTake *t,uint64_t frame,const AdControl *c) {
    if(!t||!t->assets||!t->events||!ad_control_valid(c,t->assets->config.channels)||
        (!t->assets->config.residual_bank&&c->mix.residual_gain>0)||frame!=t->frames||frame>=AT_MAX_FRAMES)return 0;
    if(t->count&&frame==t->events[t->count-1].frame){t->events[t->count-1].control=*c;return 1;}
    if(t->count&&at_control_same(c,&t->events[t->count-1].control))return 1;
    if(t->count>=t->capacity){t->overflow=1;return 0;}
    t->events[t->count].frame=frame;t->events[t->count++].control=*c;return 1;
}
int at_take_commit(AtTake *t,unsigned frames,uint64_t hash,uint64_t source_hash) {
    if(!t||!frames||frames>AT_MAX_FRAMES||t->overflow||!t->count||t->events[0].frame||t->frames>AT_MAX_FRAMES-frames)return 0;
    t->frames+=frames;t->audio_hash=hash;t->source_hash=source_hash;return 1;
}
void at_take_finish(AtTake *t) {
    if(!t)return;
    while(t->count&&t->events[t->count-1].frame>=t->frames)--t->count;
    if(t->stop_frame>=t->frames)t->stop_frame=UINT64_MAX;
}
int at_take_valid(const AtTake *t) {
    unsigned i;
    if(!t||!t->events||!t->assets||t->overflow||!t->count||t->count>t->capacity||t->capacity>AT_MAX_EVENTS||
        !t->frames||t->frames>AT_MAX_FRAMES||t->events[0].frame||
        (t->stop_frame!=UINT64_MAX&&t->stop_frame>=t->frames)||!at_assets_valid(t->assets)||
        !ad_control_valid(&t->initial,t->assets->config.channels)||
        (!t->assets->config.residual_bank&&t->initial.mix.residual_gain>0))return 0;
    for(i=0;i<t->count;++i)if(t->events[i].frame>=t->frames||(i&&t->events[i].frame<=t->events[i-1].frame)||
        !ad_control_valid(&t->events[i].control,t->assets->config.channels)||
        (!t->assets->config.residual_bank&&t->events[i].control.mix.residual_gain>0))return 0;
    return 1;
}
uint64_t at_hash_samples(uint64_t hash,const float *audio,unsigned samples) {
    unsigned i,k;
    for(i=0;i<samples;++i){uint32_t bits;memcpy(&bits,audio+i,4);
        for(k=0;k<4;++k){hash^=(bits>>(8*k))&255;hash*=UINT64_C(1099511628211);}}
    return hash;
}
uint64_t at_hash_sources(uint64_t hash,const AdCapture *c,unsigned frames) {
    unsigned n;
    for(n=0;n<frames;++n){
        hash=at_hash_samples(hash,c->dna_raw+2*n,2);hash=at_hash_samples(hash,c->dna+2*n,2);
        hash=at_hash_samples(hash,c->residual+2*n,2);hash=at_hash_samples(hash,c->body+2*n,2);
        hash=at_hash_samples(hash,c->events+n,1);
    }
    return hash;
}
