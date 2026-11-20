#include "internal.h"
#include <math.h>
#include <string.h>
void es_notice(EsPool *p,const EsRequest *r,unsigned slot,unsigned action,unsigned reason) {
    EsNotice *n;
    if(p->log_count==ES_LOG_CAPACITY){++p->log_lost;return;}
    n=p->logf+(p->log_read+p->log_count++)%ES_LOG_CAPACITY;
    n->id=r->id;n->requested_frame=r->requested_frame;n->frame=p->frame;
    n->type=r->type;n->slot=slot;n->action=action;n->reason=reason;
}
unsigned es_pool_notices(EsPool *p,EsNotice *out,unsigned capacity) {
    unsigned n=0;if(!p||(!out&&capacity))return 0;
    while(n<capacity&&p->log_count){out[n++]=p->logf[p->log_read];p->log_read=(p->log_read+1)%ES_LOG_CAPACITY;--p->log_count;}
    return n;
}
unsigned es_pool_active(const EsPool *p) {
    unsigned n=0,k;for(k=0;k<ES_VOICES;++k)n+=p->voices[k].active;return n;
}
int es_pool_init(EsPool *p,const EsProfile profiles[ES_TYPES]) {
    unsigned k;if(!p||!profiles)return 0;
    for(k=0;k<ES_TYPES;++k)if(!es_profile_valid(profiles+k))return 0;
    memset(p,0,sizeof *p);memcpy(p->profiles,profiles,sizeof p->profiles);return 1;
}
static int valid(const EsRequest *r) {
    return r&&r->id&&r->type<ES_TYPES&&r->priority<=255&&isfinite(r->strength)&&r->strength>=0&&r->strength<=4&&
        isfinite(r->pitch)&&r->pitch>=.5f&&r->pitch<=2.6f&&isfinite(r->decay)&&r->decay>=.25f&&r->decay<=5.2f&&
        isfinite(r->texture)&&r->texture>=0&&r->texture<=2.6f;
}
int es_pool_start(EsPool *p,const EsRequest *r) {
    unsigned k,slot=ES_VOICES;int candidate=-1;
    if(!p||!valid(r)||r->requested_frame>p->frame)return 0;
    if(!p->profiles[r->type].mode_count&&!p->profiles[r->type].band_count) {
        ++p->rejected;es_notice(p,r,ES_VOICES,ES_REJECTED,ES_UNAVAILABLE);return 0;
    }
    for(k=0;k<ES_VOICES;++k) {
        EsVoice *v=p->voices+k;
        if((v->active&&v->request.id==r->id)||(v->has_pending&&v->pending.id==r->id)) {
            es_notice(p,r,k,ES_REJECTED,ES_DUPLICATE);++p->rejected;return 0;
        }
        if(!v->active&&slot==ES_VOICES)slot=k;
        if(v->active&&!v->has_pending&&v->request.priority<r->priority&&
           (candidate<0||v->request.priority<p->voices[candidate].request.priority))candidate=(int)k;
    }
    if(slot<ES_VOICES) {
        es_voice_begin(p->voices+slot,p->profiles+r->type,r);++p->started;
        es_notice(p,r,slot,ES_STARTED,ES_NATURAL);
        if(es_pool_active(p)>p->peak_active)p->peak_active=es_pool_active(p);
        return 1;
    }
    if(candidate>=0) {
        EsVoice *v=p->voices+candidate;v->pending=*r;v->has_pending=1;
        /* Reuse one slot after its 3 ms fade; never open a fifth tail voice. */
        if(v->release_at==UINT64_MAX||v->release_at+v->release_frames>v->age+144){v->release_at=v->age;v->release_frames=144;}
        v->end_reason=ES_STOLEN;++p->replaced;return 2;
    }
    ++p->rejected;es_notice(p,r,ES_VOICES,ES_REJECTED,ES_CAPACITY);return 0;
}
void es_pool_release(EsPool *p,int type,float seconds) {
    unsigned k;if(!p||type>=(int)ES_TYPES||type< -1||!isfinite(seconds)||seconds<.001f||seconds>2)return;
    for(k=0;k<ES_VOICES;++k) {
        EsVoice *v=p->voices+k;
        if(v->has_pending&&(type<0||v->pending.type==(unsigned)type)) {
            es_notice(p,&v->pending,k,ES_REJECTED,ES_CANCELLED);++p->rejected;v->has_pending=0;
        }
        if(v->active&&(type<0||v->request.type==(unsigned)type)) {
            uint64_t frames=(uint64_t)ceilf(seconds*ES_RATE);
            if(v->release_at==UINT64_MAX||v->release_at+v->release_frames>v->age+frames) {
                v->release_at=v->age;v->release_frames=frames;v->end_reason=ES_RELEASED;
            }
        }
    }
}
int es_pool_tick(EsPool *p,EsFrame *out) {
    unsigned k;if(!p||!out)return 0;
    memset(out,0,sizeof *out);
    for(k=0;k<ES_VOICES;++k) {
        EsVoice *v=p->voices+k;
        if(v->active) {out->sample[k]=es_voice_tick(v);out->id[k]=v->request.id;out->type[k]=v->request.type;}
    }
    ++p->frame;
    for(k=0;k<ES_VOICES;++k) {
        EsVoice *v=p->voices+k;
        if(v->active&&es_voice_finished(v)) {
            EsRequest next=v->pending;unsigned pending=v->has_pending;
            es_notice(p,&v->request,k,ES_ENDED,v->end_reason);v->active=v->has_pending=0;
            if(pending) {es_voice_begin(v,p->profiles+next.type,&next);++p->started;es_notice(p,&next,k,ES_STARTED,ES_STOLEN);}
        }
    }
    return 1;
}
