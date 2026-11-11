#include "color.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL %s\n",m);++failures; } } while(0)
static void original(const VslEngine *a,const VslEngine *b) {
    CHECK(!memcmp(&a->drive,&b->drive,sizeof a->drive),"complete original driving state");
    CHECK(!memcmp(&a->dna,&b->dna,sizeof a->dna),"complete original DNA state");
    CHECK(!memcmp(&a->high_orders,&b->high_orders,sizeof a->high_orders),"original upper oscillators");
    CHECK(!memcmp(&a->character,&b->character,sizeof a->character),"original cylinder events and RNG");
    CHECK(!memcmp(&a->response,&b->response,sizeof a->response),"native response state");
    CHECK(!memcmp(&a->nvh,&b->nvh,sizeof a->nvh),"original airflow RNG");
}
static void integrated(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b),*c=malloc(sizeof *c),*d=malloc(sizeof *d);
    VslParams p=vsl_default_params(0);VslEventColor off,on,bed,single;
    float x[514],y[514],z[257*12],w[514],sa[257*VSL_OBJECTS],sb[257*VSL_OBJECTS];
    unsigned block,i;uint64_t events;double difference=0;
    CHECK(a&&b&&c&&d,"allocations");if(!a||!b||!c||!d)goto done;
    p.rpm=8000;p.load=.85;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_init(c,48000,48271);vsl_init(d,48000,48271);
    vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_set_params(c,&p);vsl_set_params(d,&p);
    CHECK(vsl_color_init(&off,48000,0)&&vsl_color_init(&on,48000,1)&&
          vsl_color_init(&bed,48000,1)&&vsl_color_init(&single,48000,1),"valid init");
    for(block=0;block<400;++block) {
        VslEngine *base=malloc(sizeof *base);float native[514];
        CHECK(base!=NULL,"baseline allocation");if(!base)break;memcpy(base,a,sizeof *base);
        vsl_process(base,native,257);vsl_color_process(a,&off,x,257,2,NULL);
        CHECK(!memcmp(native,x,sizeof x),"off output bit identical to native");free(base);
        vsl_color_process(b,&on,y,257,2,sa);vsl_color_process(c,&bed,z,257,12,sb);
        for(i=0;i<257;++i)vsl_color_process(d,&single,w+i*2,1,2,NULL);
        CHECK(!memcmp(y,w,sizeof y)&&!memcmp(b,d,sizeof *b),"block1 versus257 exact audio/full state");
        CHECK(!memcmp(sa,sb,sizeof sa),"all ten source stems layout independent");
        CHECK(!memcmp(&on,&bed,sizeof on)&&!memcmp(&on,&single,sizeof on),"color state independent of layout/block");
        original(a,b);
        for(i=0;i<514;++i) { CHECK(isfinite(y[i])&&fabs(y[i])<.95,"finite unclipped output");difference+=fabs(x[i]-y[i]); }
    }
    CHECK(difference>1,"main mix is changed");
    CHECK(on.events[0]>100&&on.events[1]>100,"both physical banks observed");
    CHECK(on.events[0]+on.events[1]==off.events[0]+off.events[1],"strength cannot create events");
    p.ignition=0;vsl_set_params(b,&p);vsl_color_process(b,&on,y,257,2,NULL);events=on.events[0]+on.events[1];
    for(block=0;block<200;++block)vsl_color_process(b,&on,y,257,2,NULL);
    CHECK(events==on.events[0]+on.events[1],"no new coloring events on shutdown");
    CHECK(on.denied_events==0,"no original denied fired events observed");
done:free(a);free(b);free(c);free(d);
}
static void bypass(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p;VslEventColor color;
    float x[514],y[514];int mode;unsigned block;
    CHECK(a&&b,"bypass allocations");if(!a||!b)goto done;
    for(mode=0;mode<7;++mode) {
        p=vsl_default_params(mode<5?mode:0);p.rpm=4000;p.load=.85;
        if(mode==0)p.pure_osc=1;if(mode==6)p.combustion_variation=0;
        vsl_init(a,48000,48271);vsl_init(b,48000,48271);
        if(mode==5) { a->dna.custom_count=b->dna.custom_count=1;a->dna.custom_root=b->dna.custom_root=66;a->dna.custom_amp[0]=b->dna.custom_amp[0]=1; }
        vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_color_init(&color,48000,1);
        for(block=0;block<100;++block) {
            vsl_process(a,x,257);vsl_color_process(b,&color,y,257,2,NULL);
            CHECK(!memcmp(x,y,sizeof x),"other templates/custom/PureOSC/pressure switch exact bypass");
        }
        CHECK(color.events[0]+color.events[1]==0,"no accepted events on bypass");
    }
done:free(a);free(b);
}
static void filters(void) {
    const double rates[]={16000,48000,192000};unsigned r,k,n;VslEventColor s;
    CHECK(!vsl_color_init(&s,48000,NAN)&&!vsl_color_init(&s,8000,1)&&!vsl_color_init(&s,48000,1.1),"invalid configuration rejection");
    for(r=0;r<3;++r)for(k=0;k<2;++k) {
        VslColorLowpass f;double sum=0,last=0;
        vsl_color_lowpass_init(&f,rates[r],k?4500:1400);
        for(n=0;n<(unsigned)rates[r];++n) { last=vsl_color_lowpass_tick(&f,n==0?1:0);sum+=last;CHECK(isfinite(last),"finite impulse"); }
        CHECK(fabs(sum-1)<1e-10&&fabs(last)<1e-20,"independent DC gain and decay contract");
    }
}
int main(void) {
    filters();integrated();bypass();if(!failures)puts("Event coloration bypass,original state,permission,blocks,layouts and filters pass.");return failures?1:0;
}
