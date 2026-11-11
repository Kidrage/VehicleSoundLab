#include "adapter.h"
#include "profile.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { if(failures<12)fprintf(stderr,"FAIL %s\n",m);++failures; } } while(0)
static void original(const VslEngine *a,const VslEngine *b) {
    CHECK(!memcmp(&a->drive,&b->drive,sizeof a->drive),"original driving state");
    CHECK(!memcmp(&a->dna,&b->dna,sizeof a->dna),"original DNA");
    CHECK(!memcmp(&a->high_orders,&b->high_orders,sizeof a->high_orders),"original high orders");
    CHECK(!memcmp(&a->character,&b->character,sizeof a->character),"original cylinder events/RNG");
    CHECK(!memcmp(&a->mechanical,&b->mechanical,sizeof a->mechanical),"mechanical source state");
    CHECK(!memcmp(&a->combustion,&b->combustion,sizeof a->combustion),"original pressure variation");
}
static void integrated(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b),*c=malloc(sizeof *c),*d=malloc(sizeof *d);
    FpAdapter off,on,bed,single;VslParams p=vsl_default_params(0);
    float x[514],y[514],z[257*12],w[514],sa[257*VSL_OBJECTS],sb[257*VSL_OBJECTS];
    unsigned block,i;uint64_t events;double difference=0;
    CHECK(a&&b&&c&&d,"allocation");if(!a||!b||!c||!d)goto done;
    p.rpm=8000;p.load=.85;p.structure_transfer=.65;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_init(c,48000,48271);vsl_init(d,48000,48271);
    vsl_set_params(a,&p);vsl_set_params(b,&p);vsl_set_params(c,&p);vsl_set_params(d,&p);
    fp_init(&off,48000,0);fp_init(&on,48000,2);fp_init(&bed,48000,2);fp_init(&single,48000,2);
    /* Include the real CRANK/CATCH interval before counting RUNNING events. */
    for(block=0;block<400;++block) {
        VslEngine *base=malloc(sizeof *base);float native[514];
        CHECK(base!=NULL,"baseline allocation");if(!base)break;memcpy(base,a,sizeof *base);
        vsl_process(base,native,257);fp_process(a,&off,x,257,2,NULL);
        CHECK(!memcmp(native,x,sizeof x),"off exact native output");free(base);
        fp_process(b,&on,y,257,2,sa);fp_process(c,&bed,z,257,12,sb);
        for(i=0;i<257;++i)fp_process(d,&single,w+i*2,1,2,NULL);
        CHECK(!memcmp(y,w,sizeof y)&&!memcmp(b,d,sizeof *b),"block1 versus257");
        CHECK(!memcmp(sa,sb,sizeof sa),"ten stems stereo versus714");
        CHECK(!memcmp(&on,&bed,sizeof on)&&!memcmp(&on,&single,sizeof on),"adapter layout/block independent");
        original(a,b);
        for(i=0;i<514;++i) { CHECK(isfinite(y[i])&&fabs(y[i])<.95,"finite unclipped");difference+=fabs(x[i]-y[i]); }
    }
    CHECK(difference>1,"audible path changed");
    if(on.accepted[0]<=100||on.accepted[1]<=100)fprintf(stderr,"fired L=%llu R=%llu character=%u rpm=%.2f lifecycle=%d\n",(unsigned long long)on.accepted[0],(unsigned long long)on.accepted[1],b->character.events[0],b->control.rpm,b->drive.lifecycle);
    CHECK(on.accepted[0]>100&&on.accepted[1]>100,"both banks fired");
    p.ignition=0;vsl_set_params(b,&p);fp_process(b,&on,y,257,2,NULL);events=on.accepted[0]+on.accepted[1];
    for(block=0;block<200;++block)fp_process(b,&on,y,257,2,NULL);
    CHECK(events==on.accepted[0]+on.accepted[1],"no new strikes after shutdown");
    CHECK(!on.denied&&!on.kernel.overflow,"no denied events/voice stealing");
done:free(a);free(b);free(c);free(d);
}
static void bypass(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslParams p;FpAdapter s;
    float x[514],y[514];int mode;unsigned block;
    CHECK(a&&b,"bypass allocation");if(!a||!b)goto done;
    for(mode=0;mode<7;++mode) {
        p=vsl_default_params(mode<5?mode:0);p.rpm=4000;p.load=.85;
        if(mode==0)p.pure_osc=1;if(mode==6)p.combustion_variation=0;
        vsl_init(a,48000,48271);vsl_init(b,48000,48271);
        if(mode==5) { a->dna.custom_count=b->dna.custom_count=1;a->dna.custom_root=b->dna.custom_root=66;a->dna.custom_amp[0]=b->dna.custom_amp[0]=1; }
        vsl_set_params(a,&p);vsl_set_params(b,&p);fp_init(&s,48000,2);
        for(block=0;block<60;++block) {
            vsl_process(a,x,257);fp_process(b,&s,y,257,2,NULL);
            CHECK(!memcmp(x,y,sizeof x),"other template/custom/pureOSC/disabled exact bypass");
        }
        CHECK(!s.accepted[0]&&!s.accepted[1],"no bypass events");
    }
done:free(a);free(b);
}
static void kernel(void) {
    const double rates[]={16000,48000,192000};unsigned r,k;
    CHECK(fp_wavelet(-.001,.000075)==0&&fp_wavelet(0,.000075)==0,"causal onset");
    CHECK(fabs(fp_wavelet(.00015,.000075)-1)<1e-14,"analytic peak");
    for(r=0;r<3;++r) {
        FpKernel s;double y[2],energy=0;
        CHECK(fp_kernel_init(&s,rates[r]),"rate accepted");
        fp_kernel_strike(&s,0,.37/rates[r],1,.000075,.000028);
        for(k=0;k<(unsigned)(rates[r]*.02);++k) {
            fp_kernel_tick(&s,y);CHECK(isfinite(y[0])&&y[1]==0,"independent banks finite");energy+=y[0]*y[0];
        }
        CHECK(energy>0&&fabs(y[0])<1e-16,"pulse and filter decay");
    }
    {
        double slow=.000086,fast=.000023,numerical=0,dt=1e-8;unsigned n;
        for(n=0;n<500000;++n) {
            double x=.65*fp_wavelet((n+.5)*dt,slow)+.35*fp_wavelet((n+.5)*dt,fast);
            numerical+=x*x*dt;
        }
        CHECK(fabs(numerical/fp_kernel_energy(slow,fast)-1)<1e-10,"closed-form energy versus quadrature");
    }
}
int main(void) {
    kernel();integrated();bypass();if(!failures)puts("Firing pulse: causal kernel,energy,bypass,original state,permission,blocks/layouts pass.");
    return failures?1:0;
}
