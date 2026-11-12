#include "residual_dense/voice.h"
#include "sound_residual/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static RdVoice a,b,saved;
static SrVoice old;
static double whole[16384],split[16384],x[1024],y[1024];
static int parity(void) {
    SrProfile p={48000,2,32,{{1200,2400,{.001,.002},{.6,.2}},{2400,6000,{.002,.001},{0,0}}}};
    unsigned counts[SR_MAX_BANDS]={32,32},seed,at,n,step;
    for(seed=0;seed<4;++seed) {
        if(!sr_voice_init(&old,&p,171+seed,1,1)||!rd_voice_init(&a,&p,counts,171+seed,1,1))return 0;
        for(step=0;step<8;++step) {
            double pitch=step%2?.9:1.1,gain=step%3?.7:0;
            if(!sr_voice_set(&old,pitch,gain)||!rd_voice_set(&a,pitch,gain))return 0;
            for(at=0;at<2048;at+=n) {
                n=1+at%511;if(n>2048-at)n=2048-at;
                if(!sr_voice_process(&old,x,n)||!rd_voice_process(&a,y,n)||memcmp(x,y,2*n*sizeof *x))return 0;
                if(old.cloud.count!=a.cloud.count||memcmp(old.cloud.oscillator,a.cloud.oscillator,old.cloud.count*sizeof(SrOscillator)))return 0;
                if(old.frame!=a.frame||old.pitch!=a.pitch||old.gain!=a.gain)return 0;
            }
        }
    }
    return 1;
}
static int dense(void) {
    SrProfile p={48000,2,32,{{1200,2400,{.001,.001},{1,0}},{2400,6000,{.002,.002},{1,0}}}},invalid;
    unsigned counts[SR_MAX_BANDS]={64,256},at=0,n,i;
    if(!rd_voice_init(&a,&p,counts,31,1,1)||!rd_voice_init(&b,&p,counts,31,1,1))return 0;
    if(!rd_voice_process(&a,whole,8192))return 0;
    while(at<8192) {n=at%137+1;if(n>8192-at)n=8192-at;if(!rd_voice_process(&b,split+2*at,n))return 0;at+=n;}
    if(memcmp(whole,split,sizeof whole)||memcmp(&a,&b,sizeof a))return 0;
    for(i=0;i<8192;++i)if(whole[2*i]!=whole[2*i+1]||!isfinite(whole[2*i]))return 0;
    saved=a;
    if(rd_voice_set(&a,NAN,1)||memcmp(&a,&saved,sizeof a)||rd_voice_set(&a,1,-.1)||memcmp(&a,&saved,sizeof a))return 0;
    counts[0]=257;if(rd_voice_init(&a,&p,counts,31,1,1)||memcmp(&a,&saved,sizeof a))return 0;
    counts[0]=0;if(rd_voice_init(&a,&p,counts,31,1,1)||memcmp(&a,&saved,sizeof a))return 0;
    counts[0]=8;invalid=p;invalid.band[0].power[0]=NAN;
    if(rd_voice_init(&a,&invalid,counts,31,1,1)||memcmp(&a,&saved,sizeof a))return 0;
    if(!rd_voice_process(&a,NULL,0)||rd_voice_process(&a,NULL,1)||memcmp(&a,&saved,sizeof a))return 0;
    if(!rd_voice_init(&a,&p,counts,31,1,0)||!rd_voice_init(&b,&p,counts,31,1,1))return 0;
    memset(&p,0,sizeof p);memset(counts,0,sizeof counts);
    if(!rd_voice_process(&a,x,512)||!rd_voice_process(&b,y,512))return 0;
    for(i=0;i<1024;++i)if(x[i]!=0||!isfinite(y[i]))return 0;
    if(memcmp(&a.cloud,&b.cloud,sizeof a.cloud)||a.frame!=b.frame)return 0;
    return 1;
}
int main(void) {
    if(!parity()) {puts("FAIL: old32 sample/state parity");return 1;}
    if(!dense()) {puts("FAIL: dense chunk/mono/ownership/invalid/silent-clock");return 2;}
    puts("PASS: old32 active state/sample parity; dense chunks, mono, ownership, controls and silent clock");return 0;
}
