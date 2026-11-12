#include "render.h"
#include "rt_numeric/scope.h"
#include <math.h>
#include <string.h>
int rsm_control_valid(const RsmControl *p) {
    return p&&rss_control_valid(&p->source)&&isfinite(p->gain)&&p->gain>=0&&p->gain<=.5&&
        isfinite(p->width)&&p->width>=0&&p->width<=1;
}
int rsm_render_init(RsmRender *out,const RssConfig *c,unsigned channels,const RsmControl *p) {
    RsmRender r;
    if(!out||!c||!rsm_control_valid(p)||(!c->source.low&&p->source.source.low_gain>0)||
       (!c->detail&&p->source.detail_gain>0))return 0;
    memset(&r,0,sizeof r);
    if(!sb_layout_init(&r.layout,channels)||!rss_voice_init(&r.voice,c,&p->source))return 0;
    r.target=*p;r.gain=p->gain;r.width=p->width;r.follow=1-exp(-1/(.018*48000));*out=r;return 1;
}
int rsm_render_set(RsmRender *r,const RsmControl *p) {
    if(!r||!r->voice.initialized||!rsm_control_valid(p)||
       (!r->voice.source.has_low&&p->source.source.low_gain>0)||
       (!r->voice.has_detail&&p->source.detail_gain>0)||!rss_voice_set(&r->voice,&p->source))return 0;
    r->target=*p;return 1;
}
static int process(RsmRender *r,float *out,unsigned frames,int stopping,const RsmCapture *capture) {
    unsigned n,c;
    if(!r||!r->voice.initialized||(frames&&!out)||(stopping!=0&&stopping!=1))return 0;
    for(n=0;n<frames;++n) {
        RssFrame f;double mixed[12],envelope=r->frame<480?r->frame/480.:1;
        if(!rss_voice_tick(&r->voice,&f))return 0;
        r->gain+=r->follow*(r->target.gain-r->gain);r->width+=r->follow*(r->target.width-r->width);
        if(!rss_output_frame(&r->layout,&f,r->gain,r->width,mixed))return 0;
        if(stopping||r->release) {
            if(r->release<480)++r->release;
            envelope*=1-r->release/480.;
        }
        for(c=0;c<r->layout.channels;++c) {
            float dry=(float)mixed[c];out[n*r->layout.channels+c]=dry*(float)envelope;
            if(capture&&capture->dry)capture->dry[n*r->layout.channels+c]=dry;
        }
        if(capture)for(c=0;c<2;++c) {
            if(capture->dna)capture->dna[n*2+c]=(float)f.source.dna[c];
            if(capture->low)capture->low[n*2+c]=(float)f.source.low[c];
            if(capture->detail)capture->detail[n*2+c]=(float)f.detail[c];
        }
        ++r->frame;
    }
    return 1;
}
int rsm_render_process(RsmRender *r,float *out,unsigned frames,int stopping,const RsmCapture *capture) {
    RnScope scope=rn_scope_enter();int result=process(r,out,frames,stopping,capture);
    rn_scope_leave(scope);return result;
}
