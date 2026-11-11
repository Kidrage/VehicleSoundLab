#include "core/engine.h"
#include "core/character.h"
#include "core/response_kernel.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void live_control(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p=vsl_default_params(0);
    float x[514],y[514];unsigned block,i,changed=0;uint64_t strikes;double before;
    CHECK(a&&b,"engines allocated");if(!a||!b)goto done;
    p.rpm=4000;p.load=.85;p.pressure_texture=p.structure_transfer=.65;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_set_params(a,&p);p.response_shape=1;vsl_set_params(b,&p);
    vsl_process(a,x,1);vsl_process(b,y,1);
    CHECK(b->smooth.response_shape>0&&b->smooth.response_shape<.002,"shape smooths per sample");
    for(block=0;block<400;++block) {
        vsl_process(a,x,257);vsl_process(b,y,257);
        for(i=0;i<514;++i) { CHECK(isfinite(y[i]),"finite candidate");if(x[i]!=y[i])++changed; }
        CHECK(!memcmp(&a->drive,&b->drive,sizeof a->drive),"shape cannot alter full driving state");
        CHECK(!memcmp(&a->character,&b->character,sizeof a->character),"original event/RNG/character states retained");
    }
    CHECK(changed>1000,"live shape affects audible output samples");
    CHECK(b->response.pressure_events==vsl_character_events(&b->character),"one pressure response per permitted native strike");
    before=b->smooth.response_shape;p.response_shape=0;vsl_set_params(b,&p);vsl_process(b,y,1);
    CHECK(b->smooth.response_shape<before&&b->smooth.response_shape>0,"shape release is continuous");
    p.ignition=0;vsl_set_params(b,&p);vsl_process(b,y,240);strikes=b->response.pressure_events;
    for(block=0;block<200;++block)vsl_process(b,y,257);
    CHECK(b->response.pressure_events==strikes,"shutdown denies new shape strikes while tails advance");
    p.response_shape=NAN;vsl_set_params(b,&p);CHECK(b->target.response_shape==0,"nonfinite shape clamps");
    p.response_shape=1.3;vsl_set_params(b,&p);CHECK(b->target.response_shape==1,"shape unit range");
done:free(a);free(b);
}
static void layout_blocks(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b),*c=malloc(sizeof *c);
    VslParams p=vsl_default_params(0);float x[514],y[514],bed[257*12],sa[257*VSL_OBJECTS],sb[257*VSL_OBJECTS];
    unsigned block,i;CHECK(a&&b&&c,"layout engines allocated");if(!a||!b||!c)goto done;
    p.rpm=8000;p.load=.85;p.pressure_texture=p.structure_transfer=.65;p.response_shape=.73123456789;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_init(c,48000,48271);
    vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_set_params(c,&p);
    for(block=0;block<400;++block) {
        for(i=0;i<257;++i)vsl_process(a,x+i*2,1);
        vsl_process_layout(b,y,257,2,sa);vsl_process_layout(c,bed,257,12,sb);
        CHECK(!memcmp(x,y,sizeof x),"shape sample bits independent of host block size");
        CHECK(!memcmp(a,b,sizeof *a),"complete same-layout state independent of blocks");
        CHECK(!memcmp(sa,sb,sizeof sa),"all10 shape sources independent of layout");
        CHECK(!memcmp(&b->response,&c->response,sizeof b->response),"complete response state independent of layout");
    }
done:free(a);free(b);free(c);
}
static void eligibility(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p;float x[514],y[514];int profile;unsigned block;
    CHECK(a&&b,"eligibility engines allocated");if(!a||!b)goto done;
    for(profile=0;profile<6;++profile) {
        p=vsl_default_params(profile<5?profile:0);p.pressure_texture=p.structure_transfer=.65;
        if(profile==0)p.pure_osc=1;
        vsl_init(a,48000,48271);vsl_init(b,48000,48271);
        if(profile==5) { a->dna.custom_count=b->dna.custom_count=1;a->dna.custom_root=b->dna.custom_root=66;a->dna.custom_amp[0]=b->dna.custom_amp[0]=1; }
        vsl_set_params(a,&p);p.response_shape=1;vsl_set_params(b,&p);
        for(block=0;block<200;++block) {
            vsl_process(a,x,257);vsl_process(b,y,257);
            CHECK(!memcmp(x,y,sizeof x),"other templates/import/Pure OSC exact bypass");
        }
        CHECK(b->response.pressure_events==0&&b->response.structure_events==0,"ineligible shape event denial");
    }
done:free(a);free(b);
}
int main(void) {
    live_control();layout_blocks();eligibility();
    if(!failures)puts("Native shape control,smoothing,firing permission,blocks,layouts and eligibility pass.");return failures?1:0;
}
