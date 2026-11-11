#define _CRT_SECURE_NO_WARNINGS
#include "oscillator.h"
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } }while(0)
static void loader_checks(void) {
    const char *path="reference_osc_test.model";RoModel model={0};RoSegment *saved;FILE *f;
    const char *bad[]={"VSL_REFERENCE_OSC 1 48000 48000 12001\n",
        "VSL_REFERENCE_OSC 1 48000 48000 1\n0 256 1\n0 nan 0 0 0 0 0",
        "VSL_REFERENCE_OSC 1 48000 48000 2\n0 256 0\n128 256 0\n",
        "VSL_REFERENCE_OSC 1 48000 48000 1\n0 256 0\ntrailing\n"};unsigned i;
    f=fopen(path,"wb");CHECK(f!=NULL,"test fixture opens");if(!f)return;
    fputs("VSL_REFERENCE_OSC 1 48000 48000 1\n0 256 1\n0 .1 .2 0 628 0 0 .1 .2 .3 628 0 0\n",f);fclose(f);
    CHECK(ro_model_load(path,&model)&&model.count==1,"valid coefficient model loads");saved=model.segments;
    for(i=0;i<sizeof bad/sizeof bad[0];++i) {
        f=fopen(path,"wb");if(!f){CHECK(0,"bad fixture opens");break;}
        fputs(bad[i],f);fclose(f);
        CHECK(!ro_model_load(path,&model),"malformed model rejects without crash");
        CHECK(model.segments==saved&&model.count==1,"failed load preserves active model");
    }
    ro_model_free(&model);CHECK(!model.segments&&!model.count,"free clears ownership");remove(path);
}
int main(void) {
    RoPartial rows[2]={0};RoSegment segment={0,48000,2,rows};RoModel model={48000,1,48000,&segment};RoPlayer a,b;
    double x[514],y[514],h[514],tolerance=0;unsigned frame=0,n,i;double before;
    rows[0].channel[0]=(RoChannel){.1,.2,.37,2*3.14159265358979323846*223.7,3.14159265358979323846*31,0};
    rows[0].channel[1]=rows[0].channel[0];rows[0].channel[1].phase0+=1.2;
    rows[1].group=1;rows[1].channel[0]=(RoChannel){.03,.01,-.4,2*3.14159265358979323846*5301.8,0,0};
    rows[1].channel[1]=rows[1].channel[0];
    CHECK(ro_player_init(&a,&model,0)&&ro_player_init(&b,&model,0),"known AM/FM stereo model initializes");
    while(frame<48000) {
        n=48000-frame;if(n>257)n=257;
        CHECK(ro_process(&a,x,h,n)==n,"full host block renders");
        for(i=0;i<n;++i) {
            double t=(frame+i)/48000.;double expected=(.1+.1*t)*cos(.37+2*3.14159265358979323846*223.7*t+3.14159265358979323846*31*t*t);
            CHECK(ro_process(&b,y+i*2,NULL,1)==1,"single frame renders");
            tolerance=fmax(tolerance,fabs(x[i*2]-expected));
        }
        CHECK(!memcmp(x,y,n*2*sizeof(double)),"1 vs257 frames gives exact stereo output");frame+=n;
    }
    CHECK(tolerance<1e-12,"independent analytic chirp and AM formula");
    CHECK(!ro_process(&a,x,NULL,1),"bounded model end");
    ro_player_init(&a,&model,0);ro_set_high(&a,1);ro_process(&a,x,NULL,1);before=a.high_amount;
    CHECK(before>0&&before<.002,"high addition smooths");ro_set_high(&a,0);ro_process(&a,x,NULL,1);
    CHECK(a.high_amount>0&&a.high_amount<before,"high release preserves tail");
    CHECK(!ro_set_high(&a,NAN)&&!ro_set_high(&a,-1),"invalid live amounts rejected");
    loader_checks();
    if(!failures)puts("Reference OSC analytic AM/FM, stereo phase, host blocks, smoothing and transactional loader pass.");return failures?1:0;
}
