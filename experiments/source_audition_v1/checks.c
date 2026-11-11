#ifdef NDEBUG
#undef NDEBUG
#endif
#include "audition.h"
#include "spatial/scene.h"
#include <assert.h>
#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
static void integration(int profile,int channels) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslSourceAudition *observer=malloc(sizeof *observer);
    VslParams p=vsl_default_params(profile);
    float aa[257*12],bb[257*12],sa[257*10],sb[257*10],views[257*VSL_AUDITION_MODES*12];
    unsigned block,i;int c,g;
    assert(a&&b&&observer);vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_audition_init(observer);
    p.profile=profile;p.drive_mode=VSL_BENCH;p.ignition=1;p.start_id=1;p.rpm=6000;p.load=.85;
    p.master=.3;p.space=.37;p.perspective=.41;p.width=.81;p.propagation=1;
    p.pressure_texture=p.structure_transfer=.65;vsl_set_params(a,&p);vsl_set_params(b,&p);
    for(block=0;block<260;++block) {
        assert(vsl_process_layout(a,aa,257,channels,sa));
        assert(vsl_audition_process_layout(b,observer,bb,257,channels,sb,views));
        assert(!memcmp(a,b,sizeof *a));assert(!memcmp(aa,bb,257*channels*sizeof(float)));assert(!memcmp(sa,sb,sizeof sa));
        for(i=0;i<257;++i)for(c=0;c<channels;++c) {
            double sum=0;assert(views[i*VSL_AUDITION_MODES*channels+c]==aa[i*channels+c]);
            for(g=0;g<VSL_AUDITION_GROUPS;++g) {
                float only=views[(i*VSL_AUDITION_MODES+1+2*g)*channels+c];
                float without=views[(i*VSL_AUDITION_MODES+2+2*g)*channels+c];
                assert(isfinite(only)&&isfinite(without));sum+=only;
                assert(fabs((double)only+without-aa[i*channels+c])<2e-7);
            }
            assert(fabs(sum-aa[i*channels+c])<2e-7);
        }
    }
    for(g=0;g<VSL_AUDITION_MODES;++g)assert(!observer->clipped[g]);
    free(a);free(b);free(observer);
}
static void independent_masked_renderer(int channels) {
    VslEngine *e=malloc(sizeof *e);VslSpatial *state=calloc(1,sizeof *state);VslObjectFrame input={0},masked={0};
    VslParams p=vsl_default_params(0);double native[12],observed[12];unsigned i;int c;
    unsigned mask=(1u<<VSL_EXHAUST_L)|(1u<<VSL_BODY)|(1u<<VSL_EVENT);
    assert(e&&state);vsl_init(e,48000,48271);
    for(i=0;i<9600;++i) {
        p.perspective=.5+.4*sin(i*.0002);p.width=.7;p.space=.43;p.propagation=i>=2000;
        e->smooth=e->target=p;
        if(i%240==0) { vsl_scene_update(e,channels);vsl_audition_scene_update(e,state,channels); }
        for(c=0;c<VSL_OBJECTS;++c) {
            input.sample[c]=.03*sin(i*(.021+c*.006)+.11*c);
            masked.sample[c]=mask&(1u<<c)?input.sample[c]:0;
        }
        vsl_scene_tick(e,&masked,native,channels);
        vsl_audition_scene_tick(e,state,&input,mask,observed,channels);
        for(c=0;c<channels;++c)assert(fabs(native[c]-observed[c])<1e-13);
    }
    free(e);free(state);
}
static void partition(void) {
    unsigned mask=0;int g;char name[80];
    for(g=0;g<VSL_AUDITION_GROUPS;++g) { unsigned one=vsl_audition_group_mask(g);assert(one&&!(mask&one));mask|=one; }
    assert(mask==(1u<<VSL_OBJECTS)-1);
    assert(!vsl_audition_group_mask(-1)&&!vsl_audition_group_mask(VSL_AUDITION_GROUPS));
    assert(!vsl_audition_mode_name(-1,name,sizeof name)&&!vsl_audition_mode_name(VSL_AUDITION_MODES,name,sizeof name));
    assert(!vsl_audition_mode_name(1,name,2));
}
int main(void) {
    int profile;partition();independent_masked_renderer(2);independent_masked_renderer(12);
    for(profile=0;profile<VSL_PROFILE_COUNT;++profile) { integration(profile,2);integration(profile,12); }
    puts("source audition: full native engine unchanged, masked renderer equality, partition/linear complement and all-five-template layouts pass");return 0;
}
