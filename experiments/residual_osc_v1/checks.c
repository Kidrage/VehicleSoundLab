#define _CRT_SECURE_NO_WARNINGS
#include "sound_residual/voice.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static SrVoice a,b,saved;
static int read_text(const char *text,SrProfile *profile) {
    FILE *f=tmpfile();int ok;if(!f)return 0;fputs(text,f);rewind(f);ok=sr_profile_read(f,profile);fclose(f);return ok;
}
static int run(void) {
    SrProfile p={48000,2,16,{{1200,2400,{.001,.002},{.6,.2}},{2400,6000,{.002,.001},{0,0}}}},old,invalid;
    double whole[16384],split[16384],silence[1024],frame[2];unsigned at=0,n,i;double energy=0;
    if(!sr_profile_valid(&p))return 0;old=p;
    if(!read_text("VSL_SOUND_RESIDUAL 1 48000 1 8\n1200 2400 .01 .02 .6 .2\n",&p))return 0;
    old=p;
    if(read_text("VSL_SOUND_RESIDUAL 1 48000 1 8\n1200 2400 .01 .02 1 1\n",&p)||memcmp(&old,&p,sizeof p))return 0;
    if(read_text("VSL_SOUND_RESIDUAL 1 48000 1 8\n1200 2400 .01 .02 .6 .2\ntrailing",&p)||memcmp(&old,&p,sizeof p))return 0;
    if(read_text("VSL_SOUND_RESIDUAL 1 48000 1 8\n1200 2400 nan .02 .6 .2\n",&p))return 0;
    invalid=p;invalid.band[0].power[0]=0;if(sr_profile_valid(&invalid))return 0;
    invalid=p;invalid.band[0].high=20000;if(sr_profile_valid(&invalid))return 0;
    invalid=p;invalid.partials=33;if(sr_profile_valid(&invalid))return 0;
    if(!sr_voice_init(&a,&p,171,1,1)||!sr_voice_init(&b,&p,171,1,1))return 0;
    if(!sr_voice_process(&a,whole,8192))return 0;
    while(at<8192) {n=(at%137)+1;if(n>8192-at)n=8192-at;if(!sr_voice_process(&b,split+2*at,n))return 0;at+=n;}
    if(memcmp(whole,split,sizeof whole))return 0;
    saved=a;
    if(sr_voice_set(&a,NAN,1)||memcmp(&a,&saved,sizeof a)||sr_voice_set(&a,1,-.1)||memcmp(&a,&saved,sizeof a))return 0;
    if(!sr_voice_process(&a,NULL,0)||sr_voice_process(&a,NULL,1))return 0;
    if(!sr_voice_set(&a,.9,.5)||!sr_voice_set(&b,.9,.5))return 0;
    for(i=0;i<1024;++i) {if(!sr_voice_process(&a,frame,1)||!sr_voice_process(&b,split,1)||memcmp(frame,split,2*sizeof(double)))return 0;}
    if(!sr_voice_init(&a,&p,171,1,0)||!sr_voice_init(&b,&p,171,1,1))return 0;
    if(!sr_voice_process(&a,silence,512)||!sr_voice_process(&b,split,512))return 0;
    for(i=0;i<1024;++i)if(silence[i]!=0)return 0;
    /* Gain cannot pause the hidden source: after reopening and settling the
       visible unmuted signals must converge on the same ongoing trajectory. */
    if(!sr_voice_set(&a,1,1))return 0;
    for(i=0;i<48000;++i) {
        if(!sr_voice_process(&a,frame,1)||!sr_voice_process(&b,split,1))return 0;
        if(!isfinite(frame[0])||!isfinite(frame[1]))return 0;
        if(i>40000&&fabs(frame[0]-split[0])>1e-12)return 0;
        energy+=frame[0]*frame[0];
    }
    if(energy<1)return 0;
    if(!sr_voice_init(&a,&p,172,1,1)||!sr_voice_process(&a,split,512)||!memcmp(split,whole,1024*sizeof(double)))return 0;
    return 1;
}
int main(void) {int ok=run();puts(ok?"PASS: residual profile, deterministic blocks, control rejection and silent clock":"FAIL: residual contract");return ok?0:1;}
