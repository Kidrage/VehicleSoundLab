#include "core/engine.h"
#include "core/modules.h"
#include "spatial/scene.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
int main(void) {
    VslEngine *e=malloc(sizeof *e);VslObjectFrame o={0};double out[12];int i,c;
    VslParams p=vsl_default_params(0);double difference=0,sum=0;
    if(!e)return 2;vsl_init(e,48000,48271);
    e->smooth.width=1;e->smooth.space=0;vsl_scene_update(e,2);
    o.sample[VSL_EXHAUST_L]=1;vsl_scene_tick(e,&o,out,2);
    CHECK(out[0]>out[1],"left exhaust object routes to left speaker");
    vsl_init(e,48000,48271);e->smooth.width=1;e->smooth.space=0;vsl_scene_update(e,2);
    memset(&o,0,sizeof o);o.sample[VSL_EXHAUST_R]=1;vsl_scene_tick(e,&o,out,2);
    CHECK(out[1]>out[0],"right exhaust object routes to right speaker");
    e->smooth.width=0;e->smooth.space=.8;vsl_scene_update(e,2);
    for(i=0;i<5000;++i) { o.sample[VSL_EXHAUST_R]=sin(i*.2);vsl_scene_tick(e,&o,out,2);CHECK(out[0]==out[1],"width zero folds reflections and direct sound to mono"); }
    vsl_init(e,48000,48271);e->smooth.space=0;vsl_scene_update(e,12);
    for(i=0;i<VSL_OBJECTS;++i) {
        double energy=0;
        for(c=0;c<8;++c)if(c!=3)energy+=e->spatial.gain[i][c]*e->spatial.gain[i][c];
        CHECK(fabs(energy-1)<1e-10,"bed panning has unit energy per object");
        for(c=8;c<12;++c)CHECK(e->spatial.gain[i][c]==0,"dry engine is not copied to ceiling");
    }
    p.rpm=5000;p.load=.8;p.width=.8;vsl_set_params(e,&p);
    for(i=0;i<400;++i) {
        float audio[512];vsl_process(e,audio,256);
        if(i>200)for(c=0;c<256;++c) { double l=audio[c*2],r=audio[c*2+1];difference+=(l-r)*(l-r);sum+=l*l+r*r; }
    }
    CHECK(difference/sum>.001,"running engine has independently rendered stereo content");
    p.ignition=0;vsl_set_params(e,&p);
    for(i=0;i<500;++i) { float audio[512];vsl_process(e,audio,256); }
    CHECK(fabs(e->objects.sample[VSL_EXHAUST_L])<1e-12,"no residual combustion after shutdown settles");
    {
        float audio[12*256],stems[256*VSL_OBJECTS];
        p.ignition=1;++p.start_id;vsl_set_params(e,&p);
        for(i=0;i<300;++i) {
            CHECK(vsl_process_layout(e,audio,256,12,stems),"12 channel renderer accepts layout");
            for(c=0;c<12*256;++c)CHECK(isfinite(audio[c]) && fabs(audio[c])<=.95001,"12 channels remain finite");
        }
        CHECK(!vsl_process_layout(e,audio,1,6,NULL),"unsupported layouts rejected");
    }
    {
        VslEngine *b=malloc(sizeof *b);float a_audio[512],b_audio[3072],a_stems[256*VSL_OBJECTS],b_stems[256*VSL_OBJECTS];
        CHECK(b!=NULL,"allocate second layout");if(!b) { free(e);return 2; }
        p=vsl_default_params(0);p.drive_mode=VSL_AUTODRIVE;vsl_init(e,48000,48271);vsl_init(b,48000,48271);
        vsl_set_params(e,&p);vsl_set_params(b,&p);
        for(i=0;i<5700;++i) {
            vsl_process_layout(e,a_audio,256,2,a_stems);vsl_process_layout(b,b_audio,256,12,b_stems);
            CHECK(!memcmp(a_stems,b_stems,sizeof a_stems),"layout never changes source stems");
            CHECK(e->drive.rpm==b->drive.rpm && e->drive.gear==b->drive.gear,"layout never changes vehicle state");
        }
        free(b);
    }
    free(e);if(!failures)puts("PASS: object routing, mono fold, bed energy, ceiling policy, stereo content, shutdown and 12 channels");
    return failures?1:0;
}
