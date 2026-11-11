#include "core/engine.h"
#include "core/character.h"
#include "core/firing_source.h"
#include "drive/fueling.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } }while(0)
static void originals(const VslEngine *a,const VslEngine *b) {
    CHECK(!memcmp(&a->drive,&b->drive,sizeof a->drive),"event source preserves solved drive state");
    CHECK(!memcmp(&a->dna,&b->dna,sizeof a->dna),"legacy DNA state untouched");
    CHECK(!memcmp(&a->character,&b->character,sizeof a->character),"same cylinder events and RNG");
    CHECK(!memcmp(&a->mechanical,&b->mechanical,sizeof a->mechanical),"mechanical excitation untouched");
    CHECK(!memcmp(&a->nvh,&b->nvh,sizeof a->nvh),"air/noise RNG untouched");
}
static void live(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b),*c=malloc(sizeof *c);
    VslParams p=vsl_default_params(0);float x[514],y[514],z[257*12],sa[257*VSL_OBJECTS],sb[257*VSL_OBJECTS];
    unsigned k,i;double diff=0,before;uint64_t events;
    CHECK(a&&b&&c,"allocate native event test");if(!a||!b||!c)goto done;
    p.rpm=8000;p.load=.85;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_init(c,48000,48271);
    vsl_set_params(a,&p);p.firing_source=VSL_SOURCE_VARIABLE;vsl_set_params(b,&p);vsl_set_params(c,&p);
    vsl_process(a,x,1);vsl_process_layout(b,y,1,2,sa);vsl_process_layout(c,z,1,12,sb);
    CHECK(b->firing_source.mix>0&&b->firing_source.mix<.002,"enable follows per sample");
    for(k=0;k<400;++k) {
        if(k==100||k==200) {
            p.firing_source=k==100?VSL_SOURCE_FIXED:VSL_SOURCE_VARIABLE;
            before=b->firing_source.variation;vsl_set_params(b,&p);vsl_set_params(c,&p);
            CHECK(b->firing_source.variation==before,"mode change does not reset old responses");
        }
        if(k==300) { p.pulse_amount=.32;vsl_set_params(b,&p);vsl_set_params(c,&p); }
        vsl_process_layout(a,x,257,2,sa);vsl_process_layout(b,y,257,2,sb);originals(a,b);
        for(i=0;i<257;++i) {
            int s;for(s=VSL_INTAKE;s<VSL_OBJECTS;++s)if(s!=VSL_BODY)
                CHECK(sa[i*VSL_OBJECTS+s]==sb[i*VSL_OBJECTS+s],"other direct source stems exact");
            CHECK(isfinite(y[i*2])&&fabs(y[i*2])<.95,"finite unclipped event output");
            diff+=fabs(x[i*2]-y[i*2]);
        }
        vsl_process_layout(c,z,257,12,sa);
        CHECK(!memcmp(sa,sb,sizeof sa),"all ten source objects same in stereo and 7.1.4");
        CHECK(!memcmp(&b->firing_source,&c->firing_source,sizeof b->firing_source),"event/filter state independent of output layout");
    }
    CHECK(diff>1,"new source changes audible full mix");
    CHECK(!b->firing_source.kernel.overflow,"no independent response stolen at high RPM");
    CHECK(b->firing_source.accepted[0]+b->firing_source.accepted[1]==vsl_character_events(&b->character),"one source strike per permitted cylinder event");
    before=b->firing_source.mix;p.firing_source=VSL_SOURCE_OSC;vsl_set_params(b,&p);vsl_process(b,y,1);
    CHECK(b->firing_source.mix>0&&b->firing_source.mix<before,"live OSC switch retains fade/tails");
    p.pure_osc=1;vsl_set_params(b,&p);vsl_process(b,y,1);
    events=b->firing_source.accepted[0]+b->firing_source.accepted[1];
    for(k=0;k<120;++k)vsl_process(b,y,257);
    CHECK(events==b->firing_source.accepted[0]+b->firing_source.accepted[1],"pure OSC creates no new event strikes");
    CHECK(b->firing_source.mix==0,"bypass settles to exact zero");
    p.firing_source=99;p.pulse_amount=NAN;vsl_set_params(b,&p);
    CHECK(b->target.firing_source==2&&b->target.pulse_amount==0,"canonical runtime bounds");
done:free(a);free(b);free(c);
}
static void bypass(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p;float x[514],y[514];int mode;unsigned k;
    CHECK(a&&b,"bypass allocation");if(!a||!b)goto done;
    for(mode=0;mode<7;++mode) {
        p=vsl_default_params(mode<5?mode:0);p.rpm=4000;p.load=.85;
        if(mode==0)p.pure_osc=1;if(mode==6)p.combustion_variation=0;
        vsl_init(a,48000,48271);vsl_init(b,48000,48271);
        if(mode==5) { a->dna.custom_count=b->dna.custom_count=1;a->dna.custom_root=b->dna.custom_root=66;a->dna.custom_amp[0]=b->dna.custom_amp[0]=1; }
        vsl_set_params(a,&p);p.firing_source=VSL_SOURCE_VARIABLE;vsl_set_params(b,&p);
        for(k=0;k<100;++k) { vsl_process(a,x,257);vsl_process(b,y,257);CHECK(!memcmp(x,y,sizeof x),"other profile/custom/PureOSC/disabled variation exact bypass"); }
        CHECK(b->firing_source.accepted[0]+b->firing_source.accepted[1]==0,"no bypass events accepted");
    }
done:free(a);free(b);
}
static void permission_and_tails(void) {
    const double rates[]={16000,48000,192000};int r;unsigned k;
    VslEngine *e=malloc(sizeof *e);CHECK(e!=NULL,"permission allocation");if(!e)return;
    for(r=0;r<3;++r) {
        double main[2]={0,0};VslObjectFrame o={0};VslParams p=vsl_default_params(0);uint64_t accepted;
        vsl_init(e,rates[r],48271);p.firing_source=2;vsl_set_params(e,&p);
        e->drive.lifecycle=VSL_RUNNING;e->drive.combustion=1;e->drive.fuel.command=1;
        e->smooth.profile=VSL_V10;e->control.rpm=8000;e->excitation.firing=1;e->smooth.dna=.85;e->voice.dna_gain=1;
        e->character.events[0]=1;
        vsl_firing_source_tick(&e->firing_source,e,&o,main);
        accepted=e->firing_source.accepted[0];CHECK(accepted==1,"permitted native event accepted");
        e->drive.fuel.command=0;CHECK(!vsl_fueling_allows_firing(&e->drive),"fuel-cut fixture explicit");
        ++e->character.events[0];vsl_firing_source_tick(&e->firing_source,e,&o,main);
        CHECK(e->firing_source.accepted[0]==accepted&&e->firing_source.denied==1,"cut forbids new excitation");
        for(k=0;k<(unsigned)(rates[r]*.03);++k)vsl_firing_source_tick(&e->firing_source,e,&o,main);
        CHECK(!e->firing_source.kernel.overflow&&isfinite(e->firing_source.last[4]),"tails drain at each supported rate extreme");
        CHECK(e->firing_source.accepted[0]==accepted,"ringdown creates no phantom event");
    }
    free(e);
}
int main(void) { live();bypass();permission_and_tails();if(!failures)puts("Live event source,transitions,permission,source independence and bypass pass.");return failures?1:0; }
