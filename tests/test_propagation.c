#include "core/engine.h"
#include "spatial/scene.h"
#include "spatial/propagation.h"
#include "profiles/propagation.h"
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void prepare(VslPropagation *s,const VslObjectInfo *source,double sr) {
    int i;memset(s,0,sizeof *s);
    for(i=0;i<VSL_OBJECTS;++i)vsl_propagation_target(s,i,source,0,0,0,sr);
}
static void impulse(void) {
    VslPropagation *s=malloc(sizeof *s);VslObjectInfo source={"test",1.2,.55,-.5};
    const VslPropagationProfile *p=vsl_propagation_profile();
    double sum[3]={0},moment[3]={0},out[3],sr=48000;int n,k;
    CHECK(s!=NULL,"allocate path state");if(!s)return;prepare(s,&source,sr);
    CHECK(s->clamped_paths==0,"test geometry fits history");
    CHECK(s->delay[0][0]<s->delay[0][1],"left-side source reaches left ear first");
    CHECK(s->target_shadow[0][0]==0&&s->target_shadow[0][1]>0,"head shadow only affects far ear");
    for(n=0;n<4000;++n) {
        vsl_propagation_tick(s,0,n==0?1:0,out);vsl_propagation_advance(s);
        for(k=0;k<3;++k) { sum[k]+=out[k];moment[k]+=n*out[k];CHECK(isfinite(out[k]),"impulse finite"); }
    }
    for(k=0;k<3;++k)CHECK(fabs(sum[k]-s->target_gain[0][k])<1e-9,"path preserves documented DC gain including head-shadow filter");
    /* Near ear and centre have no shadow filter, so their impulse moments
       directly measure fractional time-of-flight, independent of peak bin. */
    for(k=0;k<3;k+=2) {
        double ear=k==0?p->ear_spacing_m*.5:0;
        double distance=sqrt(source.x*source.x+(source.y-ear)*(source.y-ear)+source.z*source.z);
        CHECK(fabs(moment[k]/sum[k]-distance/p->speed_mps*sr-VSL_PATH_LATENCY)<1e-8,"fractional impulse moment matches geometry plus explicit FIR latency");
    }
    source.y=-source.y;prepare(s,&source,sr);
    CHECK(s->delay[0][1]<s->delay[0][0]&&s->target_shadow[0][1]==0,"mirrored source reverses near ear and head shadow");
    source.y=0;prepare(s,&source,sr);
    for(n=0;n<800;++n) {
        vsl_propagation_tick(s,0,n==0?1:0,out);vsl_propagation_advance(s);
        CHECK(out[0]==out[1],"centred source produces identical ear signals");
    }
    free(s);
}
static void operating_range(void) {
    static const double rates[]={16000,44100,48000,96000,192000};
    VslEngine *e=malloc(sizeof *e);int r,view,i;
    CHECK(e!=NULL,"allocate engine");if(!e)return;
    for(r=0;r<5;++r)for(view=0;view<=100;++view) {
        vsl_init(e,rates[r],48271);e->smooth.perspective=view/100.;vsl_scene_update(e,2);
        CHECK(e->spatial.propagation.clamped_paths==0,"all supported rates and listener positions fit delay storage");
        for(i=0;i<VSL_OBJECTS;++i) {
            const VslObjectInfo *o=vsl_object_info(i);
            double lx,ly,lz,d;vsl_listener_position(view/100.,&lx,&ly,&lz);
            d=sqrt((o->x-lx)*(o->x-lx)+(o->y-ly)*(o->y-ly)+(o->z-lz)*(o->z-lz));
            CHECK(fabs(e->spatial.propagation.target_delay[i][2]-d/343*rates[r]-VSL_PATH_LATENCY)<1e-8,"centre time-of-flight uses scene coordinates plus explicit FIR latency");
        }
    }
    free(e);
}
static void integrated(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b),*c=malloc(sizeof *c);
    VslParams p=vsl_default_params(0),q;float aa[256*2],bb[256*2],cc[256*12];
    float sa[256*VSL_OBJECTS],sb[256*VSL_OBJECTS],sc[256*VSL_OBJECTS];
    double difference=0,max_step=0,last[2]={0};int n,i;
    CHECK(a&&b&&c,"allocate layouts and bypass comparison");if(!a||!b||!c)goto done;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_init(c,48000,48271);
    p.drive_mode=VSL_AUTODRIVE;p.width=.8;q=p;q.propagation=1;
    vsl_set_params(a,&p);vsl_set_params(b,&q);vsl_set_params(c,&q);
    for(n=0;n<600;++n) {
        vsl_process_layout(a,aa,256,2,sa);vsl_process_layout(b,bb,256,2,sb);vsl_process_layout(c,cc,256,12,sc);
        CHECK(!memcmp(sa,sb,sizeof sa)&&!memcmp(sb,sc,sizeof sb),"propagation and speaker layout never change source samples");
        CHECK(!memcmp(&a->drive,&b->drive,sizeof a->drive)&&!memcmp(&b->drive,&c->drive,sizeof b->drive),"propagation/layout never change drive state");
        for(i=0;i<512;++i)difference+=fabs(aa[i]-bb[i]);
    }
    CHECK(difference>1,"enabled module changes actual output");
    CHECK(b->spatial.propagation.mix==1,"propagation switch settles exactly on");
    q.width=0;vsl_set_params(b,&q);
    for(n=0;n<150;++n)vsl_process(b,bb,256);
    for(i=0;i<256;++i)CHECK(fabs(bb[2*i]-bb[2*i+1])<1e-7,"width zero folds direct path and reflection/filter history to mono");
    /* Pure OSC may still be spatialised, but not fed random waveform content. */
    q.pure_osc=1;q.width=.8;vsl_init(a,48000,123);vsl_init(b,48000,9876);
    vsl_set_params(a,&q);vsl_set_params(b,&q);
    for(n=0;n<600;++n) {
        vsl_process(a,aa,256);vsl_process(b,bb,256);
        if(n>400)CHECK(!memcmp(aa,bb,sizeof aa),"propagated pure OSC remains seed independent");
    }
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);vsl_set_params(a,&q);vsl_set_params(b,&q);
    for(n=0;n<300;++n) {
        vsl_process(a,aa,256);
        vsl_process(b,bb,17);vsl_process(b,bb+34,63);vsl_process(b,bb+160,176);
        CHECK(!memcmp(aa,bb,sizeof aa),"fractional paths independent of host block splits");
    }
    /* Exercise moving perspective and rapid bypass changes with no source
       discontinuity. This is a click bound, not a perceptual quality claim. */
    memset(&a->objects,0,sizeof a->objects);last[0]=last[1]=0;
    for(n=0;n<20000;++n) {
        double out[2];
        if(n%240==0) { a->smooth.perspective=(n%2400)/2400.;a->target.propagation=!a->target.propagation;vsl_scene_update(a,2); }
        a->objects.sample[VSL_EXHAUST_L]=.1*sin(n*.03);
        vsl_scene_tick(a,&a->objects,out,2);
        for(i=0;i<2;++i) { CHECK(isfinite(out[i]),"moving path finite");if(n>2000)max_step=fmax(max_step,fabs(out[i]-last[i]));last[i]=out[i]; }
    }
    CHECK(max_step<.02,"moving/changed path stays smooth for continuous test input");
done:free(a);free(b);free(c);
}
int main(void) {
    impulse();operating_range();integrated();
    if(!failures)puts("PASS: geometric path impulses, fractional delay, head-side symmetry, sample-rate range, source/drive independence, mono and smooth switching");
    return failures?1:0;
}
