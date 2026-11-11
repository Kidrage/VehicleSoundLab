#include "oscillator.h"
#include <math.h>
#include <string.h>
int ro_player_init(RoPlayer *p,const RoModel *m,double amount) {
    if(!p||!m||!m->count||!m->rate||!isfinite(amount)||amount<0||amount>1)return 0;
    memset(p,0,sizeof *p);p->model=m;p->high_amount=p->high_target=amount;
    p->follow=1-exp(-1/(.018*m->rate));return 1;
}
int ro_set_high(RoPlayer *p,double amount) {
    if(!p||!isfinite(amount)||amount<0||amount>1)return 0;
    p->high_target=amount;return 1;
}
unsigned ro_process(RoPlayer *p,double *stereo,double *high_stereo,unsigned frames) {
    const RoModel *m=p->model;unsigned n=0;
    while(n<frames&&p->frame<m->frames) {
        double base[2]={0,0},high[2]={0,0};int c;
        while(p->segment<m->count&&p->frame>=m->segments[p->segment].start+m->segments[p->segment].frames)++p->segment;
        if(p->segment<m->count) {
            const RoSegment *s=&m->segments[p->segment];
            if(p->frame>=s->start) {
                double t=(p->frame-s->start)/(double)m->rate,r=(p->frame-s->start)/(double)s->frames;unsigned j;
                for(j=0;j<s->count;++j) {
                    const RoPartial *partial=&s->partials[j];
                    for(c=0;c<2;++c) {
                        const RoChannel *a=&partial->channel[c];
                        double phase=a->phase0+a->omega0*t+a->c2*t*t+a->c3*t*t*t;
                        double y=(a->amplitude0+(a->amplitude1-a->amplitude0)*r)*cos(phase);
                        if(partial->group)high[c]+=y;else base[c]+=y;
                    }
                }
            }
        }
        p->high_amount+=p->follow*(p->high_target-p->high_amount);
        if(p->high_target==0&&p->high_amount<1e-12)p->high_amount=0;
        for(c=0;c<2;++c) {
            stereo[n*2+c]=base[c]+p->high_amount*high[c];
            if(high_stereo)high_stereo[n*2+c]=high[c];
        }
        ++p->frame;++n;
    }
    return n;
}
