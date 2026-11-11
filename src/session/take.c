#include "take.h"
#include "parameters.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
int vsl_take_allocate(VslTake *t,unsigned capacity) {
    if(!t||!capacity||capacity>VSL_TAKE_EVENTS)return 0;
    memset(t,0,sizeof *t);t->events=calloc(capacity,sizeof *t->events);
    if(!t->events)return 0;t->capacity=capacity;return 1;
}
void vsl_take_free(VslTake *t) { if(t) { free(t->events);memset(t,0,sizeof *t); } }
int vsl_take_begin(VslTake *t,const VslEngine *e) {
    unsigned i;
    if(!t||!t->events||!e||e->frame||e->sample_rate!=48000)return 0;
    t->count=0;t->frames=0;t->overflow=0;t->audio_hash=VSL_TAKE_HASH_INITIAL;
    t->sample_rate=48000;t->seed=e->nvh.seed;memcpy(t->dsp,VSL_VERSION,sizeof VSL_VERSION);
    t->assets.dna_count=(unsigned)e->dna.custom_count;t->assets.dna_root=e->dna.custom_root;
    memcpy(t->assets.dna_amp,e->dna.custom_amp,sizeof t->assets.dna_amp);
    memcpy(t->assets.dna_phase,e->dna.custom_phase,sizeof t->assets.dna_phase);
    t->assets.ir_length=e->acoustics.ir_length;
    memset(t->assets.ir,0,sizeof t->assets.ir);
    for(i=0;i<t->assets.ir_length;++i)t->assets.ir[i]=e->acoustics.ir[i];
    return 1;
}
int vsl_take_record(VslTake *t,uint64_t frame,const VslParams *p) {
    if(!t||!t->events||!p||frame!=t->frames||frame>=VSL_TAKE_MAX_FRAMES)return 0;
    if(t->count&&vsl_params_same(&t->events[t->count-1].params,p))return 1;
    if(t->count>=t->capacity) { t->overflow=1;return 0; }
    t->events[t->count].frame=frame;t->events[t->count++].params=*p;return 1;
}
uint64_t vsl_take_hash(uint64_t h,const float *audio,unsigned samples) {
    unsigned i,k;for(i=0;i<samples;++i) {
        uint32_t bits;memcpy(&bits,audio+i,sizeof bits);
        for(k=0;k<4;++k) { h^=(bits>>(8*k))&255;h*=UINT64_C(1099511628211); }
    }
    return h;
}
void vsl_take_commit(VslTake *t,const float *audio,unsigned frames) {
    t->audio_hash=vsl_take_hash(t->audio_hash,audio,frames*2);t->frames+=frames;
}
void vsl_take_finish(VslTake *t) {
    while(t&&t->count&&t->events[t->count-1].frame>=t->frames)--t->count;
}
int vsl_take_validate(const VslTake *t) {
    unsigned i;double ir_sum=0;
    if(!t||!t->events||!t->count||t->count>t->capacity||t->capacity>VSL_TAKE_EVENTS||
        !t->frames||t->frames>VSL_TAKE_MAX_FRAMES||t->sample_rate!=48000||!t->seed||
        !memchr(t->dsp,0,sizeof t->dsp)||strcmp(t->dsp,VSL_VERSION)||t->events[0].frame||t->assets.dna_count>VSL_PARTIALS||
        !t->assets.ir_length||t->assets.ir_length>VSL_MAX_IR)return 0;
    if(!isfinite(t->assets.dna_root)||(t->assets.dna_count&&(t->assets.dna_root<10||t->assets.dna_root>4000)))return 0;
    for(i=0;i<t->assets.dna_count;++i)if(!isfinite(t->assets.dna_amp[i])||t->assets.dna_amp[i]<0||t->assets.dna_amp[i]>100||!isfinite(t->assets.dna_phase[i]))return 0;
    for(i=0;i<t->assets.ir_length;++i) { if(!isfinite(t->assets.ir[i]))return 0;ir_sum+=fabs(t->assets.ir[i]); }
    if(ir_sum>1.00001)return 0; /* effective IR from factory/set_ir, never raw unbounded gain */
    for(i=0;i<t->count;++i) {
        const VslParams *p=&t->events[i].params;
        if(t->events[i].frame>=t->frames||(i&&t->events[i].frame<=t->events[i-1].frame))return 0;
        if(!vsl_take_params_valid(p))return 0;
    }
    return 1;
}
int vsl_take_player_init(VslTakePlayer *player,VslEngine *e,const VslTake *t) {
    unsigned i;if(!player||!e||!vsl_take_validate(t))return 0;
    vsl_init(e,t->sample_rate,t->seed);
    e->dna.custom_count=(int)t->assets.dna_count;e->dna.custom_root=t->assets.dna_root;
    memcpy(e->dna.custom_amp,t->assets.dna_amp,sizeof e->dna.custom_amp);
    memcpy(e->dna.custom_phase,t->assets.dna_phase,sizeof e->dna.custom_phase);
    memset(e->acoustics.ir,0,sizeof e->acoustics.ir);
    memcpy(e->acoustics.ir,t->assets.ir,t->assets.ir_length*sizeof(float));
    e->acoustics.ir_length=t->assets.ir_length;e->acoustics.tap_count=0;
    for(i=0;i<t->assets.ir_length;++i)if(t->assets.ir[i]!=0)e->acoustics.taps[e->acoustics.tap_count++]=i;
    player->take=t;player->next=0;player->audio_hash=VSL_TAKE_HASH_INITIAL;return 1;
}
unsigned vsl_take_process(VslTakePlayer *player,VslEngine *e,float *out,unsigned frames,int channels,float *stems) {
    const VslTake *t=player->take;unsigned done=0;
    if(!t||(channels!=2&&channels!=12))return 0;
    while(done<frames&&e->frame<t->frames) {
        uint64_t next=t->frames;unsigned n;
        if(player->next<t->count&&t->events[player->next].frame==e->frame)
            vsl_set_params(e,&t->events[player->next++].params);
        if(player->next<t->count)next=t->events[player->next].frame;
        if(next<=e->frame)return done;
        n=(unsigned)fmin((double)(frames-done),(double)(next-e->frame));
        vsl_process_layout(e,out+done*channels,n,channels,stems?stems+done*VSL_OBJECTS:NULL);
        if(channels==2)player->audio_hash=vsl_take_hash(player->audio_hash,out+done*2,n*2);
        done+=n;
    }
    return done;
}
