#include "voice.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
static int valid(double p,double a){return isfinite(p)&&p>=.9&&p<=1.1&&isfinite(a)&&a>=0&&a<=1;}
static void filter_init(LrFilter *s,double hz,int hp){double c=cos(2*PI*hz/48000),alpha=sin(2*PI*hz/48000)/sqrt(2),a0=1+alpha;
    s->b0=(hp?1+c:1-c)/(2*a0);s->b1=(hp?-(1+c):1-c)/a0;s->b2=s->b0;s->a1=-2*c/a0;s->a2=(1-alpha)/a0;}
static double process(LrFilter *s,double x){double y=s->b0*x+s->z1;s->z1=s->b1*x-s->a1*y+s->z2;s->z2=s->b2*x-s->a2*y;return y;}
int lr_voice_init(LrVoice *s,const LrProfile *m,uint64_t seed,double p,double a){
    if(!s||!lr_profile_valid(m)||!valid(p,a))return 0;memset(s,0,sizeof *s);s->profile=m;
    s->pitch=s->pitch_target=p;s->amount=s->amount_target=a;s->follow=1-exp(-1/(.018*m->rate));
    filter_init(&s->highpass,24,1);filter_init(&s->lowpass,340,0);lr_cloud_init(&s->cloud,m,seed);return 1;
}
int lr_voice_set(LrVoice *s,double p,double a){if(!s||!s->profile||!valid(p,a))return 0;s->pitch_target=p;s->amount_target=a;return 1;}
void lr_voice_process(LrVoice *s,double *mono,unsigned frames){unsigned n;
    for(n=0;n<frames;++n){double x;s->pitch+=s->follow*(s->pitch_target-s->pitch);s->amount+=s->follow*(s->amount_target-s->amount);
        x=lr_cloud_sample(&s->cloud,s->profile,s->pitch);x=process(&s->lowpass,process(&s->highpass,x));mono[n]=x*s->amount;}
}
