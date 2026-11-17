#include "crank_rotation/voice.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define PI 3.14159265358979323846
#define CHECK(x) do{if(!(x)){fprintf(stderr,"rotation check line %d\n",__LINE__);return 1;}}while(0)
int main(void){
    CkVoice *v=calloc(1,sizeof *v),*copy=malloc(sizeof *v);CkProfile p={0};double x[2],air,max=0,phase;unsigned n,c;
    CHECK(v&&copy);p.count=p.bands=1;p.flutter_hz=11;p.coherence=1;p.mode[0].hz=1373;p.mode[0].width_hz=8;
    for(n=0;n<3;++n)for(c=0;c<2;++c)p.mode[0].amplitude[n][c]=.2;
    p.mode[0].phase[1]=.7;CHECK(ck_init(v,&p,11243));phase=v->initial_phase[0];
    p.mode[0].hz=999;CHECK(v->profile.mode[0].hz==1373);p.mode[0].hz=1373;
    /* Independent analytic carrier oracle, including the original L/R offset;
       no fixed-frequency-only test: vary pitch continuously every sample. */
    for(n=0;n<96000;++n){double pitch=.8+.4*(double)n/96000;
        CHECK(ck_tick(v,.5,1,pitch,0,x,&air));
        for(c=0;c<2;++c){double expected=.2*cos(2*PI*phase+p.mode[0].phase[c]),e=fabs(x[c]-expected);if(e>max)max=e;}
        phase+=p.mode[0].hz*pitch/48000;phase-=floor(phase);CHECK(air==1);
    }CHECK(max<2e-8);
    *copy=*v;x[0]=123;x[1]=456;CHECK(!ck_tick(v,NAN,1,1,1,x,NULL));CHECK(!memcmp(v,copy,sizeof *v));CHECK(x[0]==123&&x[1]==456);
    p.mode[0].width_hz=NAN;CHECK(!ck_init(copy,&p,11243));CHECK(!memcmp(v,copy,sizeof *v));
    printf("Continuous variable-pitch analytic error %.9g; invalid controls transactional; owned model PASS\n",max);
    free(copy);free(v);return 0;
}
