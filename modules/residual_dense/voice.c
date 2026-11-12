#include "voice.h"
#include <math.h>
#include <string.h>
static int valid(double pitch,double gain) {
    return isfinite(pitch)&&pitch>=.9&&pitch<=1.1&&isfinite(gain)&&gain>=0&&gain<=1;
}
int rd_voice_init(RdVoice *s,const SrProfile *p,const unsigned *counts,uint64_t seed,double pitch,double gain) {
    if(!s||!rd_counts_valid(p,counts)||!valid(pitch,gain))return 0;
    memset(s,0,sizeof *s);rd_cloud_init(&s->cloud,p,counts,seed);rd_cloud_tune(&s->cloud,pitch);
    s->pitch=s->pitch_target=pitch;s->gain=s->gain_target=gain;s->follow=1-exp(-1/(.018*48000));s->initialized=1;
    return 1;
}
int rd_voice_set(RdVoice *s,double pitch,double gain) {
    if(!s||!s->initialized||!valid(pitch,gain))return 0;
    s->pitch_target=pitch;s->gain_target=gain;return 1;
}
int rd_voice_process(RdVoice *s,double *out,unsigned frames) {
    unsigned n;if(!s||!s->initialized||(frames&&!out))return 0;
    for(n=0;n<frames;++n) {
        double raw[2];s->pitch+=s->follow*(s->pitch_target-s->pitch);s->gain+=s->follow*(s->gain_target-s->gain);
        if(s->frame%64==0)rd_cloud_tune(&s->cloud,s->pitch);
        rd_cloud_tick(&s->cloud,raw,s->frame%1024==0);
        out[2*n]=raw[0]*s->gain;out[2*n+1]=raw[1]*s->gain;++s->frame;
    }
    return 1;
}
