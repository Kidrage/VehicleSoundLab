#define _CRT_SECURE_NO_WARNINGS
#include "start_texture/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define REQUIRE(x) do{if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static StVoice a,b,old;
static SrCloud direct;
static double x[514],y[514],raw[514],other[514];
int main(void) {
    StProfile p={0},saved;FILE *f;unsigned n,c;double env=0;
    p.spectrum.rate=48000;p.spectrum.bands=2;p.spectrum.partials=8;
    p.spectrum.band[0]=(SrBand){300,800,{.02,.03},{.4,-.3}};
    p.spectrum.band[1]=(SrBand){1000,2000,{.01,.02},{-.1,.7}};
    p.attack_seconds=.005;p.release_seconds=.035;
    REQUIRE(st_profile_valid(&p));REQUIRE(st_voice_init(&a,&p,48271,1));
    sr_cloud_init(&direct,&p.spectrum,48271);sr_cloud_tune(&direct,1);
    REQUIRE(st_voice_set(&a,1,1));
    for(n=0;n<4800;++n) {
        double expected[2];sr_cloud_tick(&direct,expected,n%1024==0);
        REQUIRE(st_voice_process(&a,x,raw,1));env+=a.attack*(1-env);
        REQUIRE(env==a.envelope);
        for(c=0;c<2;++c){REQUIRE(raw[c]==expected[c]);REQUIRE(x[c]==expected[c]*env);}
    }
    REQUIRE(st_voice_set(&a,0,1));
    for(n=0;n<48000;++n){REQUIRE(st_voice_process(&a,x,raw,1));env+=a.release*(0-env);REQUIRE(env==a.envelope);}
    REQUIRE(a.envelope<1e-12);
    /* Equal-source phase history with different amounts, including a closed gate.
       Start a second time without resetting the continuous cloud. */
    REQUIRE(st_voice_init(&a,&p,48271,0));REQUIRE(st_voice_init(&b,&p,48271,1));
    for(n=0;n<96000;n+=1) {
        int gate=n<20000||(n>=50000&&n<70000);
        REQUIRE(st_voice_set(&a,gate,0));REQUIRE(st_voice_set(&b,gate,1));
        REQUIRE(st_voice_process(&a,x,raw,1));REQUIRE(st_voice_process(&b,y,other,1));
        REQUIRE(raw[0]==other[0]&&raw[1]==other[1]&&x[0]==0&&x[1]==0);
        REQUIRE(!memcmp(&a.cloud,&b.cloud,sizeof a.cloud));
    }
    /* A long held gate has no recording duration or implicit end/reset. */
    REQUIRE(st_voice_init(&a,&p,19,1));REQUIRE(st_voice_init(&b,&p,19,1));
    REQUIRE(st_voice_set(&a,1,1));REQUIRE(st_voice_set(&b,1,1));
    for(n=0;n<2000;++n) {
        REQUIRE(st_voice_process(&a,x,raw,257));
        for(c=0;c<257;++c)REQUIRE(st_voice_process(&b,&y[2*c],&other[2*c],1));
        REQUIRE(!memcmp(x,y,sizeof x)&&!memcmp(raw,other,sizeof raw));
    }
    REQUIRE(a.frame==514000&&a.envelope>.999999);REQUIRE(!memcmp(&a,&b,sizeof a));
    old=a;REQUIRE(!st_voice_set(&a,2,1));REQUIRE(!memcmp(&a,&old,sizeof a));
    REQUIRE(!st_voice_set(&a,0,NAN));REQUIRE(!st_voice_process(&a,x,x,1));
    REQUIRE(!memcmp(&a,&old,sizeof a));
    p.attack_seconds=0;REQUIRE(!st_voice_init(&a,&p,0,1));REQUIRE(!memcmp(&a,&old,sizeof a));p.attack_seconds=.005;
    /* Failed file load must not corrupt a previously usable profile. */
    saved=p;f=tmpfile();REQUIRE(f);fputs("VSL_START_TEXTURE 1 nan .035\nVSL_SOUND_RESIDUAL 1 48000 1 8\n300 800 .02 .03 0 0\n",f);rewind(f);
    REQUIRE(!st_profile_read(f,&p));REQUIRE(!memcmp(&p,&saved,sizeof p));fclose(f);
    puts("PASS analytic gate, legacy cloud identity, amount/phase isolation, second start, held10s, chunk1/257, transactional rejects");return 0;
}
