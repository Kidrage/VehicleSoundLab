#include "modal_layer/state.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"idle control line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define PI 3.14159265358979323846
static int known(unsigned variant) {
    MsProfile modal={0};RdtProfile detail={0};MlProfile p;MlState s,muted,before;
    RdtVoice r;double amount=.7,position=0,start=0,target=0,follow=1-exp(-1/(.018*48000));
    unsigned duration=0,count=0,n,c,k;int previous=0;
    modal.rate=48000;modal.count=2;
    modal.mode[0]=(MsMode){variant?121.7:153.23,{.2,.12},{.13,.57}};
    modal.mode[1]=(MsMode){variant?733.9:413.75,{.05,.03},{-.5,1.2}};
    detail.rate=48000;detail.count=1;detail.base_hz=63;detail.warmup_frames=32;
    detail.band[0].order=detail.band[0].sections=1;detail.band[0].low_hz=20;detail.band[0].high_hz=20000;
    detail.band[0].sigma=.1;detail.band[0].gain=.02;detail.band[0].right_over_left=.8;
    detail.band[0].a[0]=1;detail.band[0].a[1]=-.3;
    detail.band[0].sos[0][0]=detail.band[0].sos[0][3]=1;
    p=(MlProfile){&modal,&detail,variant?.9:1.1,.6,.4,1.7,997,613};
    CHECK(ml_state_init(&s,&p,39281,amount)&&ml_state_init(&muted,&p,39281,0));
    CHECK(rdt_voice_init(&r,&detail,39281));
    for(n=0;n<detail.warmup_frames;++n){double x[2];CHECK(rdt_voice_tick(&r,0,x,NULL));}
    for(n=0;n<96000;++n) {
        int gate=(n>=500&&n<900)||(n>=1100&&n<1300)||n>=2000;
        double value=n<700?.7:n<2500?0:1,env=n>7000&&n<9000?0:.63,d[2],weight;
        MlFrame f,z;
        if(gate!=previous){start=position;target=(double)gate;duration=gate?p.attack_frames:p.release_frames;count=0;previous=gate;}
        if(count<duration){++count;position=count==duration?target:start+(target-start)*(double)count/duration;}
        amount+=follow*(value-amount);weight=position*position*(3-2*position)*amount;
        CHECK(ml_state_tick(&s,gate,value,env,&f)&&ml_state_tick(&muted,0,0,0,&z));
        CHECK(rdt_voice_tick(&r,0,d,NULL));
        CHECK(fabs(f.weight-weight)<1e-12&&f.weight>=0&&f.weight<=1&&f.keep==1-f.weight);
        for(c=0;c<2;++c) {
            double want=0;
            for(k=0;k<modal.count;++k)want+=modal.mode[k].amplitude[c]*p.modal_gain*
                cos(modal.mode[k].phase[c]+2*PI*modal.mode[k].hz*p.modal_ratio*n/48000);
            CHECK(fabs(f.modal[c]-want)<2e-11&&f.detail[c]==d[c]*p.detail_gain);
            CHECK(f.raw[c]==z.raw[c]&&fabs(f.output[c]-(want+d[c]*p.detail_gain)*(env*weight*p.level_gain))<2e-11);
        }
    }
    CHECK(!memcmp(&s.voice.modal,&muted.voice.modal,sizeof s.voice.modal)&&!memcmp(&s.voice.detail,&muted.voice.detail,sizeof s.voice.detail));
    before=s;
    {MlFrame out={0},saved=out;CHECK(!ml_state_tick(&s,1,NAN,1,&out)&&!memcmp(&s,&before,sizeof s)&&!memcmp(&out,&saved,sizeof out));
     CHECK(!ml_state_tick(&s,2,1,1,&out)&&!memcmp(&s,&before,sizeof s));}
    return 0;
}
int main(void){CHECK(!known(0)&&!known(1));puts("PASS direct modal/Rdt, independent gate and18ms amount oracle, muted advance, invalid-call transaction");return 0;}
