#include "atlas_take/take.h"
#include "core/engine.h"
#include "drive/scenarios.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"stereo bed line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define N 240
static SdProfile profile[2];static SaBank bank;static RaBank residual;
static AdRender render[4];static VslEngine engine[4];
static float out[4][N*12],raw[4][N*2],dna[4][N*2],body[4][N*2],noise[4][N*2];
static float event[4][N],aux[4][N*VSL_OBJECTS],obj[4][N*VSL_OBJECTS];
static float observation[4][N*2],bed[4][N*12];
static float startup[4][N*2];
static float catch_bloom[4][N*2];
static AdCapture capture[4];

static int routing(void) {
    SbLayout s={2};double in[2],a[12],b[12];unsigned i,c;
    CHECK(!sb_layout_init(&s,8)&&s.channels==2&&!sb_layout_init(NULL,2));
    for(i=0;i<4000;++i) {
        double width=(i%101)/100.,mid,side,energy;
        in[0]=sin(.031*i);in[1]=cos(.057*i);mid=.5*(in[0]+in[1]);side=.5*(in[0]-in[1]);
        CHECK(sb_layout_init(&s,2));sb_route(&s,in,width,a);
        CHECK(sb_layout_init(&s,12));sb_route(&s,in,width,b);
        CHECK(a[0]==b[0]&&a[1]==b[1]);for(c=2;c<12;++c)CHECK(b[c]==0);
        energy=2*(mid*mid+width*width*side*side);
        CHECK(fabs(a[0]*a[0]+a[1]*a[1]-energy)<2e-15);
        sb_route(&s,in,1,a);CHECK(!memcmp(a,in,sizeof in));
        sb_route(&s,in,0,b);CHECK(b[0]==mid&&b[1]==mid);
    }
    in[0]=1;in[1]=-1;sb_route(&s,in,1,a);CHECK(a[0]==1&&a[1]==-1);
    in[0]=.2;in[1]=.2;sb_route(&s,in,.3,a);CHECK(a[0]==.2&&a[1]==.2);
    return 0;
}
int main(void) {
    const SdProfile *p[2]={profile,profile+1};unsigned h,i,j,k,block;
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR,&residual};
    AdControl control={{0},{.2,1,0,1,0,0,1,0,.35,.6}};
    VslParams params=vsl_default_params(VSL_V10);uint64_t hash[4];
    CHECK(!routing());
    for(i=0;i<2;++i) {
        SdProfile *m=profile+i;m->rate=48000;m->window=1024;m->hop=256;m->harmonics=20;m->base_hz=20+40*i;
        m->components=1;m->rho[0]=.4;
        for(h=0;h<20;++h){m->harmonic[h].rho=.2;for(k=0;k<2;++k){
            m->harmonic[h].mean[k*2]=(.02+.003*i)*cos(h*.3+k*.7)/(h+1);
            m->harmonic[h].mean[k*2+1]=(.02+.003*i)*sin(h*.3+k*.7)/(h+1);
            m->harmonic[h].basis[0][k*2]=.001/(h+1);}}
        residual.root[i]=m->base_hz;residual.profile[i].rate=48000;residual.profile[i].bands=1;residual.profile[i].partials=32;
        residual.profile[i].band[0]=(SrBand){1200,3000,{.00001,.00002},{.4,.2}};
    }
    residual.count=2;CHECK(sa_bank_init(&bank,p,2,8));
    vsl_scenario_apply(VSL_SCENARIO_SHIFTS,0,&params);
    control.drive=(AdInput){params.drive_mode,params.ignition,params.start_id,params.gear,params.auto_gear,params.backfire,
                           params.rpm,params.load,params.throttle,params.brake};
    for(i=0;i<4;++i) {
        config.scene_mode=i==0?AD_SCENE_OBJECTS:AD_SCENE_STEREO_BED;config.channels=i==2?12:2;
        CHECK(ad_render_init(render+i,engine+i,&config,&control));hash[i]=AT_HASH_INITIAL;
        capture[i].dna_raw=raw[i];capture[i].dna=dna[i];capture[i].body=body[i];capture[i].residual=noise[i];
        capture[i].events=event[i];capture[i].aux_objects=aux[i];capture[i].objects=obj[i];
        capture[i].observation=observation[i];capture[i].bed=bed[i];
        capture[i].startup=startup[i];
        capture[i].catch_bloom=catch_bloom[i];
    }
    for(block=0;block<1600;++block) {
        vsl_scenario_apply(VSL_SCENARIO_SHIFTS,block*.005,&params);
        control.drive=(AdInput){params.drive_mode,params.ignition,params.start_id,params.gear,params.auto_gear,params.backfire,
                               params.rpm,params.load,params.throttle,params.brake};
        control.mix.room=block>400?.3:0;control.mix.event_gain=block>400?.2:0;
        control.mix.intake_gain=block>400?.2:0;control.mix.mechanical_gain=block>400?.2:0;
        control.mix.air_gain=block>400?.2:0;control.mix.road_gain=block>400?.2:0;control.mix.wind_gain=block>400?.2:0;
        control.mix.width=block>800?.4:1;
        for(i=0;i<4;++i) {
            CHECK(ad_render_set(render+i,&control));
            if(i!=3)CHECK(ad_render_process(render+i,out[i],N,capture+i));
            else for(j=0;j<N;++j) {
                AdCapture c=capture[i];
                c.dna_raw+=j*2;c.dna+=j*2;c.body+=j*2;c.residual+=j*2;c.events+=j;
                c.aux_objects+=j*VSL_OBJECTS;c.objects+=j*VSL_OBJECTS;c.observation+=j*2;c.bed+=j*2;
                c.startup+=j*2;
                c.catch_bloom+=j*2;
                CHECK(ad_render_process(render+i,out[i]+2*j,1,&c));
            }
            hash[i]=at_hash_sources(hash[i],capture+i,N);
            CHECK(!memcmp(&engine[0].drive,&engine[i].drive,sizeof engine[i].drive));
            CHECK(!memcmp(raw[0],raw[i],sizeof raw[0])&&!memcmp(observation[0],observation[i],sizeof observation[0]));
            for(j=0;j<N*(unsigned)render[i].config.channels;++j)CHECK(isfinite(out[i][j]));
        }
        CHECK(!memcmp(out[1],out[3],N*2*sizeof(float))&&!memcmp(bed[1],bed[3],N*2*sizeof(float)));
        CHECK(!memcmp(&render[1].dna,&render[3].dna,sizeof render[1].dna));
        for(j=0;j<N;++j) {
            CHECK(bed[1][2*j]==bed[2][12*j]&&bed[1][2*j+1]==bed[2][12*j+1]);
            for(k=2;k<12;++k)CHECK(bed[2][12*j+k]==0);
            for(i=1;i<4;++i) {
                CHECK(obj[i][j*VSL_OBJECTS+VSL_EXHAUST_L]==0&&obj[i][j*VSL_OBJECTS+VSL_EXHAUST_R]==0);
                CHECK(obj[i][j*VSL_OBJECTS+VSL_BODY]==0);
            }
            if(block<=400)for(k=2;k<12;++k)CHECK(out[2][12*j+k]==0);
        }
    }
    CHECK(hash[0]==hash[1]&&hash[1]==hash[2]&&hash[2]==hash[3]);
    config.scene_mode=(AdSceneMode)2;CHECK(!ad_render_init(render+3,engine+3,&config,&control));
    printf("PASS:4000 width/energy/layout controls; continuous drive sources %016llx;2/12bed,object isolation,one-sample chunks,invalid config\n",(unsigned long long)hash[0]);
    return 0;
}
