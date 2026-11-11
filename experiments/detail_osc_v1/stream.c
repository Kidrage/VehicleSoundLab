#include "stream.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
static int valid(double pitch,double gain,int loop) {
    return isfinite(pitch)&&pitch>=.9&&pitch<=1.1&&isfinite(gain)&&gain>=0&&gain<=1&&(loop==0||loop==1);
}
int de_init(DePlayer *p,const DoModel *m,double pitch,double gain,int loop) {
    if(!p||!m||!m->grains||!m->count||m->window!=512||m->hop!=128||!valid(pitch,gain,loop))return 0;
    memset(p,0,sizeof *p);p->model=m;p->pitch=p->pitch_target=pitch;p->gain=p->gain_target=gain;p->loop=loop;
    p->follow=1-exp(-1/(.018*m->rate));return 1;
}
int de_set(DePlayer *p,double pitch,double gain,int loop) {
    if(!p||!p->model||!valid(pitch,gain,loop))return 0;
    p->pitch_target=pitch;p->gain_target=gain;p->loop=loop;return 1;
}
static double sample(const DoModel *m,double position) {
    int last=(int)floor((position+m->window-m->hop)/m->hop),first=last-3,g;
    double sum=0;if(first<0)first=0;if(last>=(int)m->count)last=(int)m->count-1;
    for(g=first;g<=last;++g) {
        const DoGrain *grain=&m->grains[g];double local=position-grain->start;
        double w;unsigned j;
        if(local<0||local>=m->window)continue;
        w=(.5-.5*cos(2*PI*local/m->window))/1.5;
        for(j=0;j<grain->count;++j) {
            const DoTone *t=&grain->tones[j];double phase=2*PI*t->bin*local/m->window;
            double scale=(t->bin==0||t->bin==m->window/2?1.:2.)/m->window;
            sum+=(t->real*cos(phase)-t->imag*sin(phase))*scale*w;
        }
    }
    return sum;
}
unsigned de_process(DePlayer *p,double *mono,unsigned frames) {
    unsigned n=0;if(!p||!p->model||!mono)return 0;
    while(n<frames) {
        if(p->position>=p->model->frames) {
            if(!p->loop)break;
            p->position-=p->model->frames;++p->loops;
        }
        p->pitch+=p->follow*(p->pitch_target-p->pitch);
        p->gain+=p->follow*(p->gain_target-p->gain);
        mono[n++]=sample(p->model,p->position)*p->gain;
        p->position+=p->pitch;++p->frame;
    }
    return n;
}
