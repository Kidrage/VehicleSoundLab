#define _CRT_SECURE_NO_WARNINGS
#include "session/take.h"
#include "session/parameters.h"
#include "io/take_file.h"
#include "io/take_render.h"
#include "io/file.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } }while(0)
static void record(VslTake *t,VslEngine *e,int profile,int custom) {
    VslParams p=vsl_default_params(profile);unsigned b,n;float out[1024],ir[]={.8f,.1f,-.2f};
    vsl_init(e,48000,48271);p.drive_mode=VSL_PEDALS;p.ignition=0;p.start_id=0;p.propagation=1;
    if(custom) {
        e->dna.custom_count=3;e->dna.custom_root=220.123456789;
        e->dna.custom_amp[0]=.37;e->dna.custom_amp[1]=.091;e->dna.custom_amp[2]=.019;
        e->dna.custom_phase[0]=.123456789012345;e->dna.custom_phase[1]=-.87;
        CHECK(vsl_set_ir(e,ir,3,48000),"custom IR prepared once");
    }
    CHECK(vsl_take_begin(t,e),"fresh take begins");
    for(b=0;b<800;++b) {
        n=b==799?173:512;
        if(b==2) { p.ignition=1;p.start_id=1; }
        if(b==150) { p.throttle=1;p.gear=1;p.pressure_texture=.653456789123456;p.structure_transfer=.617234567891234;p.response_shape=.317234567891234;p.event_color=.571234567891234;p.firing_source=VSL_SOURCE_VARIABLE;p.pulse_amount=.723456789123; }
        if(b==300) { p.gear=2;p.width=.713456789123;p.pumping=.4123456789;p.pressure_texture=.431234567891234;p.structure_transfer=.891234567891234;p.response_shape=.843456789123456;p.event_color=.891234567891234;p.firing_source=VSL_SOURCE_FIXED;p.pulse_amount=.393456789123; }
        if(b==400) { p.throttle=0;p.propagation=0;p.mechanical_model=0;p.response_shape=0;p.event_color=0;p.firing_source=VSL_SOURCE_OSC; }
        if(b==500) { p.brake=.32;p.combustion_variation=0; }
        if(b==600) { p.ignition=0;p.master=.11345; }
        vsl_set_params(e,&p);
        CHECK(vsl_take_record(t,e->frame,&e->target),"record actual target at committed frame");
        vsl_process(e,out,n);vsl_take_commit(t,out,n);
    }
    vsl_take_finish(t);CHECK(t->count==7&&vsl_take_validate(t),"unchanged block inputs coalesced");
}
static void reconstruction(int profile,int custom) {
    VslTake t={0},loaded={0};VslTakePlayer a,b;VslEngine *e=malloc(sizeof *e),*r=malloc(sizeof *r),*m=malloc(sizeof *m);
    float stereo[257*2],bed[257*12],source_a[257*VSL_OBJECTS],source_b[257*VSL_OBJECTS];unsigned n,k=0;
    CHECK(e&&r&&m&&vsl_take_allocate(&t,128),"allocate roundtrip");if(!e||!r||!m||!t.events)goto done;
    record(&t,e,profile,custom);
    CHECK(vsl_take_save("take_roundtrip.vsltake",&t)&&vsl_take_save("take_roundtrip.vsltake",&t),"atomic save and replace");
    CHECK(vsl_take_load("take_roundtrip.vsltake",&loaded),"load portable take");
    CHECK(loaded.frames==t.frames&&loaded.audio_hash==t.audio_hash&&loaded.count==t.count,"metadata exact");
    CHECK(loaded.assets.dna_root==t.assets.dna_root&&!memcmp(loaded.assets.ir,t.assets.ir,sizeof t.assets.ir),"effective assets roundtrip without renormalization");
    CHECK(vsl_take_player_init(&a,r,&loaded)&&vsl_take_player_init(&b,m,&loaded),"two layouts initialize");
    do {
        unsigned chunk=k++%3==0?17:257;
        n=vsl_take_process(&a,r,stereo,chunk,2,source_a);
        CHECK(n==vsl_take_process(&b,m,bed,chunk,12,source_b),"layouts preserve event boundary count");
        CHECK(!memcmp(source_a,source_b,n*VSL_OBJECTS*sizeof(float)),"7.1.4 and stereo share exact pre-spatial sources");
        CHECK(!memcmp(&r->drive,&m->drive,sizeof r->drive),"layout independent full drive state");
        CHECK(!memcmp(&r->character,&m->character,sizeof r->character),"layout independent full character state");
    }while(n);
    CHECK(a.audio_hash==t.audio_hash&&r->frame==t.frames,"arbitrary host chunks reproduce recorded stereo bits");
    CHECK(!memcmp(&e->drive,&r->drive,sizeof e->drive),"complete reconstructed drive state equals recording");
    CHECK(!memcmp(&e->character,&r->character,sizeof e->character),"complete reconstructed character state equals recording");
    CHECK(!memcmp(&e->response,&r->response,sizeof e->response),"complete response shape state reconstructed");
    CHECK(!memcmp(&r->response,&m->response,sizeof r->response),"response state independent of layout");
    CHECK(!memcmp(&e->color,&r->color,sizeof e->color),"complete main-pressure state reconstructed");
    CHECK(!memcmp(&r->color,&m->color,sizeof r->color),"main-pressure state independent of layout");
    CHECK(!memcmp(&e->firing_source,&r->firing_source,sizeof e->firing_source),"complete event source reconstruction");
    CHECK(!memcmp(&r->firing_source,&m->firing_source,sizeof r->firing_source),"event source layout independence");
    CHECK(!vsl_take_begin(&t,e),"cannot begin from an unrecorded warm engine");
    if(custom) { uint64_t h;CHECK(vsl_take_render(&loaded,"take_float.wav",2,NULL,NULL,&h)&&h==loaded.audio_hash,"offline float export verifies stereo hash"); }
done:
    vsl_take_free(&t);vsl_take_free(&loaded);free(e);free(r);free(m);
}
static char *read_text(const char *path) {
    FILE *f=vsl_fopen(path,"rb");long n;char *s;if(!f)return NULL;
    fseek(f,0,SEEK_END);n=ftell(f);rewind(f);s=malloc((size_t)n+1);
    if(s) { fread(s,1,n,f);s[n]=0; }fclose(f);return s;
}
static void reject_variant(VslTake *loaded,const char *source,const char *find,const char *replace,int truncate) {
    const char *at=find?strstr(source,find):NULL;FILE *f=vsl_fopen("take_bad.vsltake","wb");VslTakeEvent *old=loaded->events;uint64_t h=loaded->audio_hash;
    CHECK(f!=NULL&&(!find||at),"malformed fixture constructed");if(!f)return;
    if(at) { fwrite(source,1,(size_t)(at-source),f);fputs(replace,f);fputs(at+strlen(find),f); }
    else fwrite(source,1,truncate?strlen(source)/2:strlen(source),f);
    fclose(f);CHECK(!vsl_take_load("take_bad.vsltake",loaded),"malformed input rejected");
    CHECK(loaded->events==old&&loaded->audio_hash==h,"failed load preserves previous take");
}
static void malformed(void) {
    VslTake t={0};char *s;CHECK(vsl_take_load("take_roundtrip.vsltake",&t),"malformed base loads");s=read_text("take_roundtrip.vsltake");if(!s)goto done;
    reject_variant(&t,s,"dsp " VSL_VERSION,"dsp 99.0.0",0);
    reject_variant(&t,s,"fields 38","fields 36",0);
    reject_variant(&t,s,"VSLTAKE 5","VSLTAKE 4",0);
    reject_variant(&t,s,"sample_rate 48000","sample_rate 192000",0);
    reject_variant(&t,s,"events 7","events 999999999999999999999",0);
    reject_variant(&t,s,"event 1024 ","event 0 ",0);
    reject_variant(&t,s,"event 0 4 0 ","event 0 4 2 ",0);
    reject_variant(&t,s,"event 0 4 0 ","event 0 4 0 nan ",0);
    reject_variant(&t,s,"end","end junk",0);
    reject_variant(&t,s,NULL,NULL,1);
    CHECK(!vsl_take_save("missing_dir/take.vsltake",&t),"save path failure reported");
    t.events[0].params.master=NAN;CHECK(!vsl_take_validate(&t),"nonfinite parameter rejected");t.events[0].params.master=.5;
    t.events[0].params.response_shape=1.1;CHECK(!vsl_take_validate(&t),"response shape range enforced");t.events[0].params.response_shape=0;
    t.events[0].params.event_color=1.1;CHECK(!vsl_take_validate(&t),"main-pressure range enforced");t.events[0].params.event_color=0;
    t.events[0].params.firing_source=3;CHECK(!vsl_take_validate(&t),"invalid event-source enum rejected");t.events[0].params.firing_source=0;
    t.events[0].params.pulse_amount=NAN;CHECK(!vsl_take_validate(&t),"nonfinite pulse mix rejected");t.events[0].params.pulse_amount=1;
    t.events[0].params.propagation=2;CHECK(!vsl_take_validate(&t),"noncanonical bool rejected");
done:
    free(s);vsl_take_free(&t);
}
static void limits(void) {
    VslTake t={0};VslEngine *e=malloc(sizeof *e);VslParams p=vsl_default_params(0);float out[8];
    CHECK(e&&vsl_take_allocate(&t,1),"limited allocation");if(!e||!t.events)goto done;
    vsl_init(e,48000,48271);CHECK(vsl_take_begin(&t,e),"limit take begin");
    CHECK(vsl_take_record(&t,0,&p),"first event");vsl_process(e,out,4);vsl_take_commit(&t,out,4);
    p.width=.4;CHECK(!vsl_take_record(&t,4,&p)&&t.overflow,"capacity exhaustion explicit");vsl_take_finish(&t);
    CHECK(t.count==1&&t.frames==4&&vsl_take_validate(&t),"capacity retains reproducible prefix");
    CHECK(!vsl_take_record(&t,0,&p),"stale input timestamp rejected");
    t.frames=VSL_TAKE_MAX_FRAMES;CHECK(!vsl_take_record(&t,t.frames,&p),"duration bounded before next audio block");
    CHECK(vsl_take_begin(&t,(vsl_init(e,48000,48271),e)),"new fresh limit take");
    CHECK(vsl_take_record(&t,0,&p),"uncommitted event stored");vsl_take_finish(&t);
    CHECK(t.count==0&&!vsl_take_validate(&t),"failed submission removes uncommitted event and empty take invalid");
done:
    vsl_take_free(&t);free(e);
}
int main(void) {
    int i;reconstruction(0,0);for(i=0;i<VSL_PROFILE_COUNT;++i)reconstruction(i,i==0);
    malformed();limits();if(!failures)puts("Take reconstruction, source/layout independence, transactional I/O and bounds passed.");
    return failures?1:0;
}
