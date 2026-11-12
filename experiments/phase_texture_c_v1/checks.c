#include "phase_texture/voice.h"
#include "dna_scene/scene.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define PI 3.14159265358979323846
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line%d: %s\n",__LINE__,#x);return 0;}}while(0)
static SdProfile model;
static SdVoice original,adapted;
static PtVoice phase;
static void fixture(unsigned harmonics) {
    unsigned h;memset(&model,0,sizeof model);
    model.rate=48000;model.window=1024;model.hop=256;model.base_hz=250;model.harmonics=harmonics;
    for(h=0;h<harmonics;++h) {
        double p=.23*(h+1);model.harmonic[h].mean[0]=.003*cos(p);model.harmonic[h].mean[1]=.003*sin(p);
        model.harmonic[h].mean[2]=.002*cos(-p);model.harmonic[h].mean[3]=.002*sin(-p);
    }
}
static int direct_and_bypass(void) {
    unsigned n,h,c;double maximum=0;
    fixture(24);
    CHECK(sd_voice_init(&original,&model,31,1,1,1));adapted=original;
    CHECK(pt_voice_init(&phase,&model,917,0));
    for(n=0;n<70001;++n) {
        double a[2],b[2];
        if(n==1000){CHECK(sd_voice_set(&original,.9,.4,.3));CHECK(sd_voice_set(&adapted,.9,.4,.3));}
        if(n==40000){CHECK(sd_voice_set(&original,1.1,1,1));CHECK(sd_voice_set(&adapted,1.1,1,1));}
        sd_voice_process(&original,a,1);pt_voice_tick(&phase,&adapted,b);
        CHECK(!memcmp(a,b,sizeof a)&&!memcmp(&original,&adapted,sizeof original));
    }
    CHECK(sd_voice_init(&adapted,&model,31,1,1,1));CHECK(pt_voice_init(&phase,&model,917,1));
    for(n=0;n<140003;++n) {
        double out[2],delay;pt_voice_tick(&phase,&adapted,out);delay=phase.motion.last_seconds;
        CHECK(isfinite(delay)&&fabs(delay)<=4e-6);
        for(c=0;c<2;++c) {
            double expected=0;
            for(h=0;h<model.harmonics;++h) {
                double f=(h+1)*model.base_hz,phi=2*PI*f*n/48000+(c?-.23:.23)*(h+1);
                double x=fmin(1,fmax(0,(f-1200)/700)),mask=.5-.5*cos(PI*x);
                expected+=(c?.002:.003)*(cos(phi)+mask*(cos(phi+2*PI*f*delay)-cos(phi)));
            }
            maximum=fmax(maximum,fabs(out[c]-expected));
        }
    }
    CHECK(maximum<2e-11);
    {PtVoice saved=phase;CHECK(!pt_voice_set(&phase,NAN)&&!pt_voice_set(&phase,1.01));CHECK(!memcmp(&saved,&phase,sizeof saved));}
    printf("direct OSC max error %.9g FS; exact bypass/clock/RNG over70001samples\n",maximum);
    return 1;
}
static int low_unchanged(void) {
    unsigned n;fixture(4);
    CHECK(sd_voice_init(&original,&model,7,1.1,1,1));adapted=original;
    CHECK(pt_voice_init(&phase,&model,917,1));
    for(n=0;n<4097;++n) {double a[2],b[2];sd_voice_process(&original,a,1);pt_voice_tick(&phase,&adapted,b);CHECK(!memcmp(a,b,sizeof a));}
    return 1;
}
static DsScene scene[2];static VslEngine spatial[2];
static float outputs[2][4097*2],dna[2][4097*2],low[2][4097*2];
static int scene_chunking(void) {
    DsSceneConfig config={{0},DS_OBSERVE_LEFT,DS_ROUTE_PAIR,2};
    DsSceneControl control={{1,1,1,1,1,1},.5,1,0,0,0};unsigned i,at;
    fixture(24);config.source.dna=config.source.low=&model;
    config.source.dna_seed=config.source.low_seed=48271;config.source.low_scale=1.6;config.source.phase_seed=917;
    for(i=0;i<2;++i) {
        CHECK(ds_scene_init(&scene[i],&spatial[i],&config,&control));
        for(at=0;at<4097;) {
            unsigned n=i?1:257;DsCapture capture={0};if(n>4097-at)n=4097-at;
            capture.dna_raw=dna[i]+2*at;capture.low_raw=low[i]+2*at;
            CHECK(ds_scene_process(&scene[i],outputs[i]+2*at,n,&capture));at+=n;
        }
    }
    CHECK(!memcmp(outputs[0],outputs[1],sizeof outputs[0]));
    CHECK(!memcmp(dna[0],dna[1],sizeof dna[0])&&!memcmp(low[0],low[1],sizeof low[0]));
    control.source.phase_texture=0;CHECK(ds_scene_init(&scene[1],&spatial[1],&config,&control));
    {DsCapture c={0};c.low_raw=low[1];CHECK(ds_scene_process(&scene[1],outputs[1],4097,&c));}
    CHECK(!memcmp(low[0],low[1],sizeof low[0]));
    puts("chunk1/257 exact; independent LF exact under active phase motion");return 1;
}
int main(void) {return direct_and_bypass()&&low_unchanged()&&scene_chunking()?0:1;}
