#include "pitch.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>
#define RT_PI 3.14159265358979323846
static int parameters(double pitch,double high) {
    return isfinite(pitch)&&pitch>=.75&&pitch<=1.25&&isfinite(high)&&high>=0&&high<=1;
}
static double phase(const RoChannel *a,double t) {
    return a->phase0+a->omega0*t+a->c2*t*t+a->c3*t*t*t;
}
static int frequency_bound(const RoChannel *a,double duration,unsigned rate) {
    double limit=2*RT_PI*.46*rate/1.25,vertex;
    double w0=a->omega0,w1=a->omega0+2*a->c2*duration+3*a->c3*duration*duration;
    if(!isfinite(w0)||!isfinite(w1)||fabs(w0)>limit||fabs(w1)>limit)return 0;
    if(a->c3!=0) {
        vertex=-a->c2/(3*a->c3);
        if(vertex>0&&vertex<duration&&fabs(a->omega0+2*a->c2*vertex+3*a->c3*vertex*vertex)>limit)return 0;
    }
    return 1;
}
void rt_player_free(RtPlayer *p) { if(!p)return;free(p->phase_extra);memset(p,0,sizeof *p); }
int rt_player_init(RtPlayer *p,const RoModel *m,const RtTracks *t,double pitch,double high) {
    RtPlayer next={0};unsigned i,j,c;
    if(!p||!m||!m->segments||!m->count||!m->rate||!t||!t->ids||!t->offsets||
       t->segments!=m->count||!t->tracks||t->tracks>RT_MAX_TRACKS||!parameters(pitch,high))return 0;
    for(i=0;i<m->count;++i)for(j=0;j<m->segments[i].count;++j)for(c=0;c<2;++c)
        if(!frequency_bound(&m->segments[i].partials[j].channel[c],m->segments[i].frames/(double)m->rate,m->rate))return 0;
    next.phase_extra=calloc((size_t)t->tracks*2,sizeof *next.phase_extra);if(!next.phase_extra)return 0;
    next.model=m;next.tracks=t;next.pitch=next.pitch_target=pitch;next.high=next.high_target=high;
    next.follow=1-exp(-1/(.018*m->rate));rt_player_free(p);*p=next;return 1;
}
int rt_set(RtPlayer *p,double pitch,double high) {
    if(!p||!parameters(pitch,high))return 0;p->pitch_target=pitch;p->high_target=high;return 1;
}
unsigned rt_process(RtPlayer *p,double *stereo,unsigned frames) {
    const RoModel *m=p->model;unsigned n=0;
    while(n<frames&&p->frame<m->frames) {
        double base[2]={0,0},high[2]={0,0};unsigned c;
        while(p->segment<m->count&&p->frame>=m->segments[p->segment].start+m->segments[p->segment].frames)++p->segment;
        p->pitch+=p->follow*(p->pitch_target-p->pitch);p->high+=p->follow*(p->high_target-p->high);
        if(p->high_target==0&&p->high<1e-12)p->high=0;
        if(p->segment<m->count) {
            const RoSegment *s=&m->segments[p->segment];
            if(p->frame>=s->start) {
                double t=(p->frame-s->start)/(double)m->rate,r=(p->frame-s->start)/(double)s->frames;unsigned j;
                for(j=0;j<s->count;++j) {
                    const RoPartial *part=&s->partials[j];unsigned id=p->tracks->ids[p->tracks->offsets[p->segment]+j];
                    for(c=0;c<2;++c) {
                        const RoChannel *a=&part->channel[c];double phi=phase(a,t);
                        double y=(a->amplitude0+(a->amplitude1-a->amplitude0)*r)*cos(phi+p->phase_extra[id*2+c]);
                        p->phase_extra[id*2+c]+=(p->pitch-1)*(phase(a,t+1./m->rate)-phi);
                        if(part->group)high[c]+=y;else base[c]+=y;
                    }
                }
            }
        }
        for(c=0;c<2;++c)stereo[n*2+c]=base[c]+p->high*high[c];
        ++p->frame;++n;
    }
    return n;
}
