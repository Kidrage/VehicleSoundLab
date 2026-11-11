#include "core/engine.h"
#include "core/character.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void original_state(const VslEngine *a,const VslEngine *b) {
    CHECK(!memcmp(&a->drive,&b->drive,sizeof a->drive),"complete original drive state");
    CHECK(!memcmp(&a->dna,&b->dna,sizeof a->dna),"complete original DNA state");
    CHECK(!memcmp(&a->high_orders,&b->high_orders,sizeof a->high_orders),"original upper oscillators");
    CHECK(!memcmp(&a->character,&b->character,sizeof a->character),"original cylinder events and RNG");
    CHECK(!memcmp(&a->response,&b->response,sizeof a->response),"existing added response state");
    CHECK(!memcmp(&a->nvh,&b->nvh,sizeof a->nvh),"original airflow RNG");
}
static void live(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p=vsl_default_params(0);
    float x[514],y[514];unsigned block,i;double difference=0,before;uint64_t events;
    CHECK(a&&b,"live allocations");if(!a||!b)goto done;
    p.rpm=8000;p.load=.85;p.pressure_texture=p.structure_transfer=.65;p.response_shape=.75;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);
    vsl_set_params(a,&p);p.event_color=1;vsl_set_params(b,&p);
    vsl_process(a,x,1);vsl_process(b,y,1);
    CHECK(b->smooth.event_color>0&&b->smooth.event_color<.002,"main shape smooths per sample");
    for(block=0;block<400;++block) {
        vsl_process(a,x,257);vsl_process(b,y,257);original_state(a,b);
        for(i=0;i<514;++i) { CHECK(isfinite(y[i])&&fabs(y[i])<.95,"finite unclipped live output");difference+=fabs(x[i]-y[i]); }
    }
    CHECK(difference>1,"main shape changes full mixture");
    CHECK(b->color.events[0]+b->color.events[1]==vsl_character_events(&b->character),"same permitted native events");
    before=b->smooth.event_color;p.event_color=0;vsl_set_params(b,&p);vsl_process(b,y,1);
    CHECK(b->smooth.event_color<before&&b->smooth.event_color>0,"main shape release smooths");
    p.ignition=0;vsl_set_params(b,&p);vsl_process(b,y,257);events=b->color.events[0]+b->color.events[1];
    for(block=0;block<200;++block)vsl_process(b,y,257);
    CHECK(events==b->color.events[0]+b->color.events[1],"shutdown forbids new main-color events");
    p.event_color=NAN;vsl_set_params(b,&p);CHECK(b->target.event_color==0,"nonfinite main shape clamps");
    p.event_color=1.2;vsl_set_params(b,&p);CHECK(b->target.event_color==1,"main shape unit bound");
done:free(a);free(b);
}
static void layouts(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b),*c=malloc(sizeof *c);VslParams p=vsl_default_params(0);
    float x[514],y[514],bed[257*12],sa[257*VSL_OBJECTS],sb[257*VSL_OBJECTS];unsigned block,i;
    CHECK(a&&b&&c,"layout allocations");if(!a||!b||!c)goto done;
    p.rpm=4000;p.load=.85;p.pressure_texture=p.structure_transfer=.65;p.response_shape=.75;p.event_color=.73123456789;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_init(c,48000,48271);
    vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_set_params(c,&p);
    for(block=0;block<400;++block) {
        if(block==150) { p.event_color=.213456789;p.load=-.4;vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_set_params(c,&p); }
        if(block==300) { p.event_color=.89123456;p.load=.85;vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_set_params(c,&p); }
        for(i=0;i<257;++i)vsl_process(a,x+i*2,1);
        vsl_process_layout(b,y,257,2,sa);vsl_process_layout(c,bed,257,12,sb);
        CHECK(!memcmp(x,y,sizeof x)&&!memcmp(a,b,sizeof *a),"dynamic parameter1 vs257 blocks exact audio/full state");
        CHECK(!memcmp(sa,sb,sizeof sa),"all ten dynamic source stems layout independent");
        CHECK(!memcmp(&b->color,&c->color,sizeof b->color),"complete main-pressure state layout independent");
    }
done:free(a);free(b);free(c);
}
static void bypass(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p;float x[514],y[514];int mode;unsigned block;
    CHECK(a&&b,"bypass allocations");if(!a||!b)goto done;
    for(mode=0;mode<7;++mode) {
        p=vsl_default_params(mode<5?mode:0);p.rpm=4000;p.load=.85;
        if(mode==0)p.pure_osc=1;if(mode==6)p.combustion_variation=0;
        vsl_init(a,48000,48271);vsl_init(b,48000,48271);
        if(mode==5) { a->dna.custom_count=b->dna.custom_count=1;a->dna.custom_root=b->dna.custom_root=66;a->dna.custom_amp[0]=b->dna.custom_amp[0]=1; }
        vsl_set_params(a,&p);p.event_color=1;vsl_set_params(b,&p);
        for(block=0;block<100;++block) {
            vsl_process(a,x,257);vsl_process(b,y,257);
            CHECK(!memcmp(x,y,sizeof x),"other templates/custom/PureOSC/pressure switch exact bypass");
        }
        CHECK(b->color.events[0]+b->color.events[1]==0,"no accepted main-color events on bypass");
    }
done:free(a);free(b);
}
int main(void) {
    live();layouts();bypass();if(!failures)puts("Native main-pressure shape,smoothing,original state,permission,blocks and layouts pass.");return failures?1:0;
}
