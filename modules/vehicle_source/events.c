#include "internal.h"
#include "profiles.h"
const char *vs_event_bank_identity(void){return VSL_EVENT_BANK_SHA256;}
int vs_engine_event_profile(VsEngine *s,unsigned type,const EsProfile *p) {
    if(!s||type>=ES_TYPES||!es_profile_valid(p)||s->generator.frame||s->event_pool.frame||
       s->event_pool.started||s->event_control.count)return 0;
    if(s->flare&&((1u<<type)&0x27u)&&(p->mode_count||p->band_count))return 0;
    s->event_pool.profiles[type]=*p;
    if(p->mode_count||p->band_count)s->event_control.available_mask|=1u<<type;
    else s->event_control.available_mask&=~(1u<<type);
    return 1;
}
unsigned vs_event_mask(void) {
    unsigned k,mask=0;
    for(k=0;k<ES_TYPES;++k)if(vsl_event_profiles[k].mode_count||vsl_event_profiles[k].band_count)mask|=1u<<k;
    return mask;
}
int vs_events_init(VsEngine *s,const EcControl *c) {
    unsigned k;ec_init(&s->event_control,vs_event_mask());
    if(!es_pool_init(&s->event_pool,vsl_event_profiles)||!ec_set(&s->event_control,c,0))return 0;
    for(k=0;k<ES_TYPES;++k)s->event_levels[k]=c->enabled?c->gain*c->levels[k]:0;
    return 1;
}
void vs_events_observe(VsEngine *s,const VslDrive *d,const VslParams *p,uint64_t frame) {
    EcObservation o={0};
    o.lifecycle=(int)d->lifecycle;o.shift_direction=d->shift_direction;o.previous_gear=d->previous_gear;
    o.starts=d->start_events;o.shifts=d->shift_events;o.overruns=d->overrun_events;
    o.rpm=d->rpm;o.load=d->load;o.overrun_strength=d->overrun_strength;o.allow_afterfire=p->backfire;
    ec_observe(&s->event_control,&o,frame);
}
int vs_events_sample(void *state,uint64_t frame) {
    VsEngine *s=state;EcCommand c;EsFrame f;unsigned k,n=(unsigned)(frame-s->event_block_frame);
    if(n>=VS_BLOCK_MAX||s->event_pool.frame!=frame)return 0;
    while(ec_poll(&s->event_control,frame,&c)) {
        if(c.operation==EC_START)es_pool_start(&s->event_pool,&c.request);
        else es_pool_release(&s->event_pool,c.type,c.release_seconds);
    }
    for(k=0;k<ES_TYPES;++k) {
        double target=s->event_control.control.enabled?s->event_control.control.gain*s->event_control.control.levels[k]:0;
        s->event_levels[k]+=s->generator.follow*(target-s->event_levels[k]);
    }
    if(!es_pool_tick(&s->event_pool,&f))return 0;
    for(k=0;k<ES_VOICES;++k)s->event_voices[k][n]=(float)(f.sample[k]*s->event_levels[f.type[k]]);
    return vs_flare_sample(s,frame);
}
unsigned vs_engine_events(VsEngine *s,EsNotice *out,unsigned capacity) {
    return s?es_pool_notices(&s->event_pool,out,capacity):0;
}
