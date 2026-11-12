#include "voice.h"
#include <math.h>
#include <string.h>
#define RSS_PI 3.14159265358979323846
int rss_control_valid(const RssControl *p) {
    return p&&ds_source_control_valid(&p->source)&&p->source.phase_texture==0&&
        isfinite(p->detail_gain)&&p->detail_gain>=0&&p->detail_gain<=1;
}
int rss_voice_init(RssVoice *out,const RssConfig *c,const RssControl *p) {
    RssVoice v;unsigned n;
    if(!out||!c||!rss_control_valid(p)||!rss_profile_valid(c->source.dna)||
       (c->source.low&&!rss_profile_valid(c->source.low))||
       (c->detail&&(!rdt_profile_valid(c->detail)||c->detail->rate!=c->source.dna->rate||
                   c->detail->base_hz!=c->source.dna->base_hz)))return 0;
    memset(&v,0,sizeof v);
    if(!ds_source_init(&v.source,&c->source,&p->source))return 0;
    if(c->detail) {
        double unused[2];unsigned warm=c->detail->warmup_frames;
        if(!rdt_voice_init(&v.detail,c->detail,c->detail_seed))return 0;
        for(n=0;n<warm;++n) {
            double phase=fmod(((double)n-warm)*c->detail->base_hz/48000*p->source.pitch,1);
            if(phase<0)phase+=1;
            if(!rdt_voice_tick(&v.detail,phase,unused,NULL))return 0;
        }
        v.has_detail=1;
    }
    v.target=*p;v.detail_gain=p->detail_gain;v.follow=1-exp(-1/(.018*48000));v.initialized=1;
    *out=v;return 1;
}
int rss_voice_set(RssVoice *v,const RssControl *p) {
    if(!v||!v->initialized||!rss_control_valid(p)||!ds_source_set(&v->source,&p->source))return 0;
    v->target=*p;return 1;
}
int rss_voice_tick(RssVoice *v,RssFrame *f) {
    unsigned c;double phase;
    if(!v||!v->initialized||!f)return 0;
    phase=v->source.dna.oscillator.phase/(2*RSS_PI);
    /* The source samples this phase, then advances it. Do not use next phase. */
    ds_source_tick(&v->source,&f->source);
    f->detail_raw[0]=f->detail_raw[1]=0;
    if(v->has_detail&&!rdt_voice_tick(&v->detail,phase,f->detail_raw,NULL))return 0;
    v->detail_gain+=v->follow*(v->target.detail_gain-v->detail_gain);
    for(c=0;c<2;++c) {
        f->detail[c]=f->detail_raw[c]*v->detail_gain*v->source.dna_gain;
        f->mix[c]=(f->source.dna[c]+f->source.low[c])+f->detail[c];
    }
    f->phase_cycles=phase;return 1;
}
