#include "atlas_drive/render.h"
#include "core/engine.h"
#include "drive/drive.h"
#include "drive/scenarios.h"
#include "drive/fueling.h"
#include "atlas_take/parameters.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"aux check line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static SdProfile model[2];static SaBank bank;
static AdRender a,b,c;static VslEngine ea,eb,ec;
static float output[240*12],other[480],third[240*12];
static float raw[3][480],aux_raw[3][240*VSL_OBJECTS],aux[3][240*VSL_OBJECTS],events[3][240];
static void input(AdControl *control,const VslParams *p) {
    control->drive=(AdInput){p->drive_mode,p->ignition,p->start_id,p->gear,p->auto_gear,p->backfire,p->rpm,p->load,p->throttle,p->brake};
}
static void amounts(AdControl *p,double value) {
    p->mix.intake_gain=p->mix.mechanical_gain=p->mix.air_gain=p->mix.road_gain=p->mix.wind_gain=value;
}
static int scenario(int id,unsigned blocks,unsigned *seen,double power[DA_LAYERS]) {
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl ca={{0},{.2,1,.2,.7,0,0,0,0}},cb,cc;AdCapture cap[3]={{0}};
    VslParams params=vsl_default_params(VSL_V10);VslDrive reference;
    unsigned block,i,j;int map[VSL_OBJECTS]={-1,-1,DA_INTAKE,-1,DA_MECHANICAL,DA_AIR,DA_AIR,-1,DA_ROAD,DA_WIND};
    vsl_scenario_apply(id,0,&params);input(&ca,&params);amounts(&ca,1);cb=ca;amounts(&cb,0);cc=ca;cc.mix.spatial=1;
    CHECK(ad_render_init(&a,&ea,&config,&ca)&&ad_render_init(&b,&eb,&config,&cb));
    config.channels=12;CHECK(ad_render_init(&c,&ec,&config,&cc));vsl_drive_reset(&reference,VSL_V10);
    for(i=0;i<3;++i){cap[i].dna_raw=raw[i];cap[i].events=events[i];cap[i].aux_raw=aux_raw[i];cap[i].aux_objects=aux[i];}
    for(block=0;block<blocks;++block) {
        unsigned previous_fired=ea.mechanical.fired_strikes,previous_rotating=ea.mechanical.rotating_strikes;
        vsl_scenario_apply(id,block*.005,&params);input(&ca,&params);cb=ca;amounts(&cb,block<400?0:1);cc=ca;cc.mix.spatial=1;cc.mix.room=.3;
        CHECK(ad_render_set(&a,&ca)&&ad_render_set(&b,&cb)&&ad_render_set(&c,&cc));
        vsl_drive_step(&reference,&ea.target,.005);
        CHECK(ad_render_process(&a,output,240,cap));
        CHECK(ad_render_process(&b,other,1,cap+1));
        cap[1].dna_raw+=2;cap[1].events+=1;cap[1].aux_raw+=VSL_OBJECTS;cap[1].aux_objects+=VSL_OBJECTS;
        CHECK(ad_render_process(&b,other+2,239,cap+1));
        cap[1].dna_raw=raw[1];cap[1].events=events[1];cap[1].aux_raw=aux_raw[1];cap[1].aux_objects=aux[1];
        CHECK(ad_render_process(&c,third,240,cap+2));
        CHECK(!memcmp(&ea.drive,&reference,sizeof reference)&&!memcmp(&ea.drive,&eb.drive,sizeof reference)&&!memcmp(&ea.drive,&ec.drive,sizeof reference));
        CHECK(!memcmp(raw[0],raw[1],sizeof raw[0])&&!memcmp(raw[0],raw[2],sizeof raw[0]));
        CHECK(!memcmp(events[0],events[1],sizeof events[0])&&!memcmp(events[0],events[2],sizeof events[0]));
        CHECK(!memcmp(aux_raw[0],aux_raw[1],sizeof aux_raw[0])&&!memcmp(aux_raw[0],aux_raw[2],sizeof aux_raw[0]));
        CHECK(!memcmp(aux[0],aux[2],sizeof aux[0]));
        if(block>=520)CHECK(!memcmp(aux[0],aux[1],sizeof aux[0]));
        if(!vsl_fueling_allows_firing(&ea.drive))CHECK(ea.mechanical.fired_strikes==previous_fired);
        if(ea.drive.lifecycle==VSL_CRANK&&ea.mechanical.rotating_strikes>previous_rotating)*seen|=1;
        if(ea.drive.fuel.mode==VSL_FUEL_CUT&&ea.mechanical.rotating_strikes>previous_rotating)*seen|=2;
        if(ea.drive.operating==VSL_SHIFT_CUT)*seen|=4;
        if(ea.drive.lifecycle==VSL_OFF)*seen|=8;
        if(ea.drive.speed_kph>5&&fabs(aux_raw[0][VSL_ROAD])+fabs(aux_raw[0][VSL_WIND])>0)*seen|=16;
        for(i=0;i<240;++i)for(j=0;j<VSL_OBJECTS;++j) {
            double x=aux[0][i*VSL_OBJECTS+j];CHECK(isfinite(x));
            if(map[j]>=0)power[map[j]]+=x*x;else CHECK(x==0);
            if(block<400)CHECK(aux[1][i*VSL_OBJECTS+j]==0);
            if(ea.drive.speed_kph==0&&(j==VSL_ROAD||j==VSL_WIND))CHECK(x==0);
        }
        for(i=0;i<480;++i)CHECK(isfinite(output[i])&&fabs(output[i])<.95);
        for(i=0;i<240*12;++i)CHECK(isfinite(third[i])&&fabs(third[i])<.95);
        CHECK(ea.dna.pitch_phase==0&&ea.pad.phase[0]==0&&ea.high_orders.active==0);
        CHECK(ea.frame==a.frame&&a.dna.frame==a.frame&&isfinite(ea.control.phase)&&ea.control.phase>=0&&ea.control.phase<2*VSL_PI);
        if(ea.control.rpm>5&&ea.control.phase>0)*seen|=32;
    }
    return 0;
}
int main(void) {
    const SdProfile *p[2]={model,model+1};unsigned i,seen=0,count;double power[DA_LAYERS]={0};
    AdControl initial={{VSL_BENCH,0,0,1,0,1,1200,.5,0,0},{.2,1,0,.7,0,0,0,0}},bad;
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};const AtField *fields;
    for(i=0;i<2;++i){model[i].rate=48000;model[i].window=1024;model[i].hop=256;model[i].harmonics=8;model[i].base_hz=20+40*i;model[i].harmonic[0].mean[0]=model[i].harmonic[0].mean[2]=.1;}
    CHECK(sa_bank_init(&bank,p,2,0));
    CHECK(!scenario(VSL_SCENARIO_SHIFTS,3200,&seen,power));
    CHECK(!scenario(VSL_SCENARIO_LIFT,1200,&seen,power));
    CHECK((seen&63)==63);for(i=0;i<DA_LAYERS;++i)CHECK(power[i]>1e-12);
    CHECK(ad_render_init(&a,&ea,&config,&initial));fields=at_fields(&count);CHECK(count==27&&!strcmp(fields[count-1].name,"catch_gain"));
    for(i=20;i<count;++i) {
        double *v;bad=initial;v=(double*)((char*)&bad+fields[i].offset);*v=NAN;
        CHECK(!ad_render_set(&a,&bad)&&at_control_same(&a.target,&initial));*v=1.01;CHECK(!ad_render_set(&a,&bad));
        *v=-.01;CHECK(!ad_render_set(&a,&bad));
    }
    printf("PASS: one controller, crank/fuelcut/shift/off permissions, independent sources/RNG/chunks, zero-to-one continuity and2/12objects; seen%u powers",seen);
    for(i=0;i<DA_LAYERS;++i)printf(" %.7g",power[i]);puts("");return 0;
}
