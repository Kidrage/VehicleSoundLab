#include "voice.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
int pt_voice_set(PtVoice *s,double amount) {
    if(!s||!s->model||!isfinite(amount)||amount<0||amount>1)return 0;
    s->target=amount;return 1;
}
int pt_voice_init(PtVoice *s,const SdProfile *m,uint64_t seed,double amount) {
    unsigned h;
    if(!s||!m||m->rate!=48000||m->harmonics<1||m->harmonics>SD_MAX_HARMONICS||
       !isfinite(amount)||amount<0||amount>1)return 0;
    memset(s,0,sizeof *s);s->model=m;s->amount=s->target=amount;
    s->follow=1-exp(-1/(.018*m->rate));
    for(h=0;h<m->harmonics;++h) {
        double x=fmin(1,fmax(0,((h+1)*m->base_hz-1200)/700));
        s->mask[h]=.5-.5*cos(PI*x);
    }
    pt_motion_init(&s->motion,seed);return 1;
}
static void sample(PtVoice *p,SdVoice *s,double delay,double out[2]) {
    const SdProfile *m=s->model;unsigned h,c;
    double bc=cos(s->oscillator.phase),bs=sin(s->oscillator.phase),cl=bc,sl=bs;
    double shift=2*PI*m->base_hz*s->pitch*delay;
    double dc=cos(s->oscillator.phase+shift),ds=sin(s->oscillator.phase+shift),cm=dc,sm=ds;
    out[0]=out[1]=0;
    for(h=0;h<m->harmonics;++h) {
        const SdHarmonic *a=&m->harmonic[h];double z[4],next;
        for(c=0;c<4;++c)z[c]=a->mean[c]+s->amount*(s->texture.left[h][c]+s->texture.fraction*(s->texture.right[h][c]-s->texture.left[h][c]));
        for(c=0;c<2;++c) {
            double re=s->oscillator.unit[h][2*c],im=s->oscillator.unit[h][2*c+1];
            double original=re*cl-im*sl;
            double value=original+p->mask[h]*((re*cm-im*sm)-original);
            out[c]+=hypot(z[2*c],z[2*c+1])*value;
        }
        next=sl*bc+cl*bs;cl=cl*bc-sl*bs;sl=next;
        next=sm*dc+cm*ds;cm=cm*dc-sm*ds;sm=next;
    }
}
void pt_voice_tick(PtVoice *p,SdVoice *s,double out[2]) {
    const SdProfile *m=s->model;double delay,ratio=m->base_hz/(m->rate/(double)m->window);
    /* Match sound_dna's amplitude/control update order, leaving its code intact.
       Only this opt-in adapter has the additional shared phase coordinate. */
    sd_texture_prepare(&s->texture,m);
    s->pitch+=s->follow*(s->pitch_target-s->pitch);
    s->amount+=s->follow*(s->amount_target-s->amount);
    s->gain+=s->follow*(s->gain_target-s->gain);
    p->amount+=p->follow*(p->target-p->amount);
    if(fabs(p->target-p->amount)<1e-14)p->amount=p->target;
    delay=pt_motion_tick(&p->motion)*p->amount;
    if(delay==0)sd_oscillator_sample(&s->oscillator,&s->texture,m,s->amount,out);
    else sample(p,s,delay,out);
    out[0]*=s->gain;out[1]*=s->gain;
    s->oscillator.phase+=2*PI*s->pitch/m->window*ratio;
    if(s->oscillator.phase>=2*PI)s->oscillator.phase-=2*PI;
    s->texture.fraction+=s->pitch/m->hop*ratio;++s->frame;
}
