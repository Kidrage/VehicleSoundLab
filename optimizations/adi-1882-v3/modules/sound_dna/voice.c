#include "voice.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
static int valid(float p,float a,float g){return isfinite(p)&&p>=.9f&&p<=1.1f&&isfinite(a)&&a>=0&&a<=1&&isfinite(g)&&g>=0&&g<=1;}
int sd_voice_init(SdVoice *s,const SdProfile *m,uint64_t seed,float p,float a,float g){
    if(!s||!m||m->rate!=48000||m->window!=1024||m->hop!=256||m->harmonics<1||m->harmonics>SD_MAX_HARMONICS||m->components>SD_MAX_COMPONENTS||!isfinite(m->base_hz)||m->base_hz<5||m->harmonics*m->base_hz*1.1f>.45f*m->rate||!valid(p,a,g))return 0;
    memset(s,0,sizeof *s);s->model=m;s->pitch=s->pitch_target=p;s->amount=s->amount_target=a;s->gain=s->gain_target=g;s->follow=1-expf(-1/(.018f*m->rate));
    sd_texture_init(&s->texture,m,seed);sd_oscillator_init(&s->oscillator,m);return 1;
}
int sd_voice_set(SdVoice *s,float p,float a,float g){if(!s||!s->model||!valid(p,a,g))return 0;s->pitch_target=p;s->amount_target=a;s->gain_target=g;return 1;}
void sd_voice_process(SdVoice *s,float *stereo,unsigned frames){unsigned n;const SdProfile *m=s->model;float ratio=m->base_hz/(m->rate/(float)m->window);
    for(n=0;n<frames;++n){float out[2];sd_texture_prepare(&s->texture,m);
        s->pitch+=s->follow*(s->pitch_target-s->pitch);s->amount+=s->follow*(s->amount_target-s->amount);s->gain+=s->follow*(s->gain_target-s->gain);
        sd_oscillator_sample(&s->oscillator,&s->texture,m,s->amount,out);stereo[2*n]=out[0]*s->gain;stereo[2*n+1]=out[1]*s->gain;
        s->oscillator.phase+=2*PI*s->pitch/m->window*ratio;if(s->oscillator.phase>=2*PI)s->oscillator.phase-=2*PI;
        s->texture.fraction+=s->pitch/m->hop*ratio;++s->frame;
    }
}
