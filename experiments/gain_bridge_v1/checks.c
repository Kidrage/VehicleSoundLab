#ifdef NDEBUG
#undef NDEBUG
#endif
#include "bridge.h"
#include "core/modules.h"
#include <assert.h>
#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
static void ramp_math(unsigned period) {
    VslGainBridge b;VslVoicing v={0};float pairs[VSL_BRIDGE_GAINS*2];unsigned i;
    assert(vsl_gain_bridge_init(&b,1));v.dna_gain=1;v.body_gain=.4;
    assert(!vsl_gain_bridge_control(&b,&v,0));assert(vsl_gain_bridge_control(&b,&v,period));
    for(i=1;i<=period;++i) {
        vsl_gain_bridge_audio(&b,&v,pairs);
        assert(fabs(v.dna_gain-(double)i/period)<1e-14);
        assert(fabs(v.body_gain-.4*i/period)<1e-14);
    }
    assert(b.current[0]==1&&b.current[1]==.4);
    for(i=0;i<period;++i)vsl_gain_bridge_audio(&b,&v,pairs);
    assert(v.dna_gain==1&&v.body_gain==.4);
    assert(fabs(b.maximum_ramp_step[0]-1./period)<1e-14);
    v.dna_gain=0;assert(vsl_gain_bridge_control(&b,&v,period));
    for(i=1;i<=period;++i) { vsl_gain_bridge_audio(&b,&v,pairs);assert(fabs(v.dna_gain-(1-(double)i/period))<1e-14); }
    assert(v.dna_gain==0);
}
static void integration(int profile,int channels,int enabled) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslGainBridge bridge;
    VslParams p=vsl_default_params(profile);float aa[257*12],bb[257*12],sa[257*10],sb[257*10];
    unsigned block,i;int c;
    assert(a&&b&&vsl_gain_bridge_init(&bridge,enabled));vsl_init(a,48000,48271);vsl_init(b,48000,48271);
    p.drive_mode=VSL_AUTODRIVE;p.ignition=p.start_id=1;p.master=.3;p.space=.37;p.propagation=1;p.perspective=.41;p.width=.81;
    p.pressure_texture=p.structure_transfer=.65;vsl_set_params(a,&p);vsl_set_params(b,&p);
    for(block=0;block<900;++block) {
        assert(vsl_process_layout(a,aa,257,channels,sa));
        assert(vsl_gain_bridge_process(b,&bridge,bb,257,channels,sb,NULL));
        if(!enabled) { assert(!memcmp(a,b,sizeof *a));assert(!memcmp(aa,bb,257*channels*sizeof(float)));assert(!memcmp(sa,sb,sizeof sa)); }
        else {
            assert(!memcmp(&a->drive,&b->drive,sizeof a->drive));assert(!memcmp(&a->voice,&b->voice,sizeof a->voice));
            assert(!memcmp(&a->control,&b->control,sizeof a->control));assert(!memcmp(&a->dna,&b->dna,sizeof a->dna));
            assert(!memcmp(&a->high_orders,&b->high_orders,sizeof a->high_orders));assert(!memcmp(&a->events,&b->events,sizeof a->events));
            assert(a->nvh.seed==b->nvh.seed&&a->mechanical.rotating_seed==b->mechanical.rotating_seed&&a->mechanical.fired_seed==b->mechanical.fired_seed);
            for(i=0;i<257;++i)for(c=7;c<10;++c)assert(sa[i*10+c]==sb[i*10+c]);
        }
        for(i=0;i<257*(unsigned)channels;++i)assert(isfinite(bb[i])&&fabs(bb[i])<.95);
    }
    for(c=0;c<VSL_BRIDGE_GAINS;++c)assert(bridge.maximum_ramp_step[c]<=bridge.maximum_held_step[c]/240+1e-14);
    free(a);free(b);
}
static void partition_and_layout(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b),*bed=malloc(sizeof *bed);
    VslGainBridge ba,bb,bc;VslParams p=vsl_default_params(0);
    unsigned total=160000,done,n,i;float *aa=malloc(total*2*sizeof(float)),*ab=malloc(total*2*sizeof(float));
    float out[257*12],sa[257*10],sb[257*10];
    assert(a&&b&&bed&&aa&&ab);vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_init(bed,48000,48271);
    assert(vsl_gain_bridge_init(&ba,1)&&vsl_gain_bridge_init(&bb,1)&&vsl_gain_bridge_init(&bc,1));
    p.drive_mode=VSL_AUTODRIVE;p.ignition=p.start_id=1;p.pressure_texture=p.structure_transfer=.65;
    vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_set_params(bed,&p);
    for(done=0;done<total;) {
        n=total-done;if(n>257)n=257;
        assert(vsl_gain_bridge_process(a,&ba,aa+done*2,n,2,sa,NULL));
        assert(vsl_gain_bridge_process(bed,&bc,out,n,12,sb,NULL));
        assert(!memcmp(sa,sb,n*10*sizeof(float)));assert(!memcmp(&a->drive,&bed->drive,sizeof a->drive));
        done+=n;
    }
    for(i=0;i<total;++i)assert(vsl_gain_bridge_process(b,&bb,ab+i*2,1,2,NULL,NULL));
    assert(!memcmp(aa,ab,total*2*sizeof(float)));assert(!memcmp(a,b,sizeof *a));assert(!memcmp(&ba,&bb,sizeof ba));
    free(a);free(b);free(bed);free(aa);free(ab);
}
int main(void) {
    int profile,channels,enabled;unsigned periods[]={80,221,240,480,960},i;
    for(i=0;i<5;++i)ramp_math(periods[i]);
    for(profile=0;profile<VSL_PROFILE_COUNT;++profile)for(channels=2;channels<=12;channels+=10)
        for(enabled=0;enabled<=1;++enabled)integration(profile,channels,enabled);
    partition_and_layout();
    puts("gain bridge: causal closed-form ramps, exact bypass, native control/drive/clocks/RNG preserved, layout and block invariance pass");return 0;
}
