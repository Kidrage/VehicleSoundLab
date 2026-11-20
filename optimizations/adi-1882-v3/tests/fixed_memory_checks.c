#include "experiments/vehicle_source_v1/bridge.h"
#include "embedded/fixed_assets.h"
#include "drive_catalog/catalog.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Test-only output storage is deliberately outside the production image. */
#define TEST_CHANNELS 23
#define EXACT_FRAMES 1024
#define RENDER_FRAMES 32768
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"fixed memory line %d: %s\n",__LINE__,#x); goto done; } } while(0)
static float monitor[(VS_BLOCK_MAX+1)*2];
static float packed[(VS_BLOCK_MAX+1)*TEST_CHANNELS];
static float reference[EXACT_FRAMES][TEST_CHANNELS+2];
typedef struct {uint64_t hash,frames;float error,peak;double energy;} RenderResult;

static uint64_t hash_float(uint64_t h,float x){
    uint32_t bits;memcpy(&bits,&x,sizeof bits);
    h^=bits;return h*UINT64_C(1099511628211);
}
static int same_state(VsbHandle *h,const VsTelemetry *expected){
    VsTelemetry actual;if(!vsl_source_state(h,&actual))return 0;
    return !memcmp(&actual,expected,sizeof actual);
}
static int boundaries(VsbHandle *h){
    VsTelemetry t;unsigned n;int ok=0;
    CHECK(vsl_source_state(h,&t)&&t.frame==0);
    for(n=0;n<sizeof monitor/sizeof *monitor;++n)monitor[n]=123.25f;
    for(n=0;n<sizeof packed/sizeof *packed;++n)packed[n]=123.25f;
    CHECK(vsl_source_process(h,NULL,NULL,0));
    CHECK(vsl_source_process(h,monitor,packed,0));
    CHECK(same_state(h,&t));
    CHECK(!vsl_source_process(h,monitor,packed,VS_BLOCK_MAX+1));
    CHECK(!vsl_source_process(h,monitor,monitor,64));
    CHECK(!vsl_source_process(h,monitor,monitor+1,64));
    CHECK(!vsl_source_process(h,packed+1,packed,64));
    CHECK(same_state(h,&t));
    for(n=0;n<sizeof monitor/sizeof *monitor;++n)CHECK(monitor[n]==123.25f);
    for(n=0;n<sizeof packed/sizeof *packed;++n)CHECK(packed[n]==123.25f);
    ok=1;
done:return ok;
}
static int render(int compare,RenderResult *result){
    const unsigned sizes[]={1,64,73,240,1024};
    VsbHandle *h=NULL,*extra=NULL;VsControl c;VsTelemetry t;unsigned at=0,block=0;
    int ok=0;RenderResult r={UINT64_C(1469598103934665603),0,0,0,0};
    CHECK(h=vsl_source_open(DC_FINE_IDLE));
    CHECK(vsl_source_channels()==TEST_CHANNELS);
    CHECK(boundaries(h));
    CHECK(vsl_source_state(h,&t));
    extra=vsl_source_open(DC_FINE_IDLE);CHECK(!extra);
    CHECK(same_state(h,&t));
    CHECK(vsl_source_controls(h,&c));
    c.mode=VS_BENCH;c.ignition=c.start_id=1;c.rpm=1600;c.load=.4f;
    CHECK(vsl_source_set(h,&c));
    while(at<RENDER_FRAMES){
        unsigned n=compare?VS_BLOCK_MAX:sizes[block++%(sizeof sizes/sizeof *sizes)];
        unsigned i,k,ch;if(n>RENDER_FRAMES-at)n=RENDER_FRAMES-at;
        CHECK(vsl_source_process(h,monitor,packed,n));
        for(i=0;i<n;++i){
            unsigned offset=0;
            for(ch=0;ch<2;++ch){
                float sum=0;
                for(k=0,offset=0;k<VS_STEMS;++k){
                    const VsStemInfo *info=vs_stem_info(k);
                    float x=packed[i*TEST_CHANNELS+offset+(info->channels==2?ch:0)];
                    CHECK(isfinite(x));sum+=x*(ch?info->monitor_right:info->monitor_left);
                    offset+=info->channels;
                }
                CHECK(isfinite(monitor[2*i+ch]));
                r.error=fmaxf(r.error,fabsf(sum-monitor[2*i+ch]));
                CHECK(fabsf(sum-monitor[2*i+ch])<2e-6f);
                r.peak=fmaxf(r.peak,fabsf(monitor[2*i+ch]));
                r.energy+=(double)monitor[2*i+ch]*monitor[2*i+ch];
            }
            for(k=0;k<TEST_CHANNELS+2;++k){
                float x=k<2?monitor[2*i+k]:packed[i*TEST_CHANNELS+k-2];
                r.hash=hash_float(r.hash,x);
                if(at+i<EXACT_FRAMES){
                    if(compare)CHECK(!memcmp(&x,&reference[at+i][k],sizeof x));
                    else reference[at+i][k]=x;
                }
            }
        }
        at+=n;
        CHECK(vsl_source_state(h,&t)&&t.frame==at);
    }
    CHECK(r.energy>0);r.frames=at;*result=r;ok=1;
done:vsl_source_close(extra);vsl_source_close(h);return ok;
}
static int four_events(void){
    VsbHandle *h=NULL;VsControl c;VsTelemetry t;EsProfile p={0};EsNotice notices[16];
    unsigned k,n,count,slots=0,offset;double energy[ES_VOICES]={0};int ok=0;
    CHECK(h=vsl_source_open(DC_FINE_IDLE));
    p.mode_count=1;p.duration_seconds=1;p.release_seconds=.02f;p.level=.3f;
    p.modes[0]=(EsMode){175,.2f,.3f,.3f,175,0};
    CHECK(es_profile_valid(&p));CHECK(vsl_source_event_profile(h,ES_AFTERFIRE,&p));
    CHECK(vsl_source_controls(h,&c));
    c.ignition=c.start_id=0;c.events.enabled=1;c.events.gain=.5f;
    c.events.manual_type=ES_AFTERFIRE;c.events.levels[ES_AFTERFIRE]=1;
    for(k=0;k<ES_VOICES;++k){
        c.events.manual_sequence=k+1;CHECK(vsl_source_set(h,&c));
        CHECK(vsl_source_process(h,monitor,packed,1));
    }
    CHECK(vsl_source_process(h,monitor,packed,VS_BLOCK_MAX));
    CHECK(vsl_source_state(h,&t));
    CHECK(t.event_active==ES_VOICES&&t.event_peak==ES_VOICES&&t.event_started==ES_VOICES);
    CHECK(!t.event_overflow&&!t.event_log_lost&&!t.event_rejected);
    count=vsl_source_events(h,notices,16);CHECK(count==ES_VOICES);
    for(k=0;k<count;++k){
        CHECK(notices[k].action==ES_STARTED&&notices[k].type==ES_AFTERFIRE);
        CHECK(notices[k].slot<ES_VOICES);slots|=1u<<notices[k].slot;
        CHECK(notices[k].frame==k);
    }
    CHECK(slots==(1u<<ES_VOICES)-1);
    for(k=0,offset=0;k<VS_EVENT_0;++k)offset+=vsl_source_stem_channels(k);
    for(n=0;n<VS_BLOCK_MAX;++n)for(k=0;k<ES_VOICES;++k){
        float x=packed[n*TEST_CHANNELS+offset+k];CHECK(isfinite(x));energy[k]+=(double)x*x;
    }
    for(k=0;k<ES_VOICES;++k)CHECK(energy[k]>0);
    ok=1;
done:vsl_source_close(h);return ok;
}
static int native_boundaries(void){
    VsAssets *assets=NULL,*extra_assets=NULL;VsEngine *engine=NULL,*extra=NULL;
    AdControl initial;VsControl control;VsOutput out={0};VsTelemetry before,after;
    unsigned n;int ok=0;
    CHECK(assets=vsl_fixed_assets_acquire());
    extra_assets=vsl_fixed_assets_acquire();CHECK(!extra_assets);
    initial=vsl_fixed_initial();vs_control_from_atlas(&initial,&control);
    control.dna_unified=1;
    control.intake_gain=control.air_gain=control.road_gain=control.wind_gain=0;
    CHECK(engine=vs_engine_create(assets,&control));
    CHECK(vs_engine_telemetry(engine,&before)&&before.frame==0);
    extra=vs_engine_create(assets,&control);CHECK(!extra);
    for(n=0;n<sizeof monitor/sizeof *monitor;++n)monitor[n]=123.25f;
    for(n=0;n<sizeof packed/sizeof *packed;++n)packed[n]=123.25f;
    out.monitor=out.stem[VS_DNA]=monitor;
    CHECK(vs_engine_process(engine,&out,0));
    CHECK(!vs_engine_process(engine,&out,73));
    out.stem[VS_DNA]=packed;out.stem[VS_LOW]=packed+1;
    CHECK(!vs_engine_process(engine,&out,73));
    out.stem[VS_LOW]=NULL;
    CHECK(!vs_engine_process(engine,&out,VS_BLOCK_MAX+1));
    CHECK(vs_engine_telemetry(engine,&after)&&!memcmp(&before,&after,sizeof before));
    for(n=0;n<sizeof monitor/sizeof *monitor;++n)CHECK(monitor[n]==123.25f);
    for(n=0;n<sizeof packed/sizeof *packed;++n)CHECK(packed[n]==123.25f);
    CHECK(vs_engine_process(engine,&out,73));
    CHECK(vs_engine_telemetry(engine,&after)&&after.frame==73);
    ok=1;
done:
    vs_engine_destroy(extra);vs_engine_destroy(engine);
    vsl_fixed_assets_release(extra_assets);vsl_fixed_assets_release(assets);return ok;
}
int main(void){
    RenderResult one,two;
    if(!render(0,&one)||!render(1,&two)||!four_events()||!native_boundaries())return 1;
    if(one.frames!=two.frames||one.hash!=two.hash){
        fprintf(stderr,"fixed memory: reopened/partitioned output differs\n");return 1;
    }
    printf("PASS fixed V10: singleton refusal, zero/invalid/overlap transactions, 1/64/73/240/1024 blocks, "
           "reopen/partition hash %016llx, first1024 exact, 23ch sum error %.9g, four live event slots\n",
           (unsigned long long)one.hash,fmaxf(one.error,two.error));
    return 0;
}
