#ifdef NDEBUG
#undef NDEBUG
#endif
#include "core/engine.h"
#include "core/character.h"
#include "core/modules.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void step(VslEngine *e) {
    VslObjectFrame o={0};vsl_clocks_tick(e);vsl_character_tick(e,&o);
    assert(isfinite(o.sample[0])&&isfinite(o.sample[1])&&isfinite(o.sample[VSL_MECHANICAL]));
}
static void scheduling(void) {
    double rates[]={16000,48000,192000};unsigned r,i,n;VslEngine *e=malloc(sizeof *e);assert(e);
    for(r=0;r<3;++r) {
        double energy=0;
        vsl_init(e,rates[r],48271);e->control.rpm=2400;e->drive.lifecycle=VSL_RUNNING;
        e->drive.combustion=e->drive.fuel.command=e->excitation.firing=e->fade=1;
        e->voice.dna_gain=.8;e->voice.mechanical_gain=.07;
        e->combustion.mix=e->mechanical.mix=1;e->smooth.pressure_texture=e->smooth.structure_transfer=1;
        for(i=0;i<(unsigned)rates[r];++i)step(e);
        n=vsl_character_events(&e->character);assert(n>=199&&n<=200);
        for(i=0;i<10;++i)assert(e->character.events[i]>=19&&e->character.events[i]<=20);
        assert(e->character.energy_min>.88&&e->character.energy_max<1.13);
        e->drive.fuel.command=0;
        /* A stored response survives cut, while the next firing is suppressed. */
        step(e);assert(vsl_character_events(&e->character)==n);
        for(i=0;i<VSL_CHARACTER_STRUCTURE_MODES;++i)energy+=fabs(e->character.structure.mode[i].real)+fabs(e->character.structure.mode[i].imag);
        assert(energy>1e-8);
        e->control.rpm=0;for(i=0;i<(unsigned)(rates[r]*.5);++i)step(e);
        energy=0;for(i=0;i<VSL_CHARACTER_STRUCTURE_MODES;++i)energy+=fabs(e->character.structure.mode[i].real)+fabs(e->character.structure.mode[i].imag);
        assert(energy<1e-12&&vsl_character_events(&e->character)==n);
        e->control.rpm=2400;e->drive.fuel.command=1;e->drive.lifecycle=VSL_STOPPING;
        for(i=0;i<(unsigned)(rates[r]*.1);++i)step(e);assert(vsl_character_events(&e->character)==n);
        e->drive.lifecycle=VSL_RUNNING;e->target.pure_osc=1;
        for(i=0;i<(unsigned)(rates[r]*.1);++i)step(e);assert(vsl_character_events(&e->character)==n);
        e->target.pure_osc=0;e->smooth.profile=VSL_V8;step(e);
        assert(e->character.added[0]==0&&e->character.added[1]==0&&e->character.added[2]==0);
        e->smooth.profile=VSL_V10;step(e);
        assert(vsl_character_events(&e->character)==n); /* no phantom transition firing */
        for(i=0;i<(unsigned)(rates[r]*.1);++i)step(e);assert(vsl_character_events(&e->character)>n);
    }
    free(e);
}
static void integration(int channels) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p=vsl_default_params(VSL_V10);
    float aa[257*12],bb[257*12],sa[257*VSL_OBJECTS],sb[257*VSL_OBJECTS];unsigned k,changed=0,i;int c;
    assert(a&&b);vsl_init(a,48000,48271);vsl_init(b,48000,48271);p.rpm=6000;p.load=.85;
    vsl_set_params(a,&p);p.pressure_texture=.65;p.structure_transfer=.65;vsl_set_params(b,&p);
    vsl_process_layout(a,aa,1,channels,NULL);vsl_process_layout(b,bb,1,channels,NULL);
    assert(b->smooth.pressure_texture>0&&b->smooth.pressure_texture<.001);
    for(k=0;k<750;++k) {
        assert(vsl_process_layout(a,aa,257,channels,sa)&&vsl_process_layout(b,bb,257,channels,sb));
        assert(!memcmp(&a->drive,&b->drive,sizeof a->drive));
        assert(!memcmp(&a->combustion,&b->combustion,sizeof a->combustion));
        assert(!memcmp(&a->mechanical,&b->mechanical,sizeof a->mechanical));
        assert(a->nvh.seed==b->nvh.seed&&a->events.seed==b->events.seed);
        for(i=0;i<257;++i)for(c=0;c<VSL_OBJECTS;++c) {
            float x=sa[i*VSL_OBJECTS+c],y=sb[i*VSL_OBJECTS+c];assert(isfinite(y));
            if(c!=VSL_EXHAUST_L&&c!=VSL_EXHAUST_R&&c!=VSL_BODY&&c!=VSL_MECHANICAL)assert(x==y);
            if(x!=y)++changed;
        }
    }
    assert(changed>10000&&vsl_character_events(&b->character)>300);
    /* Hot control changes affect only the mix; seeded event evolution is independent. */
    assert(!memcmp(a->character.events,b->character.events,sizeof a->character.events));
    assert(!memcmp(a->character.seed,b->character.seed,sizeof a->character.seed));
    p.pressure_texture=0;p.structure_transfer=0;vsl_set_params(b,&p);vsl_process(b,bb,1);
    assert(b->smooth.pressure_texture>.64&&b->smooth.pressure_texture<.65);
    free(a);free(b);
}
static void layouts(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p=vsl_default_params(0);unsigned i;
    float aa[257*2],bb[257*12],sa[257*VSL_OBJECTS],sb[257*VSL_OBJECTS];assert(a&&b);
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);p.rpm=8000;p.pressure_texture=.6;p.structure_transfer=.8;
    vsl_set_params(a,&p);vsl_set_params(b,&p);
    for(i=0;i<750;++i) {
        vsl_process_layout(a,aa,257,2,sa);vsl_process_layout(b,bb,257,12,sb);
        assert(!memcmp(sa,sb,sizeof sa)&&!memcmp(&a->character,&b->character,sizeof a->character));
    }
    free(a);free(b);
}
static void bypasses(void) {
    int profile,mode;unsigned i;
    for(profile=0;profile<5;++profile)for(mode=0;mode<2;++mode) {
        VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p=vsl_default_params(profile);
        float aa[512*2],bb[512*2];assert(a&&b);vsl_init(a,48000,48271);vsl_init(b,48000,48271);p.rpm=4000;
        if(profile==0&&mode==0)p.pure_osc=1;
        if(profile==0&&mode==1) {
            a->dna.custom_count=b->dna.custom_count=1;a->dna.custom_root=b->dna.custom_root=220;
            a->dna.custom_amp[0]=b->dna.custom_amp[0]=1;
        }
        vsl_set_params(a,&p);p.pressure_texture=p.structure_transfer=1;vsl_set_params(b,&p);
        for(i=0;i<180;++i) { vsl_process(a,aa,512);vsl_process(b,bb,512);assert(!memcmp(aa,bb,sizeof aa)); }
        assert(!vsl_character_events(&b->character));free(a);free(b);
    }
}
int main(void) {
    scheduling();integration(2);integration(12);layouts();bypasses();
    puts("PASS: per-cylinder scheduling, cut/ringdown, independent instances/RNG, smoothed controls and layout/bypass policies");return 0;
}
