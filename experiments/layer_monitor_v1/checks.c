#include "layer_monitor/listen.h"
#include "layer_monitor/split.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"layer check%d: %s\n",__LINE__,#x);return 1;}}while(0)
int main(void) {
    LmSources s={0};float buses[LM_SAMPLES],pcm[2];LmListen a,b,before;int k;unsigned n;
    const double expected[]={.25,1.25,2.25,1.5,6.25,2.25};
    s.gain=.25;s.dna[0]=1;s.body[0]=2;s.coherent[0]=3;s.residual[0]=4;s.resonant[0]=5;
    s.aux[0]=6;s.starter[0]=7;s.catch_delta[0]=8;s.added[0]=9;s.event=10;
    lm_split(&s,buses);
    for(k=0;k<LM_LAYERS;++k)CHECK(buses[2*k]==expected[k]);
    s.fine_idle=1;s.idle_scale=.5;s.idle_modal[0]=2;s.idle_detail[0]=4;lm_split(&s,buses);
    CHECK(buses[2*LM_DNA]==.5&&buses[2*LM_DETAIL]==2.75&&buses[2*LM_OTHER]==0);
    for(k=0;k<LM_LAYERS;++k){buses[2*k]=(float)(-.6+.1*k);buses[2*k+1]=(float)(.4-.05*k);}
    CHECK(lm_listen_init(&a,0));before=a;
    CHECK(!lm_listen_set(&a,-1)&&!lm_listen_set(&a,LM_SELECTIONS)&&!memcmp(&a,&before,sizeof a));
    CHECK(!lm_listen_process(&a,NULL,buses,1)&&!lm_listen_process(&a,pcm,NULL,1));
    for(k=0;k<LM_SELECTIONS;++k) {
        double previous=.2;CHECK(lm_listen_init(&a,0)&&lm_listen_set(&a,k));
        for(n=0;n<LM_RAMP_FRAMES+3;++n) {
            double sum=0;pcm[0]=pcm[1]=.2f;CHECK(lm_listen_process(&a,pcm,buses,1));
            for(int j=0;j<LM_SELECTIONS;++j)sum+=a.weight[j];CHECK(fabs(sum-1)<1e-12);
            CHECK(fabs(pcm[0]-previous)<.0011);previous=pcm[0];
            if(n>=LM_RAMP_FRAMES-1)CHECK(pcm[0]==(k?buses[2*(k-1)]:.2f)&&pcm[1]==(k?buses[2*(k-1)+1]:.2f));
        }
    }
    CHECK(lm_listen_init(&a,0));pcm[0]=-0.f;pcm[1]=.1234567f;
    {float saved[2];memcpy(saved,pcm,sizeof pcm);CHECK(lm_listen_process(&a,pcm,buses,1)&&!memcmp(pcm,saved,sizeof pcm));}
    CHECK(lm_listen_init(&a,0)&&lm_listen_init(&b,0));
    for(n=0;n<3000;++n) {
        float x[2]={.15f,-.25f},y[2]={.15f,-.25f};
        if(n%117==0)CHECK(lm_listen_set(&a,(n/117)%LM_SELECTIONS)&&lm_listen_set(&b,(n/117)%LM_SELECTIONS));
        CHECK(lm_listen_process(&a,x,buses,1)&&lm_listen_process(&b,y,buses,1)&&!memcmp(x,y,sizeof x));
        for(k=0;k<LM_SELECTIONS;++k)CHECK(a.weight[k]>=-1e-12&&a.weight[k]<=1+1e-12);
    }
    puts("PASS split known values, fine-idle gate accounting, all7 selections, interrupted crossfades, exact full bypass and invalid selection transaction");return 0;
}
