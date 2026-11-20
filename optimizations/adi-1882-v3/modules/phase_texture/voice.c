#include "voice.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
int pt_voice_set(PtVoice *s,float amount) {
    if(!s||!s->model||!isfinite(amount)||amount<0||amount>1)return 0;
    s->target=amount;return 1;
}
int pt_voice_init(PtVoice *s,const SdProfile *m,uint64_t seed,float amount) {
    unsigned h;
    if(!s||!m||m->rate!=48000||m->harmonics<1||m->harmonics>SD_MAX_HARMONICS||
       !isfinite(amount)||amount<0||amount>1)return 0;
    memset(s,0,sizeof *s);s->model=m;s->amount=s->target=amount;
    s->follow=1-expf(-1/(.018f*m->rate));
    for(h=0;h<m->harmonics;++h) {
        float x=fminf(1,fmaxf(0,((h+1)*m->base_hz-1200)/700));
        s->mask[h]=.5f-.5f*cosf(PI*x);
    }
    pt_motion_init(&s->motion,seed);return 1;
}
static void sample(PtVoice *p,SdVoice *s,float delay,float out[2]) {
    const SdProfile *m=s->model;unsigned h,c;
    float bc=cosf(s->oscillator.phase),bs=sinf(s->oscillator.phase),cl=bc,sl=bs;
    float shift=2*PI*m->base_hz*s->pitch*delay;
    float dc=cosf(s->oscillator.phase+shift),ds=sinf(s->oscillator.phase+shift),cm=dc,sm=ds;
    out[0]=out[1]=0;
    for(h=0;h<m->harmonics;++h) {
        const SdHarmonic *a=&m->harmonic[h];float z[4],next;
        for(c=0;c<4;++c)z[c]=a->mean[c]+s->amount*(s->texture.left[h][c]+s->texture.fraction*(s->texture.right[h][c]-s->texture.left[h][c]));
        for(c=0;c<2;++c) {
            float re=s->oscillator.unit[h][2*c],im=s->oscillator.unit[h][2*c+1];
            float original=re*cl-im*sl;
            float value=original+p->mask[h]*((re*cm-im*sm)-original);
            out[c]+=hypotf(z[2*c],z[2*c+1])*value;
        }
        next=sl*bc+cl*bs;cl=cl*bc-sl*bs;sl=next;
        next=sm*dc+cm*ds;cm=cm*dc-sm*ds;sm=next;
    }
}
void pt_voice_tick(PtVoice *p,SdVoice *s,float out[2]) {
    const SdProfile *m=s->model;float delay,ratio=m->base_hz/(m->rate/(float)m->window);
    /* Match sound_dna's amplitude/control update order, leaving its code intact.
       Only this opt-in adapter has the additional shared phase coordinate. */
    sd_texture_prepare(&s->texture,m);
    s->pitch+=s->follow*(s->pitch_target-s->pitch);
    s->amount+=s->follow*(s->amount_target-s->amount);
    s->gain+=s->follow*(s->gain_target-s->gain);
    p->amount+=p->follow*(p->target-p->amount);
    if(fabsf(p->target-p->amount)<1e-14f)p->amount=p->target;
    delay=pt_motion_tick(&p->motion)*p->amount;
    if(delay==0)sd_oscillator_sample(&s->oscillator,&s->texture,m,s->amount,out);
    else sample(p,s,delay,out);
    out[0]*=s->gain;out[1]*=s->gain;
    s->oscillator.phase+=2*PI*s->pitch/m->window*ratio;
    if(s->oscillator.phase>=2*PI)s->oscillator.phase-=2*PI;
    s->texture.fraction+=s->pitch/m->hop*ratio;++s->frame;
}
