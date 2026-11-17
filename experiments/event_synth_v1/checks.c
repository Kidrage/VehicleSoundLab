#include "event_synth/api.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"event check %d: %s\n",__LINE__,#x);return 3;}}while(0)
static EsProfile profiles[ES_TYPES];
static EsPool pool,other;
int main(void) {
    unsigned k,n;EsFrame f,g;EsNotice notes[ES_LOG_CAPACITY];double energy=0;
    EsRequest request={1,0,ES_AFTERFIRE,10,123,.7,1,1,1};
    for(k=0;k<ES_TYPES;++k) {
        profiles[k].mode_count=1;profiles[k].band_count=1;
        profiles[k].duration_seconds=.1;profiles[k].release_seconds=.01;profiles[k].level=1;
        profiles[k].modes[0]=(EsMode){200,.1,0,.03,200};
        profiles[k].bands[0]=(EsBand){2000,.7,.03,.001,.01};
    }
    CHECK(es_pool_init(&pool,profiles));CHECK(es_pool_init(&other,profiles));
    CHECK(es_pool_start(&pool,&request)==1&&es_pool_start(&other,&request)==1);
    for(n=0;n<4800;++n) {
        CHECK(es_pool_tick(&pool,&f)&&es_pool_tick(&other,&g));CHECK(!memcmp(&f,&g,sizeof f));
        CHECK(f.id[0]==1&&f.type[0]==ES_AFTERFIRE&&isfinite(f.sample[0]));energy+=f.sample[0]*f.sample[0];
    }
    CHECK(energy>0&&es_pool_active(&pool)==0&&pool.frame==4800);
    CHECK(es_pool_notices(&pool,notes,128)==2&&notes[0].frame==0&&notes[0].action==ES_STARTED&&notes[1].frame==4800&&notes[1].action==ES_ENDED);
    /* Analytical zero-noise oscillator, independent of random generator. */
    for(k=0;k<ES_TYPES;++k)profiles[k].band_count=0;
    CHECK(es_pool_init(&pool,profiles));request.strength=1;
    CHECK(es_pool_start(&pool,&request)==1);
    /* Common event offset for seed123 is fixed by xorshift32's first word. */
    {uint32_t s=123;s^=s<<13;s^=s>>17;s^=s<<5;
     double hz=200*(1+.002*(2*(s/4294967296.)-1));
     for(n=0;n<1000;++n){CHECK(es_pool_tick(&pool,&f));CHECK(fabs(f.sample[0]-.1*exp(-(double)n/(48000*.03))*sin(2*3.14159265358979323846*hz*n/48000))<2e-13);}}
    /* Colouring belongs only to procedural noise, never the mechanical modes. */
    profiles[ES_AFTERFIRE].noise_lowpass_hz=6000;CHECK(es_pool_init(&pool,profiles));
    profiles[ES_AFTERFIRE].noise_lowpass_hz=0;CHECK(es_pool_init(&other,profiles));
    CHECK(es_pool_start(&pool,&request)==1&&es_pool_start(&other,&request)==1);
    for(n=0;n<1000;++n){CHECK(es_pool_tick(&pool,&f)&&es_pool_tick(&other,&g));CHECK(!memcmp(&f,&g,sizeof f));}
    profiles[ES_AFTERFIRE].noise_lowpass_hz=100;CHECK(!es_profile_valid(profiles+ES_AFTERFIRE));
    profiles[ES_AFTERFIRE].noise_lowpass_hz=NAN;CHECK(!es_profile_valid(profiles+ES_AFTERFIRE));
    profiles[ES_AFTERFIRE].noise_lowpass_hz=0;
    /* Independent smoothstep attack; no phase/time reset or noise change. */
    profiles[ES_AFTERFIRE].modes[0].attack_seconds=.02;
    CHECK(es_pool_init(&pool,profiles)&&es_pool_start(&pool,&request)==1);
    profiles[ES_AFTERFIRE].modes[0].attack_seconds=0;
    CHECK(es_pool_init(&other,profiles)&&es_pool_start(&other,&request)==1);
    for(n=0;n<1500;++n) {
        double t=fmin(1,(double)n/(ES_RATE*.02));double a=t*t*(3-2*t);
        CHECK(es_pool_tick(&pool,&f)&&es_pool_tick(&other,&g));
        CHECK(fabs(f.sample[0]-g.sample[0]*a)<2e-15);
        CHECK(pool.voices[0].modes[0].phase==other.voices[0].modes[0].phase);
        CHECK(pool.voices[0].rng==other.voices[0].rng);
    }
    profiles[ES_AFTERFIRE].modes[0].attack_seconds=-.01;CHECK(!es_profile_valid(profiles+ES_AFTERFIRE));
    profiles[ES_AFTERFIRE].modes[0].attack_seconds=NAN;CHECK(!es_profile_valid(profiles+ES_AFTERFIRE));
    profiles[ES_AFTERFIRE].modes[0].attack_seconds=2.01;CHECK(!es_profile_valid(profiles+ES_AFTERFIRE));
    profiles[ES_AFTERFIRE].modes[0].attack_seconds=0;
    CHECK(es_pool_init(&pool,profiles));
    for(k=0;k<4;++k){request.id=k+1;CHECK(es_pool_start(&pool,&request)==1);}
    request.id=1;CHECK(es_pool_start(&pool,&request)==0); /* Duplicate active ID. */
    request.id=5;CHECK(es_pool_start(&pool,&request)==0); /* Equal priority capacity. */
    request.priority=100;CHECK(es_pool_start(&pool,&request)==2&&es_pool_active(&pool)==4);
    for(n=0;n<144;++n){CHECK(es_pool_tick(&pool,&f));CHECK(f.id[0]==1&&es_pool_active(&pool)==4);}
    CHECK(es_pool_tick(&pool,&f)&&f.id[0]==5&&pool.peak_active==4);
    unsigned count=es_pool_notices(&pool,notes,128);int old_end=0,new_start=0;
    for(k=0;k<count;++k) {
        if(notes[k].id==1&&notes[k].action==ES_ENDED){CHECK(notes[k].frame==144&&notes[k].reason==ES_STOLEN);old_end=1;}
        if(notes[k].id==5&&notes[k].action==ES_STARTED){CHECK(notes[k].frame==144&&notes[k].requested_frame==0);new_start=1;}
    }
    CHECK(old_end&&new_start);
    es_pool_release(&pool,-1,.005);
    for(n=0;n<240;++n)CHECK(es_pool_tick(&pool,&f));
    CHECK(es_pool_active(&pool)==0);
    /* Unknown timbre is explicit; no fallback voice or PCM. */
    profiles[ES_AFTERFIRE].mode_count=0;CHECK(es_pool_init(&pool,profiles));request.id=9;
    CHECK(es_pool_start(&pool,&request)==0&&pool.rejected==1);
    CHECK(es_pool_notices(&pool,notes,128)==1&&notes[0].reason==ES_UNAVAILABLE);
    profiles[0].modes[0].hz=NAN;CHECK(!es_pool_init(&pool,profiles));
    puts("PASS deterministic event synthesis, analytical OSC, 4-voice bound, priority fade/identity, release, missing profile, validation");return 0;
}
