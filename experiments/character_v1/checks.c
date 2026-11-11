#ifdef NDEBUG
#undef NDEBUG
#endif
#include "character.h"
#include "core/modules.h"
#include "session/take.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void scheduling(void) {
    VslEngine *e=calloc(1,sizeof *e);VslCharacter s;VslObjectFrame o={0};unsigned i,n;
    const double rate=48000,advance=2*VSL_PI*20/rate;double energy;
    assert(e);vsl_init(e,rate,48271);e->control.rpm=2400;e->drive.lifecycle=VSL_RUNNING;
    e->drive.combustion=e->drive.fuel.command=e->excitation.firing=e->fade=1;
    e->voice.dna_gain=.8;e->voice.mechanical_gain=.07;
    vsl_character_init(&s,e,1,1,48271);
    for(i=0;i<48000;++i) { e->control.phase=fmod(e->control.phase+advance,2*VSL_PI);memset(&o,0,sizeof o);vsl_character_step(&s,e,&o); }
    n=vsl_character_events(&s);assert(n>=199&&n<=200);
    for(i=0;i<10;++i)assert(s.events[i]>=19&&s.events[i]<=20);
    assert(s.energy_min>.88&&s.energy_max<1.13);
    e->drive.fuel.command=0;
    for(i=0;i<12000;++i) { e->control.phase=fmod(e->control.phase+advance,2*VSL_PI);memset(&o,0,sizeof o);vsl_character_step(&s,e,&o); }
    assert(vsl_character_events(&s)==n);
    energy=0;for(i=0;i<VSL_CHARACTER_STRUCTURE_MODES;++i)energy+=fabs(s.structure.mode[i].real)+fabs(s.structure.mode[i].imag);
    assert(energy<1e-9);
    e->drive.fuel.command=1;e->drive.lifecycle=VSL_STOPPING;
    for(i=0;i<2400;++i) { e->control.phase=fmod(e->control.phase+advance,2*VSL_PI);vsl_character_step(&s,e,&o); }
    assert(vsl_character_events(&s)==n);
    e->drive.lifecycle=VSL_RUNNING;e->target.pure_osc=1;
    for(i=0;i<2400;++i) { e->control.phase=fmod(e->control.phase+advance,2*VSL_PI);vsl_character_step(&s,e,&o); }
    assert(vsl_character_events(&s)==n);free(e);
}
static void integration(int channels,int amount,unsigned block) {
    VslEngine *base=malloc(sizeof *base),*candidate=malloc(sizeof *candidate);
    VslCharacter s;VslParams p=vsl_default_params(VSL_V10);
    float a[512*12],b[512*12],sa[512*VSL_OBJECTS],sb[512*VSL_OBJECTS];
    unsigned total=192000,pos=0,changed=0;int c;
    assert(base&&candidate);vsl_init(base,48000,48271);vsl_init(candidate,48000,48271);
    p.rpm=6000;p.load=.85;vsl_set_params(base,&p);vsl_set_params(candidate,&p);
    vsl_character_init(&s,candidate,amount,amount,48271);
    while(pos<total) {
        unsigned n=total-pos,i;if(n>block)n=block;
        vsl_character_bind(NULL);assert(vsl_process_layout(base,a,n,channels,sa));
        vsl_character_bind(&s);assert(vsl_process_layout(candidate,b,n,channels,sb));
        assert(!memcmp(&base->drive,&candidate->drive,sizeof base->drive));
        assert(!memcmp(&base->combustion,&candidate->combustion,sizeof base->combustion));
        assert(!memcmp(&base->mechanical,&candidate->mechanical,sizeof base->mechanical));
        if(!amount)assert(!memcmp(a,b,n*channels*sizeof(float)));
        for(i=0;i<n;++i)for(c=0;c<VSL_OBJECTS;++c) {
            float x=sa[i*VSL_OBJECTS+c],y=sb[i*VSL_OBJECTS+c];assert(isfinite(y));
            if(c!=VSL_EXHAUST_L&&c!=VSL_EXHAUST_R&&c!=VSL_BODY&&c!=VSL_MECHANICAL)assert(x==y);
            if(x!=y)++changed;
        }
        pos+=n;
    }
    if(amount)assert(changed>10000&&vsl_character_events(&s)>300);
    else assert(!changed);
    vsl_character_bind(NULL);free(base);free(candidate);
}
static void layout_and_seed(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslCharacter sa,sb;
    VslParams p=vsl_default_params(VSL_V10);float aa[257*2],bb[257*12],oa[257*10],ob[257*10];unsigned i;
    assert(a&&b);vsl_init(a,48000,48271);vsl_init(b,48000,48271);p.rpm=8000;p.load=.85;
    vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_character_init(&sa,a,.6,.6,48271);vsl_character_init(&sb,b,.6,.6,48271);
    for(i=0;i<750;++i) {
        vsl_character_bind(&sa);assert(vsl_process_layout(a,aa,257,2,oa));
        vsl_character_bind(&sb);assert(vsl_process_layout(b,bb,257,12,ob));
        assert(!memcmp(oa,ob,sizeof oa));assert(!memcmp(&a->drive,&b->drive,sizeof a->drive));
        assert(!memcmp(sa.events,sb.events,sizeof sa.events));assert(!memcmp(sa.seed,sb.seed,sizeof sa.seed));
    }
    vsl_character_bind(NULL);free(a);free(b);
}
static void bypasses(void) {
    int profile,mode;
    for(profile=0;profile<5;++profile)for(mode=0;mode<2;++mode) {
        VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslCharacter s;
        VslParams p=vsl_default_params(profile);float aa[512*2],bb[512*2];unsigned i;
        assert(a&&b);vsl_init(a,48000,48271);vsl_init(b,48000,48271);p.rpm=4000;p.load=.85;
        if(profile==0&&mode==0)p.pure_osc=1;
        vsl_set_params(a,&p);vsl_set_params(b,&p);
        if(profile==0&&mode==1) {
            a->dna.custom_count=b->dna.custom_count=1;a->dna.custom_root=b->dna.custom_root=220;
            a->dna.custom_amp[0]=b->dna.custom_amp[0]=1;
        }
        vsl_character_init(&s,b,1,1,48271);
        for(i=0;i<300;++i) {
            vsl_character_bind(NULL);vsl_process(a,aa,512);vsl_character_bind(&s);vsl_process(b,bb,512);
            assert(!memcmp(aa,bb,sizeof aa));
        }
        assert(!vsl_character_events(&s));vsl_character_bind(NULL);free(a);free(b);
    }
}
int main(void) {
    scheduling();integration(2,0,512);integration(2,1,257);integration(12,1,512);
    layout_and_seed();bypasses();puts("character_v1 source, driving, fuel, bypass and layout contracts pass");return 0;
}
