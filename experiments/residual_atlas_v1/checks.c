#include "residual_atlas/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"residual atlas line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static RaBank bank,saved;
static RaVoice a,b,prior;
int main(void) {
    SrProfile low={48000,1,32,{{1200,8000,{.003,.003},{1,0}}}},high=low,invalid;
    const SrProfile *p[2]={&low,&high};double roots[2]={20,80},x[2],y[2],raw[2],other[2],power=0;
    unsigned n;
    CHECK(ra_bank_init(&bank,p,roots,2));saved=bank;
    roots[1]=20;CHECK(!ra_bank_init(&bank,p,roots,2)&&!memcmp(&bank,&saved,sizeof bank));roots[1]=80;
    invalid=high;invalid.band[0].high=7000;p[1]=&invalid;
    CHECK(!ra_bank_init(&bank,p,roots,2)&&!memcmp(&bank,&saved,sizeof bank));p[1]=&high;
    CHECK(ra_voice_init(&a,&bank,101,20,1)&&ra_voice_init(&b,&bank,101,50,0));
    for(n=0;n<48000;++n) {
        if(n%100==0)CHECK(ra_voice_set(&b,n<24000?90:5,0));
        ra_voice_tick(&a,x,raw);ra_voice_tick(&b,y,other);
        /* Identical spectral anchors: moving root does not reset, retune or
           crossfade oscillators. Muting does not stop their hidden state. */
        CHECK(!memcmp(raw,other,sizeof raw)&&x[0]==x[1]&&y[0]==0&&y[1]==0);
        power+=raw[0]*raw[0];
    }
    CHECK(fabs(power/48000-.003)<.0003&&a.frame==b.frame&&b.coverage==-1);
    prior=b;CHECK(!ra_voice_set(&b,NAN,1)&&!memcmp(&b,&prior,sizeof b));
    CHECK(ra_voice_set(&b,20,1));
    for(n=0;n<48000;++n) {ra_voice_tick(&a,x,NULL);ra_voice_tick(&b,y,NULL);}
    CHECK(fabs(x[0]-y[0])<1e-12);
    high.band[0].power[0]=.001;high.band[0].power[1]=.009;
    high.band[0].coherence[0]=-.7;high.band[0].coherence[1]=.4;
    CHECK(ra_bank_init(&bank,p,roots,2)&&ra_voice_init(&a,&bank,202,50,1));
    for(n=0;n<48000;++n) {
        double *m=a.covariance[0];ra_voice_tick(&a,x,NULL);
        CHECK(isfinite(x[0])&&isfinite(x[1])&&m[0]*m[1]+1e-15>=m[2]*m[2]+m[3]*m[3]);
    }
    CHECK(a.lower==0&&a.upper==1&&fabs(a.blend-.5)<1e-12);
    puts("PASS: residual atlas covariance, continuous cloud, mono, mute clock and transactional rejection");return 0;
}
