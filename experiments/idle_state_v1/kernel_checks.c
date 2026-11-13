#include "modal_layer/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"modal layer line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define PI 3.14159265358979323846
static int known(unsigned variant) {
    MsProfile modal={0};RdtProfile detail={0};MlProfile p;MlVoice v,muted,before;RdtVoice r;
    double maximum=0,start=0,target=0;unsigned count=0,duration=0,n,c,k;int old_gate=0;
    modal.rate=48000;modal.count=2;
    modal.mode[0]=(MsMode){variant?117.3:137.19,{.2,.14},{.12,-.41}};
    modal.mode[1]=(MsMode){variant?950.7:403.31,{.08,.06},{1.1,.73}};
    detail.rate=48000;detail.count=1;detail.base_hz=75;detail.warmup_frames=64;
    detail.band[0].order=detail.band[0].sections=1;
    detail.band[0].low_hz=20;detail.band[0].high_hz=20000;
    detail.band[0].sigma=.1;detail.band[0].gain=.02;detail.band[0].right_over_left=.7;
    detail.band[0].a[0]=1;detail.band[0].a[1]=variant?-.2:-.4;
    detail.band[0].sos[0][0]=detail.band[0].sos[0][3]=1;
    p=(MlProfile){&modal,&detail,variant?.9:1.,.7,.8,variant?.4:1.7,1024,768};
    CHECK(ml_voice_init(&v,&p,812901)&&ml_voice_init(&muted,&p,812901));
    CHECK(rdt_voice_init(&r,&detail,812901));
    for(n=0;n<detail.warmup_frames;++n){double x[2];CHECK(rdt_voice_tick(&r,0,x,NULL));}
    for(n=0;n<96000;++n) {
        int gate=(n>=500&&n<1800)||(n>=2100&&n<3500)||n>=4200;
        MlFrame f,z;double d[2],position,weight;
        if(gate!=old_gate){start=v.position;target=(double)gate;duration=gate?p.attack_frames:p.release_frames;count=0;old_gate=gate;}
        if(count<duration)++count;
        position=duration?start+(target-start)*(double)count/duration:0;
        weight=position*position*(3-2*position);
        CHECK(ml_voice_tick(&v,gate,.63,&f)&&ml_voice_tick(&muted,0,0,&z));
        CHECK(rdt_voice_tick(&r,0,d,NULL));
        CHECK(fabs(f.weight-weight)<1e-12&&f.weight>=0&&f.weight<=1&&f.keep==1-f.weight);
        if(count==duration)CHECK(v.position==target);
        for(c=0;c<2;++c) {
            double want=0,error;
            for(k=0;k<modal.count;++k)want+=p.modal_gain*modal.mode[k].amplitude[c]*
                cos(2*PI*modal.mode[k].hz*p.modal_ratio*n/48000+modal.mode[k].phase[c]);
            error=fabs(want-f.modal[c]);if(error>maximum)maximum=error;
            CHECK(error<1e-9&&f.detail[c]==p.detail_gain*d[c]);
            CHECK(f.raw[c]==f.modal[c]+f.detail[c]&&f.output[c]==f.raw[c]*(.63*f.weight*p.level_gain));
            CHECK(z.output[c]==0&&z.weight==0&&z.raw[c]==f.raw[c]);
            CHECK(fabs(2.3*f.keep+2.3*f.weight-2.3)<1e-14);
        }
        CHECK(v.modal.frame==n+1&&v.detail.frame==detail.warmup_frames+n+1);
        CHECK(!memcmp(&v.modal,&muted.modal,sizeof v.modal)&&!memcmp(&v.detail,&muted.detail,sizeof v.detail));
    }
    before=v;{MlFrame out;memset(&out,0x55,sizeof out);MlFrame original=out;
        CHECK(!ml_voice_tick(&v,2,1,&out)&&!ml_voice_tick(&v,1,NAN,&out)&&!ml_voice_tick(&v,0,9,&out));
        CHECK(!memcmp(&v,&before,sizeof v)&&!memcmp(&out,&original,sizeof out));}
    detail.band[0].envelope_order=1;CHECK(rdt_profile_valid(&detail)&&!ml_profile_valid(&p));
    CHECK(!ml_voice_init(&v,&p,1)&&!memcmp(&v,&before,sizeof v));
    printf("PASS modal_layer known%u: raw cosine max %.17g; finite/reversed/repeated gate, zero advance and flat-envelope contract\n",variant,maximum);
    return 0;
}
int main(void){CHECK(!known(0));CHECK(!known(1));return 0;}
