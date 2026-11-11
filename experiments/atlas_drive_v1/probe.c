#define _CRT_SECURE_NO_WARNINGS
#include "atlas_drive/render.h"
#include "core/engine.h"
#include "drive/scenarios.h"
#include "spatial/scene.h"
#include "io/file.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

#define BLOCK 240
#define FILES (5+VSL_OBJECTS)
static SdProfile low,high;
static SaBank bank;
static AdRender render;
static VslEngine engine;
static float output[BLOCK*12],raw[BLOCK*2],dna[BLOCK*2],dry[BLOCK*2],events[BLOCK],objects[BLOCK*VSL_OBJECTS],mono[BLOCK];
static AdTelemetry trace[BLOCK];
static double timer(void) {
#ifdef _WIN32
    LARGE_INTEGER count,freq;QueryPerformanceCounter(&count);QueryPerformanceFrequency(&freq);
    return (double)count.QuadPart/freq.QuadPart;
#else
    return (double)clock()/CLOCKS_PER_SEC;
#endif
}
static int number(const char *s,double *x) { char *end;*x=strtod(s,&end);return end!=s&&!*end&&isfinite(*x); }
static void inputs(AdControl *c,const VslParams *p) {
    c->drive.mode=p->drive_mode;c->drive.ignition=p->ignition;c->drive.start_id=p->start_id;
    c->drive.gear=p->gear;c->drive.automatic=p->auto_gear;c->drive.backfire=p->backfire;
    c->drive.rpm=p->rpm;c->drive.load=p->load;c->drive.throttle=p->throttle;c->drive.brake=p->brake;
}
static int available(const char *path) {
    FILE *existing=vsl_fopen(path,"rb");
    if (existing) { fclose(existing);fprintf(stderr,"refusing existing output: %s\n",path);return 0; }
    return 1;
}
static int run(int argc,char **argv) {
    const SdProfile *models[2]={&low,&high};
    AdConfig config={&bank,48271,VSL_V10,2,1.0/120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl control={{0},{.5,1,0,1,0,0,0,0}};
    AdCapture capture={raw,dna,events,dry,objects,trace};
    VslParams params=vsl_default_params(VSL_V10);
    VslWavWriter writers[FILES]={{0}};
    float *buffers[5]={output,raw,dna,dry,events};
    const char *suffix[5]={"render","dna_raw","dna","dry","event_layer"};
    char paths[FILES][4096],csv_path[4096],json_path[4096];
    FILE *csv=NULL,*report=NULL;
    double seconds=30,peak=0,total_time=0,max_block=0;
    unsigned align=32,frames,at=0,below=0,within=0,above=0,budget_exceeded=0;
    int i,ok=0,scenario=VSL_SCENARIO_AUTO;
    if (argc<4) {
        fputs("usage: VslAtlasDrive_probe LOWER.model UPPER.model OUTPUT_PREFIX [--scenario auto|neutral|shifts|downshift|lift|fixed --seconds30 --channels2|12 --events0..1 --detail1 --gain.5 --spatial0|1 --room0..1 --alignment0..32 --rpm7600 --load.8]\n",stderr);
        return 1;
    }
    for (i=4;i<argc;i+=2) {
        double x;const char *name=argv[i],*arg;
        if (i+1==argc) return 1;arg=argv[i+1];
        if (!strcmp(name,"--scenario")) { scenario=vsl_scenario_id(arg);if(scenario<0)return 1;continue; }
        if (!number(arg,&x)) return 1;
        if (!strcmp(name,"--seconds")) seconds=x;
        else if (!strcmp(name,"--channels")) { if(x!=2&&x!=12)return 1;config.channels=(int)x; }
        else if (!strcmp(name,"--events")) control.mix.event_gain=x;
        else if (!strcmp(name,"--detail")) control.mix.detail=x;
        else if (!strcmp(name,"--gain")) control.mix.gain=x;
        else if (!strcmp(name,"--room")) control.mix.room=x;
        else if (!strcmp(name,"--spatial")) { if(x!=0&&x!=1)return 1;control.mix.spatial=(int)x; }
        else if (!strcmp(name,"--alignment")) { if(x<0||x>32||x!=floor(x))return 1;align=(unsigned)x; }
        else if (!strcmp(name,"--rpm")) params.rpm=x;
        else if (!strcmp(name,"--load")) params.load=x;
        else return 1;
    }
    if (config.channels==12) control.mix.spatial=1;
    params.ignition=1;params.start_id=1;
    if (seconds<=0||seconds>60||!sd_profile_load(argv[1],&low)||!sd_profile_load(argv[2],&high)||
        !sa_bank_init(&bank,models,2,align)) return 2;
    vsl_scenario_apply(scenario,0,&params);inputs(&control,&params);
    if (!ad_render_init(&render,&engine,&config,&control)) return 2;
    /* Check every output before opening any, to preserve previous experiments. */
    for (i=0;i<FILES;++i) {
        const char *name=i<5?suffix[i]:vsl_object_info(i-5)->name;
        int length=snprintf(paths[i],sizeof paths[i],"%s_%s.wav",argv[3],name);
        if (length<0||length>=(int)sizeof paths[i]||!available(paths[i])) return 3;
        { int previous;for(previous=0;previous<i;++previous) if(!strcmp(paths[i],paths[previous]))return 3; }
    }
    if (snprintf(csv_path,sizeof csv_path,"%s_trace.csv",argv[3])>=(int)sizeof csv_path||
        snprintf(json_path,sizeof json_path,"%s_report.json",argv[3])>=(int)sizeof json_path||
        !available(csv_path)||!available(json_path)) return 3;
    for (i=0;i<FILES;++i) if (!vsl_wav_begin_float(&writers[i],paths[i],48000,
        i==0?(unsigned)config.channels:i<4?2u:1u)) goto done;
    csv=vsl_fopen(csv_path,"wb");if (!csv) goto done;
    fputs("frame,seconds,rpm,speed_kph,load,root_hz,lower,upper,blend,coverage,envelope,gear,lifecycle,operating,shifts,overruns,hits\n",csv);
    frames=(unsigned)(seconds*48000+.5);
    while (at<frames) {
        unsigned n=frames-at,j,c;double start,elapsed;
        if (n>BLOCK) n=BLOCK;
        vsl_scenario_apply(scenario,at/48000.,&params);inputs(&control,&params);
        if (!ad_render_set(&render,&control)) goto done;
        start=timer();if(!ad_render_process(&render,output,n,&capture))goto done;elapsed=timer()-start;
        total_time+=elapsed;max_block=fmax(max_block,elapsed);
        if (elapsed>n/48000.) ++budget_exceeded;
        for (j=0;j<n*(unsigned)config.channels;++j) {
            if (!isfinite(output[j])) goto done;
            peak=fmax(peak,fabs(output[j]));
        }
        for (i=0;i<5;++i) if (!vsl_wav_write(&writers[i],buffers[i],n)) goto done;
        for (c=0;c<VSL_OBJECTS;++c) {
            for (j=0;j<n;++j) mono[j]=objects[j*VSL_OBJECTS+c];
            if (!vsl_wav_write(&writers[c+5],mono,n)) goto done;
        }
        for (j=0;j<n;++j) {
            const AdTelemetry *t=&trace[j];
            if (t->coverage<0) ++below;else if(t->coverage>0)++above;else++within;
            if (t->frame%240==0) fprintf(csv,"%llu,%.6f,%.12g,%.12g,%.12g,%.12g,%u,%u,%.12g,%d,%.12g,%d,%d,%d,%u,%u,%u\n",
                (unsigned long long)t->frame,t->frame/48000.,t->rpm,t->speed,t->load,t->root_hz,t->lower,t->upper,t->blend,t->coverage,
                t->envelope,t->gear,t->lifecycle,t->operating,t->shifts,t->overruns,t->hits);
        }
        at+=n;
    }
    if (ferror(csv)) goto done;
    report=vsl_fopen(json_path,"wb");if(!report)goto done;
    fprintf(report,"{\n  \"schema\":\"vsl.atlas-drive-probe/1\",\n  \"frames\":%u,\"channels\":%d,\"seed\":48271,\"scenario\":%d,\n"
        "  \"source_frame\":%llu,\"owner_frame\":%llu,\"peak\":%.12g,\n"
        "  \"root_per_rpm\":%.17g,\"base_hz\":[%.17g,%.17g],\"cycle_offsets\":[%.17g,%.17g],\n"
        "  \"below_frames\":%u,\"covered_frames\":%u,\"above_frames\":%u,\n"
        "  \"shifts\":%u,\"overruns\":%u,\"procedural_hits\":%u,\"event_gain\":%.12g,\n"
        "  \"process_seconds\":%.9g,\"max_block_seconds\":%.9g,\"block_budget_seconds\":0.005,\n"
        "  \"block_budget_exceedances\":%u,\n"
        "  \"accepted\":false,\"limits\":\"Two nearby high-RPM cabin anchors; boundary timbre outside; no independent cabin LF/intake/noise; optional events reuse legacy procedural synth; no source playback or old DNA\"\n}\n",
        frames,config.channels,scenario,(unsigned long long)render.dna.frame,(unsigned long long)engine.frame,peak,config.root_per_rpm,
        low.base_hz,high.base_hz,bank.offset[0],bank.offset[1],below,within,above,engine.drive.shift_events,
        engine.drive.overrun_events,engine.events.hits,control.mix.event_gain,total_time,max_block,budget_exceeded);
    if (ferror(report)) goto done;
    printf("frames%u peak%.8g shifts%u coverage%.2f%% process%.3fs max%.3fms\n",frames,peak,engine.drive.shift_events,
        100.*within/frames,total_time,1000*max_block);ok=1;
done:
    for (i=0;i<FILES;++i) if(writers[i].file&&!vsl_wav_end(&writers[i]))ok=0;
    if(csv&&fclose(csv))ok=0;if(report&&fclose(report))ok=0;
    return ok?0:3;
}
#ifdef _WIN32
int wmain(int argc,wchar_t **wide) {
    char **args=calloc((size_t)argc,sizeof *args);int i,result=2;
    if(!args)return 2;
    for(i=0;i<argc;++i) {
        int length=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!length||!(args[i]=malloc((size_t)length))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],length,NULL,NULL))goto done;
    }
    result=run(argc,args);
done:
    for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
#else
int main(int argc,char **argv) { return run(argc,argv); }
#endif
