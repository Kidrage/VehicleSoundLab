#define _CRT_SECURE_NO_WARNINGS
#include "body.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define PI 3.14159265358979323846
int lb_profile_load(const char *path,LbProfile *profile){
    FILE *f;char magic[40],extra;unsigned version,rate,count,h,c;LbProfile candidate;int ok=0;
    if(!path||!profile||!(f=fopen(path,"rb")))return 0;
    if(fscanf(f,"%39s %u %u %u",magic,&version,&rate,&count)!=4||strcmp(magic,"VSL_LOW_BODY")||version!=1||rate!=48000||count!=3)goto done;
    for(h=0;h<3;++h)for(c=0;c<2;++c)if(fscanf(f,"%lf",&candidate.coefficient[h][c])!=1||!isfinite(candidate.coefficient[h][c])||fabs(candidate.coefficient[h][c])>.25)goto done;
    if(fscanf(f," %c",&extra)==1)goto done;
    *profile=candidate;ok=1;
done:fclose(f);return ok;
}
static int valid(double pitch,double amount,double envelope){return isfinite(pitch)&&pitch>=.9&&pitch<=1.1&&isfinite(amount)&&amount>=0&&amount<=1&&isfinite(envelope)&&envelope>=.5&&envelope<=1.5;}
int lb_init(LbSource *s,const LbProfile *p,double pitch,double amount){
    if(!s||!p||!valid(pitch,amount,1))return 0;memset(s,0,sizeof *s);s->profile=p;s->pitch=s->target_pitch=pitch;
    s->amount=s->target_amount=amount;s->envelope=s->target_envelope=1;
    s->follow=1-exp(-1/(.018*48000));s->envelope_follow=1-exp(-1/(.080*48000));return 1;
}
int lb_set(LbSource *s,double pitch,double amount,double envelope){
    if(!s||!s->profile||!valid(pitch,amount,envelope))return 0;s->target_pitch=pitch;s->target_amount=amount;s->target_envelope=envelope;return 1;
}
void lb_process(LbSource *s,double *mono,unsigned frames){
    unsigned n,h;for(n=0;n<frames;++n){double y=0;
        s->pitch+=s->follow*(s->target_pitch-s->pitch);s->amount+=s->follow*(s->target_amount-s->amount);s->envelope+=s->envelope_follow*(s->target_envelope-s->envelope);
        for(h=0;h<3;++h)y+=s->profile->coefficient[h][0]*cos((h+1)*s->phase)-s->profile->coefficient[h][1]*sin((h+1)*s->phase);
        mono[n]=y*s->amount*s->envelope;s->phase+=2*PI*s->pitch/1024;if(s->phase>=2*PI)s->phase-=2*PI;
    }
}
