#include "response.h"
#include "profile.h"
#include "core/modules.h"
#include "core/character.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#define CHECK(x) do { if(!(x)) { printf("FAIL line %d: %s\n",__LINE__,#x);return 0; } } while(0)
static double energy(const VslCharacterMode *m,unsigned count,double shape) {
    VslResponseKernel k;double w[VSL_RESPONSE_MAX_MODES],sum=0;unsigned i;
    vsl_response_kernel_init(&k,m,count,192000);
    for(i=0;i<count;++i)w[i]=m[i].weight;
    vsl_response_kernel_strike(&k,w,1,shape,0);
    for(i=0;i<192000/2;++i) {
        double x=vsl_response_kernel_read(&k);CHECK(isfinite(x));sum+=x*x;vsl_response_kernel_advance(&k);
    }
    return sum/192000;
}
static int impulse_energy(void) {
    const VslCharacterProfile *p=vsl_character_profile();double shape;
    double pressure=energy(p->pressure,VSL_CHARACTER_PRESSURE_MODES,0);
    double structure=energy(p->structure,VSL_CHARACTER_STRUCTURE_MODES,0);
    CHECK(pressure>0&&structure>0);
    for(shape=-1;shape<=1;shape+=.25) {
        CHECK(fabs(energy(p->pressure,VSL_CHARACTER_PRESSURE_MODES,shape)/pressure-1)<2e-6);
        CHECK(fabs(energy(p->structure,VSL_CHARACTER_STRUCTURE_MODES,shape)/structure-1)<2e-6);
    }
    CHECK(vsl_response_coordinate(1200,0,0,1)<0);
    CHECK(vsl_response_coordinate(8000,1,0,1)>0);
    CHECK(vsl_response_coordinate(5000,.7,.3,0)==0);
    return 1;
}
static int integration(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslResponseShape s;
    VslParams p=vsl_default_params(VSL_V10);float x[2],y[2];unsigned i;uint64_t fired;
    CHECK(a&&b);p.pressure_texture=p.structure_transfer=.65;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_set_params(a,&p);vsl_set_params(b,&p);
    vsl_response_init(&s,48000,0);
    for(i=0;i<48000*3;++i) {
        vsl_process(a,x,1);vsl_response_process(b,&s,y,1,2,NULL);
        CHECK(!memcmp(x,y,sizeof x));CHECK(!memcmp(a,b,sizeof *a));
    }
    CHECK(s.pressure_events==vsl_character_events(&b->character));
    CHECK(s.structure_events==s.pressure_events);
    s.amount=1;p.ignition=0;vsl_set_params(b,&p);
    /* Capture count immediately after permission is removed by drive update. */
    vsl_response_process(b,&s,y,1,2,NULL);fired=s.pressure_events;
    for(i=0;i<48000;++i)vsl_response_process(b,&s,y,1,2,NULL);
    CHECK(s.pressure_events==fired);CHECK(s.structure_events==fired);
    free(a);free(b);return 1;
}
static int eligibility(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslResponseShape s;
    VslParams p;float x[514],y[514];int profile;unsigned block;
    CHECK(a&&b);
    for(profile=0;profile<6;++profile) {
        p=vsl_default_params(profile<5?profile:0);p.pressure_texture=p.structure_transfer=.65;
        if(profile==0)p.pure_osc=1;
        vsl_init(a,48000,48271);vsl_init(b,48000,48271);
        if(profile==5) {
            a->dna.custom_count=b->dna.custom_count=1;a->dna.custom_root=b->dna.custom_root=66;
            a->dna.custom_amp[0]=b->dna.custom_amp[0]=1;
        }
        vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_response_init(&s,48000,1);
        for(block=0;block<200;++block) {
            vsl_process(a,x,257);vsl_response_process(b,&s,y,257,2,NULL);
            CHECK(!memcmp(x,y,sizeof x));CHECK(!memcmp(a,b,sizeof *a));
        }
        CHECK(s.pressure_events==0&&s.structure_events==0);
    }
    free(a);free(b);return 1;
}
static int block_sizes(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslResponseShape sa,sb;
    VslParams p=vsl_default_params(VSL_V10);float x[514],y[514];unsigned block,i;
    CHECK(a&&b);p.rpm=8000;p.load=.85;p.pressure_texture=p.structure_transfer=.65;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_set_params(a,&p);vsl_set_params(b,&p);
    vsl_response_init(&sa,48000,1);vsl_response_init(&sb,48000,1);
    for(block=0;block<400;++block) {
        for(i=0;i<257;++i)vsl_response_process(a,&sa,x+2*i,1,2,NULL);
        vsl_response_process(b,&sb,y,257,2,NULL);
        CHECK(!memcmp(x,y,sizeof x));CHECK(!memcmp(a,b,sizeof *a));CHECK(!memcmp(&sa,&sb,sizeof sa));
    }
    free(a);free(b);return 1;
}
int main(void) {
    if(!impulse_energy()||!integration()||!eligibility()||!block_sizes())return 2;
    puts("response energy, coordinates, bypass/state identity, firing denial, eligibility and block-size determinism pass");return 0;
}
