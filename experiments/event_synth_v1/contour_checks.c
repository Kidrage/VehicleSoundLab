#include "event_synth/api.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"contour check %d: %s\n",__LINE__,#x);return 3;}}while(0)
static EsProfile bank[ES_TYPES];static EsPool shaped,plain;
int main(void) {
    EsRequest r={1,0,ES_CATCH,100,27431,1,1,2,1};EsFrame a,b;unsigned k,n;
    for(k=0;k<ES_TYPES;++k) {
        bank[k].duration_seconds=.4;bank[k].release_seconds=.025;bank[k].level=1;bank[k].gated=1;
        bank[k].mode_count=1;bank[k].modes[0]=(EsMode){200,.1,.3,.2,200,0};
    }
    CHECK(es_pool_init(&plain,bank));
    bank[ES_CATCH].contours[0]=(EsContour){3,100,300,{0,.1,.2},{0,1,.2}};
    CHECK(es_pool_init(&shaped,bank));CHECK(es_pool_start(&plain,&r)==1&&es_pool_start(&shaped,&r)==1);
    for(n=0;n<30000;++n) {
        double t=(double)n/(ES_RATE*2),gain=t<.1?t/.1:t<.2?1-(t-.1)*8:.2;
        CHECK(es_pool_tick(&shaped,&a)&&es_pool_tick(&plain,&b));CHECK(fabs(a.sample[0]-b.sample[0]*gain)<3e-15);
        CHECK(shaped.voices[0].rng==plain.voices[0].rng);
        CHECK(shaped.voices[0].modes[0].phase==plain.voices[0].modes[0].phase);
    }
    es_pool_release(&shaped,ES_CATCH,.01);for(n=0;n<480;++n)CHECK(es_pool_tick(&shaped,&a));CHECK(!es_pool_active(&shaped));
    bank[ES_CATCH].contours[0].count=1;CHECK(!es_profile_valid(bank+ES_CATCH));
    bank[ES_CATCH].contours[0].count=3;bank[ES_CATCH].contours[1]=bank[ES_CATCH].contours[0];CHECK(!es_profile_valid(bank+ES_CATCH));
    memset(bank[ES_CATCH].contours+1,0,sizeof(EsContour));bank[ES_CATCH].contours[0].gain[1]=NAN;CHECK(!es_profile_valid(bank+ES_CATCH));
    bank[ES_CATCH].contours[0].gain[1]=1;CHECK(es_profile_valid(bank+ES_CATCH));
    puts("PASS contour timing follows decay, OSC phase/RNG preserved, release and invalid profiles");return 0;
}
