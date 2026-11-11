#define _CRT_SECURE_NO_WARNINGS
#include "residual_motion/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static RmVoice a,b,saved;
static SrVoice old;
static int require(int result,const char *message) {
    if(!result)printf("FAIL: %s\n",message);return result;
}
static RmProfile model(void) {
    RmProfile p={0};p.bands=2;p.factors=2;p.rho[0]=.7;p.rho[1]=.4;
    p.low[0]=1200;p.high[0]=2400;p.low[1]=2400;p.high[1]=6000;
    p.basis[0][0]=.08;p.basis[0][1]=.05;p.basis[1][0]=-.04;p.basis[1][1]=.1;return p;
}
static int read_text(const char *text,RmProfile *p) {
    FILE *f=tmpfile();int ok;if(!f)return 0;fputs(text,f);rewind(f);ok=rm_profile_read(f,p);fclose(f);return ok;
}
static int profile_checks(void) {
    RmProfile p=model(),q,keep;
    if(!require(rm_profile_valid(&p),"valid motion"))return 0;
    q=p;q.rho[0]=.96;if(!require(!rm_profile_valid(&q),"rho limit"))return 0;
    q=p;q.basis[0][0]=1;if(!require(!rm_profile_valid(&q),"positive-gain bound"))return 0;
    q=p;q.basis[0][0]=NAN;if(!require(!rm_profile_valid(&q),"nonfinite basis"))return 0;
    if(!require(read_text("VSL_RESIDUAL_MOTION 1 48000 480 1 1\n.5\n1200 2400 .1\n",&q),"read profile"))return 0;
    keep=q;
    if(!require(!read_text("VSL_RESIDUAL_MOTION 1 48000 480 1 1\n.5\n1200 2400 .1\ntrailing",&q)&&
                !memcmp(&q,&keep,sizeof q),"transactional trailing data"))return 0;
    if(!require(!read_text("VSL_RESIDUAL_MOTION 1 48000 480 1 1\n.5\n1200 2400 1\n",&q)&&
                !memcmp(&q,&keep,sizeof q),"transactional bound rejection"))return 0;
    return 1;
}
static int analytic_gain(void) {
    RmProfile p={0};RmEnvelope envelope;double gains[SR_MAX_BANDS];unsigned fraction,i,j;
    p.bands=1;p.factors=1;p.low[0]=1200;p.high[0]=2400;p.basis[0][0]=.5;
    for(fraction=0;fraction<480;fraction+=120) {
        double energy=0;
        for(i=0;i<2;++i)for(j=0;j<2;++j) {
            if(!rm_envelope_init(&envelope,&p,701,1))return 0;
            envelope.left[0]=i?1:-1;envelope.right[0]=j?1:-1;envelope.frame=fraction;
            rm_envelope_tick(&envelope,gains);energy+=gains[0]*gains[0]/4;
            if(!require(gains[0]>0&&gains[0]<1.76,"positive envelope"))return 0;
        }
        if(!require(fabs(energy-1)<1e-14,"exact expected energy over four Rademacher states"))return 0;
    }
    return 1;
}
int main(void) {
    SrProfile p={48000,2,16,{{1200,2400,{.001,.002},{.6,.2}},{2400,6000,{.002,.001},{0,0}}}};
    RmProfile motion=model(),bad;double whole[16384],split[16384],raw[16384],baseline[16384];unsigned at=0,n,i;
    if(!profile_checks()||!analytic_gain())return 1;
    if(!rm_voice_init(&a,&p,&motion,171,701,1,1,0)||!sr_voice_init(&old,&p,171,1,1))return 1;
    if(!rm_voice_process(&a,whole,raw,8192)||!sr_voice_process(&old,baseline,8192))return 1;
    if(!require(!memcmp(whole,baseline,sizeof whole)&&!memcmp(raw,baseline,sizeof raw)&&
                !memcmp(&a.source,&old,sizeof old),"zero amount samples and entire carrier state exact"))return 1;
    if(!rm_voice_init(&a,&p,&motion,171,701,1,1,1)||!rm_voice_init(&b,&p,&motion,171,701,1,1,1))return 1;
    rm_voice_process(&a,whole,raw,8192);
    while(at<8192){n=(at%137)+1;if(n>8192-at)n=8192-at;rm_voice_process(&b,split+2*at,NULL,n);at+=n;}
    if(!require(!memcmp(whole,split,sizeof whole)&&!memcmp(&a,&b,sizeof a),"arbitrary block determinism"))return 1;
    if(!sr_voice_init(&old,&p,171,1,1)||!sr_voice_process(&old,baseline,8192))return 1;
    if(!require(!memcmp(raw,baseline,sizeof raw)&&!memcmp(&a.source,&old,sizeof old),"motion never changes raw carriers"))return 1;
    saved=a;
    if(!require(!rm_voice_set(&a,1,1,NAN)&&!memcmp(&a,&saved,sizeof a)&&
                !rm_voice_set(&a,.8,1,1)&&!memcmp(&a,&saved,sizeof a),"invalid controls leave state unchanged"))return 1;
    bad=motion;bad.high[0]=2500;
    if(!require(!rm_voice_init(&a,&p,&bad,171,701,1,1,1)&&!memcmp(&a,&saved,sizeof a),"mismatched bands reject transactionally"))return 1;
    if(!require(!rm_voice_process(&a,whole,whole,1)&&!memcmp(&a,&saved,sizeof a)&&
                rm_voice_process(&a,NULL,NULL,0),"buffer contract"))return 1;
    if(!rm_voice_init(&a,&p,&motion,171,701,1,1,0)||!rm_voice_init(&b,&p,&motion,171,701,1,1,1))return 1;
    rm_voice_process(&a,whole,NULL,8192);rm_voice_process(&b,split,NULL,8192);
    if(!require(a.motion.seed==b.motion.seed&&!memcmp(a.motion.left,b.motion.left,sizeof a.motion.left)&&
                !memcmp(&a.source,&b.source,sizeof a.source),"zero amount advances independent motion RNG"))return 1;
    rm_voice_set(&a,1.07,1,1);rm_voice_set(&b,1.07,1,1);
    for(i=0;i<48000;++i) {
        rm_voice_process(&a,whole,NULL,1);rm_voice_process(&b,split,NULL,1);
        if(!isfinite(whole[0])||!isfinite(whole[1]))return 1;
        if(i>40000&&fabs(whole[0]-split[0])>1e-12)return 1;
    }
    p.band[0].power[1]=p.band[0].power[0];p.band[0].coherence[0]=1;p.band[0].coherence[1]=0;
    p.band[1].power[1]=p.band[1].power[0];p.band[1].coherence[0]=1;p.band[1].coherence[1]=0;
    if(!rm_voice_init(&a,&p,&motion,171,701,1,1,1))return 1;
    rm_voice_process(&a,whole,NULL,8192);for(i=0;i<8192;++i)if(whole[2*i]!=whole[2*i+1])return 1;
    puts("PASS: residual motion energy, raw/zero exactness, RNG, mono and deterministic controls");return 0;
}
