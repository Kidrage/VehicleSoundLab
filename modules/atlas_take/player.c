#include "player.h"
#include <string.h>
int at_player_init(AtPlayer *p,VslEngine *owner,const AtTake *t,int channels) {
    AdControl initial;
    if(!p||!owner||!at_take_valid(t)||(channels!=2&&channels!=12))return 0;
    memset(p,0,sizeof *p);p->take=t;p->config=t->assets->config;p->config.channels=channels;
    initial=t->initial;if(channels==12)initial.mix.spatial=1;p->current=initial;
    p->audio_hash=p->source_hash=AT_HASH_INITIAL;
    return am_render_init(&p->render,owner,&p->config,&initial);
}
unsigned at_player_process(AtPlayer *p,float *out,unsigned frames,AdTelemetry *telemetry) {
    unsigned done=0;const AtTake *t;
    if(!p||!p->take||(frames&&!out))return 0;t=p->take;
    while(done<frames&&p->render.frame<t->frames){
        uint64_t next=t->frames,at=p->render.frame;unsigned n=frames-done;
        AdCapture c={0};
        while(p->next<t->count&&t->events[p->next].frame==at){
            p->current=t->events[p->next++].control;
            if(p->config.channels==12)p->current.mix.spatial=1;
            if(!am_render_set(&p->render,&p->current))return done;
        }
        if(p->next<t->count)next=t->events[p->next].frame;
        if(at<t->stop_frame&&t->stop_frame<next)next=t->stop_frame;
        if(next<=at)return done;
        if(n>512)n=512;if(n>next-at)n=(unsigned)(next-at);
        c.dna_raw=p->raw;c.dna=p->dna;c.residual=p->residual;c.body=p->body;c.events=p->events;
        c.aux_objects=p->auxiliary;
        if(telemetry)c.telemetry=telemetry+done;
        if(!am_render_process(&p->render,out+done*p->config.channels,n,at>=t->stop_frame,&c))return done;
        p->source_hash=at_hash_sources(p->source_hash,&c,n);
        p->audio_hash=at_hash_samples(p->audio_hash,out+done*p->config.channels,n*p->config.channels);
        done+=n;
    }
    return done;
}
int at_player_complete(const AtPlayer *p) {return p&&p->take&&p->render.frame==p->take->frames;}
int at_player_verified(const AtPlayer *p) {
    return at_player_complete(p)&&p->source_hash==p->take->source_hash&&
        (p->config.channels!=p->take->assets->config.channels||p->audio_hash==p->take->audio_hash);
}
