#define _CRT_SECURE_NO_WARNINGS
#include "catch_bloom/voice.h"
#include "catch_bloom/envelope.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define PI 3.14159265358979323846
#define REQUIRE(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);return 1;}} while(0)
static double input[96000],whole[96000],chunked[96000];
static CbProfile recipe(void) {
    CbProfile p={2,2,3,.005,.035,{{92,1.1,2},{240,.7,1}}};return p;
}
int main(void) {
    CbProfile p=recipe(),before,q;CbVoice a,b;CbFilter filter;
    unsigned i,j;double peak=0,energy=0,error=0;
    /* Polynomial beta bump and exponential step response are independent
       closed forms, not a second copy of the implementation recurrence. */
    for(i=0;i<=100;++i) {
        double u=i/100.,expected=pow(u/.4,2)*pow((1-u)/.6,3);
        REQUIRE(fabs(cb_pulse(u,2,3)-expected)<2e-15);
    }
    REQUIRE(cb_voice_init(&a,&p,1));REQUIRE(cb_voice_set(&a,1,.4,1));
    for(i=0;i<4800;++i){double x[2]={0},y[2];REQUIRE(cb_voice_process(&a,x,y,1));}
    REQUIRE(fabs(a.envelope-(1-exp(-4800./(48000*.005))))<2e-14);
    REQUIRE(cb_voice_set(&a,0,0,1));
    for(i=0;i<4800;++i){double x[2]={0},y[2];REQUIRE(cb_voice_process(&a,x,y,1));}
    REQUIRE(fabs(a.envelope-(1-exp(-20))*exp(-4800./(48000*.035)))<2e-14);
    /* Steady response against |H(e^jw)| computed as a complex ratio. */
    for(j=0;j<3;++j) {
        double hz=j==0?34:j==1?92:600,w=2*PI*hz/48000;
        double nr,ni,dr,di,expected,power=0;
        REQUIRE(cb_filter_init(&filter,92,1.1));
        nr=filter.b0+filter.b2*cos(2*w);ni=-filter.b2*sin(2*w);
        dr=1+filter.a1*cos(w)+filter.a2*cos(2*w);di=-filter.a1*sin(w)-filter.a2*sin(2*w);
        expected=.5*(nr*nr+ni*ni)/(dr*dr+di*di);
        for(i=0;i<96000;++i){double x[2]={sin(w*i),0},y[2];cb_filter_tick(&filter,x,y);if(i>=48000)power+=y[0]*y[0];REQUIRE(y[1]==0);}
        REQUIRE(fabs(power/48000-expected)<2e-10);
    }
    /* Long impulse decay, mono preservation and in-place/chunk contracts. */
    REQUIRE(cb_filter_init(&filter,20,8));
    for(i=0;i<480000;++i){double x[2]={i==0?1:0,i==0?1:0},y[2];cb_filter_tick(&filter,x,y);REQUIRE(isfinite(y[0])&&y[0]==y[1]);if(i>470000)energy+=y[0]*y[0];}
    REQUIRE(energy<1e-60);
    for(i=0;i<48000;++i){input[2*i]=.1*sin(2*PI*117*i/48000);input[2*i+1]=.07*cos(2*PI*63*i/48000);}
    REQUIRE(cb_voice_init(&a,&p,1)&&cb_voice_init(&b,&p,1));
    REQUIRE(cb_voice_set(&a,1,.4,1)&&cb_voice_set(&b,1,.4,1));
    REQUIRE(cb_voice_process(&a,input,whole,48000));
    memcpy(chunked,input,sizeof input);
    for(i=0;i<48000;i+=240)REQUIRE(cb_voice_process(&b,chunked+2*i,chunked+2*i,240));
    REQUIRE(!memcmp(whole,chunked,sizeof whole)&&!memcmp(&a,&b,sizeof a));
    REQUIRE(cb_voice_init(&b,&p,1)&&cb_voice_set(&b,1,.4,1));
    for(i=0;i<48000;++i)REQUIRE(cb_voice_process(&b,input+2*i,chunked+2*i,1));
    REQUIRE(!memcmp(whole,chunked,sizeof whole)&&!memcmp(&a,&b,sizeof a));
    REQUIRE(cb_voice_init(&a,&p,0)&&cb_voice_init(&b,&p,1));
    REQUIRE(cb_voice_set(&a,0,0,0)&&cb_voice_set(&b,1,.4,1));
    REQUIRE(cb_voice_process(&a,input,whole,48000)&&cb_voice_process(&b,input,chunked,48000));
    for(i=0;i<96000;++i){peak=fmax(peak,fabs(whole[i]));error=fmax(error,fabs(chunked[i]));}
    REQUIRE(peak==0&&error>.001&&!memcmp(a.filter,b.filter,sizeof a.filter));
    before=p;q=p;q.modes=0;REQUIRE(!cb_voice_init(&a,&q,1));
    REQUIRE(cb_voice_init(&a,&p,1));b=a;
    REQUIRE(!cb_voice_set(&a,1,NAN,1)&&!cb_voice_set(&a,2,.5,1)&&!cb_voice_set(&a,1,.5,2));
    REQUIRE(!memcmp(&a,&b,sizeof a));
    {FILE *f=tmpfile();REQUIRE(f);fputs("VSL_CATCH_BLOOM 1 1 2 3 .005 .035\n92 1 2 extra\n",f);rewind(f);
     REQUIRE(!cb_profile_read(f,&p)&&!memcmp(&p,&before,sizeof p));fclose(f);}
    {FILE *f=tmpfile();REQUIRE(f);fputs("VSL_CATCH_BLOOM 1 1 2 3 .005 .035\n92 1 2\n",f);rewind(f);
     REQUIRE(cb_profile_read(f,&q)&&q.modes==1&&q.mode[0].gain==2);fclose(f);}
    puts("PASS: analytic envelope, complex response, decay, stereo, zero-state, chunk/alias, validation/read transaction");return 0;
}
