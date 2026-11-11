#define _CRT_SECURE_NO_WARNINGS
#include "../atlas_monitor_v1/models.h"
#include "atlas_drive/render.h"
#include "core/engine.h"
#include "core/modules.h"
#include "drive/drive.h"
#include "drive/scenarios.h"
#include "spatial/scene.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include <xmmintrin.h>

#define CAPACITY 512
static AmModels models;
static SaBank bank;
static AdRender render;
static VslEngine engine;
static float output[CAPACITY*12],stereo[8][CAPACITY*2],events[CAPACITY],objects[5][CAPACITY*VSL_OBJECTS];
static AdTelemetry telemetry[CAPACITY];
static VslObjectFrame spatial_input[CAPACITY];
static double times[16000];
static double cycle_counts[16000];
typedef struct {
    unsigned frame,frames,lower,upper,texture_updates;
    double wall_seconds,cycles,root;
} BlockRecord;
static BlockRecord records[16000];
static uint64_t hash(uint64_t value,const void *data,size_t size) {
    const unsigned char *p=data;size_t i;
    for(i=0;i<size;++i){value^=p[i];value*=UINT64_C(1099511628211);}return value;
}
static double timer(void) {
    LARGE_INTEGER count,frequency;QueryPerformanceCounter(&count);QueryPerformanceFrequency(&frequency);
    return (double)count.QuadPart/frequency.QuadPart;
}
static int compare(const void *a,const void *b) {
    double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);
}
static int integer(const char *text,int low,int high,int *v) {
    char *end;long x=strtol(text,&end,10);
    if(end==text||*end||x<low||x>high)return 0;*v=(int)x;return 1;
}
static void inputs(AdControl *control,const VslParams *p) {
    control->drive=(AdInput){p->drive_mode,p->ignition,p->start_id,p->gear,p->auto_gear,p->backfire,p->rpm,p->load,p->throttle,p->brake};
}
int main(int argc,char **argv) {
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl control={{0},{.2,1,.2,.7,0,0,1,0}};
    AdCapture capture={0};VslParams params=vsl_default_params(VSL_V10);
    unsigned at,frames,blocks=0,exceeded=0,i,c;double total=0,peak=0,maximum=0,total_cycles=0;
    uint64_t output_hash=UINT64_C(14695981039346656037),source_hash=UINT64_C(14695981039346656037);
    int selected,block,channels,captures,propagation,seconds,mode=-1,flush=0;
    const char *names[]={"full","dna","residual","auxiliary","spatial"};
    if((argc!=9&&argc!=10&&argc!=11)||!integer(argv[1],0,1,&selected)||!integer(argv[3],1,CAPACITY,&block)||
       !integer(argv[4],2,12,&channels)||(channels!=2&&channels!=12)||
       !integer(argv[5],0,1,&captures)||!integer(argv[6],0,1,&propagation)||!integer(argv[7],1,60,&seconds)||
       strcmp(argv[8],"shifts")||(argc==11&&!integer(argv[10],0,1,&flush))) {
        fputs("bank0|1 full|dna|residual|auxiliary|spatial block1..512 channels2|12 capture0|1 propagation0|1 seconds1..60 shifts [trace.csv [flush0|1]]\n",stderr);return 1;
    }
    for(i=0;i<5;++i)if(!strcmp(argv[2],names[i]))mode=(int)i;if(mode<0)return 1;
    if(!am_models_load(&models,selected)||!am_models_bank(&models,&bank))return 2;
    config.channels=channels;config.residual_bank=&models.residual;
    control.mix.spatial=1;control.mix.propagation=propagation;
    control.mix.residual_gain=.5;control.mix.body_mix=1;
    control.mix.intake_gain=control.mix.mechanical_gain=control.mix.air_gain=.5;
    control.mix.road_gain=control.mix.wind_gain=.3;
    vsl_scenario_apply(VSL_SCENARIO_SHIFTS,0,&params);inputs(&control,&params);
    if(!ad_render_init(&render,&engine,&config,&control))return 2;
    if(captures) {
        capture.dna_raw=stereo[0];capture.dna=stereo[1];capture.dry=stereo[2];
        capture.residual_raw=stereo[3];capture.residual=stereo[4];capture.body_raw=stereo[5];
        capture.body=stereo[6];capture.aux=stereo[7];capture.events=events;capture.telemetry=telemetry;
        capture.objects=objects[0];capture.residual_objects=objects[1];capture.body_objects=objects[2];
        capture.aux_raw=objects[3];capture.aux_objects=objects[4];
    }
    if(mode==1)sa_voice_set(&render.dna,selected?63.333333333333:40,1,1);
    if(mode==2)ra_voice_set(&render.residual,selected?63.333333333333:40,.5);
    engine.smooth.space=.2;engine.smooth.width=.7;engine.smooth.perspective=.3;
    engine.target.propagation=propagation;vsl_scene_update(&engine,channels);
    if(mode==3) {
        vsl_scenario_apply(VSL_SCENARIO_FIXED,0,&params);params.rpm=4800;
        inputs(&control,&params);if(!ad_render_set(&render,&control))return 3;
        for(i=0;i<1600;++i)vsl_drive_step(&engine.drive,&engine.target,.005);
        vsl_orchestrate(&engine,.005);
    }
    frames=(unsigned)seconds*48000;
    for(at=0;at<frames;) {
        unsigned n=frames-at,updates_before=0,updates_after=0,saved_csr;double start,elapsed;ULONG64 cycles_before,cycles_after;
        if(n>(unsigned)block)n=(unsigned)block;
        if(mode==0) {
            vsl_scenario_apply(VSL_SCENARIO_SHIFTS,at/48000.,&params);inputs(&control,&params);
            if(!ad_render_set(&render,&control))return 3;
        } else if(mode==4) {
            for(i=0;i<n;++i)for(c=0;c<VSL_OBJECTS;++c)
                spatial_input[i].sample[c]=.01*sin((at+i)*(.013+.001*c));
        }
        for(i=0;i<bank.count;++i)updates_before+=(unsigned)render.dna.texture[i].updates;
        saved_csr=_mm_getcsr();if(flush)_mm_setcsr(saved_csr|0x8040u);
        if(!QueryThreadCycleTime(GetCurrentThread(),&cycles_before))return 3;
        start=timer();
        if(mode==0) {
            if(!ad_render_process(&render,output,n,captures?&capture:NULL))return 3;
        } else for(i=0;i<n;++i) {
            double x[12]={0},raw[2];VslObjectFrame a,b;
            if(mode==1) {if(!sa_voice_tick_body(&render.dna,&render.body_band,x,raw))return 3;}
            else if(mode==2)ra_voice_tick(&render.residual,x,raw);
            else if(mode==3){da_voice_tick(&render.auxiliary,&engine,&a,&b);da_stereo(&b,x);}
            else vsl_scene_tick(&engine,&spatial_input[i],x,channels);
            for(c=0;c<(unsigned)channels;++c)output[i*channels+c]=(float)x[c];
        }
        elapsed=timer()-start;
        if(flush)_mm_setcsr(saved_csr);
        if(!QueryThreadCycleTime(GetCurrentThread(),&cycles_after))return 3;
        if(blocks>=sizeof times/sizeof *times)return 3;
        for(i=0;i<bank.count;++i)updates_after+=(unsigned)render.dna.texture[i].updates;
        records[blocks]=(BlockRecord){at,n,render.dna.lower,render.dna.upper,updates_after-updates_before,
                                     elapsed,(double)(cycles_after-cycles_before),render.dna.root_hz};
        cycle_counts[blocks]=(double)(cycles_after-cycles_before);total_cycles+=cycle_counts[blocks];
        times[blocks++]=elapsed;total+=elapsed;if(elapsed>maximum)maximum=elapsed;
        if(elapsed>n/48000.)++exceeded;
        output_hash=hash(output_hash,output,n*channels*sizeof(float));
        if(captures&&mode==0) {
            for(c=0;c<8;++c)source_hash=hash(source_hash,stereo[c],n*2*sizeof(float));
            for(c=0;c<5;++c)source_hash=hash(source_hash,objects[c],n*VSL_OBJECTS*sizeof(float));
            source_hash=hash(source_hash,events,n*sizeof(float));
        }
        for(i=0;i<n*(unsigned)channels;++i) {
            if(!isfinite(output[i]))return 3;if(fabs(output[i])>peak)peak=fabs(output[i]);
        }
        at+=n;
    }
    if(argc>=10) {
        FILE *trace=fopen(argv[9],"rb");if(trace){fclose(trace);return 3;}
        trace=fopen(argv[9],"wb");if(!trace)return 3;
        fputs("frame,frames,wall_seconds,cycles,root_hz,lower,upper,texture_updates\n",trace);
        for(i=0;i<blocks;++i) {
            const BlockRecord *r=&records[i];
            fprintf(trace,"%u,%u,%.17g,%.17g,%.17g,%u,%u,%u\n",r->frame,r->frames,
                    r->wall_seconds,r->cycles,r->root,r->lower,r->upper,r->texture_updates);
        }
        if(fclose(trace))return 3;
    }
    qsort(times,blocks,sizeof *times,compare);
    qsort(cycle_counts,blocks,sizeof *cycle_counts,compare);
    printf("{\"bank\":%d,\"mode\":\"%s\",\"block\":%d,\"channels\":%d,\"capture\":%d,\"propagation\":%d,\"seconds\":%d,\"frames\":%u,\"blocks\":%u,\"process_seconds\":%.12g,\"mean_block_ms\":%.12g,\"p99_block_ms\":%.12g,\"max_block_ms\":%.12g,\"budget_ms\":%.12g,\"budget_exceedances\":%u,\"process_cycles\":%.0f,\"p99_block_cycles\":%.0f,\"max_block_cycles\":%.0f,\"output_hash\":\"%016llx\",\"source_hash\":\"%016llx\",\"peak\":%.12g,\"shifts\":%u,\"flush_subnormals\":%d}\n",
        selected,names[mode],block,channels,captures,propagation,seconds,frames,blocks,total,
        1000*total/blocks,1000*times[(blocks-1)*99/100],1000*maximum,block/48.,exceeded,
        total_cycles,cycle_counts[(blocks-1)*99/100],cycle_counts[blocks-1],
        (unsigned long long)output_hash,(unsigned long long)source_hash,peak,engine.drive.shift_events,flush);
    return 0;
}
