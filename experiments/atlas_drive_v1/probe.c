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
#define AUDIO_FILES 10
#define RAW_AUX_FILES 6
#define FILES (AUDIO_FILES+VSL_OBJECTS+RAW_AUX_FILES)
static const int aux_source[RAW_AUX_FILES]={VSL_INTAKE,VSL_MECHANICAL,VSL_AIR_L,VSL_AIR_R,VSL_ROAD,VSL_WIND};
static const char *aux_name[RAW_AUX_FILES]={"aux_raw_intake","aux_raw_mechanical","aux_raw_air_left","aux_raw_air_right","aux_raw_road","aux_raw_wind"};
static SdProfile profiles[SA_MAX_ANCHORS];
static SaBank bank;
static RaBank residual_bank;static SrProfile residual_profiles[SA_MAX_ANCHORS];
static AdRender render;
static VslEngine engine;
static float output[BLOCK*12],raw[BLOCK*2],dna[BLOCK*2],dry[BLOCK*2],events[BLOCK],objects[BLOCK*VSL_OBJECTS],mono[BLOCK];
static float residual_raw[BLOCK*2],residual[BLOCK*2];
static float body_raw[BLOCK*2],body[BLOCK*2];
static float aux[BLOCK*2],aux_raw[BLOCK*VSL_OBJECTS],aux_objects[BLOCK*VSL_OBJECTS];
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
    const SdProfile *models[SA_MAX_ANCHORS]={0};
    const char *model_paths[SA_MAX_ANCHORS]={0};
    const char *residual_paths[SA_MAX_ANCHORS]={0};unsigned residual_count=0;
    AdConfig config={&bank,48271,VSL_V10,2,1.0/120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl control={{0},{.5,1,0,1,0,0,0,0}};
    AdCapture capture={raw,dna,events,dry,objects,trace};
    VslParams params=vsl_default_params(VSL_V10);
    VslWavWriter writers[FILES]={{0}};
    float *buffers[AUDIO_FILES]={output,raw,dna,dry,events,residual_raw,residual,body_raw,body,aux};
    const char *suffix[AUDIO_FILES]={"render","dna_raw","dna","dry","event_layer","residual_raw","residual","harmonic_body_raw","harmonic_body","auxiliary"};
    char paths[FILES][4096],csv_path[4096],json_path[4096];
    FILE *csv=NULL,*report=NULL;
    double seconds=30,peak=0,total_time=0,max_block=0;
    unsigned align=32,frames,at=0,below=0,within=0,above=0,budget_exceeded=0,count=2,a;
    int i,ok=0,scenario=VSL_SCENARIO_AUTO;
    if (argc<4) {
        fputs("usage: VslAtlasDrive_probe FIRST.model SECOND.model OUTPUT_PREFIX [--anchor NEXT.model (up to8 total, sorted root Hz) --residual-anchor FILE.residual (one per DNA anchor) --residual-gain 0..1 --body-mix 0..1 --intake 0..1 --mechanical 0..1 --air 0..1 --road 0..1 --wind 0..1 --scenario auto|neutral|shifts|downshift|lift|fixed --seconds 30 --channels 2|12 --events 0..1 --detail 1 --gain .5 --spatial 0|1 --room 0..1 --alignment 0..32 --rpm 7600 --load .8 --root-per-rpm .008333333333333333]\n",stderr);
        return 1;
    }
    model_paths[0]=argv[1];model_paths[1]=argv[2];
    for (i=4;i<argc;i+=2) {
        double x;const char *name=argv[i],*arg;
        if (i+1==argc) return 1;arg=argv[i+1];
        if (!strcmp(name,"--scenario")) { scenario=vsl_scenario_id(arg);if(scenario<0)return 1;continue; }
        if (!strcmp(name,"--anchor")) { if(count==SA_MAX_ANCHORS)return 1;model_paths[count++]=arg;continue; }
        if (!strcmp(name,"--residual-anchor")) {if(residual_count==SA_MAX_ANCHORS)return 1;residual_paths[residual_count++]=arg;continue;}
        if (!number(arg,&x)) return 1;
        if (!strcmp(name,"--seconds")) seconds=x;
        else if (!strcmp(name,"--channels")) { if(x!=2&&x!=12)return 1;config.channels=(int)x; }
        else if (!strcmp(name,"--events")) control.mix.event_gain=x;
        else if (!strcmp(name,"--detail")) control.mix.detail=x;
        else if (!strcmp(name,"--gain")) control.mix.gain=x;
        else if (!strcmp(name,"--room")) control.mix.room=x;
        else if (!strcmp(name,"--spatial")) { if(x!=0&&x!=1)return 1;control.mix.spatial=(int)x; }
        else if (!strcmp(name,"--stereo-bed")) { if(x!=0&&x!=1)return 1;config.scene_mode=(AdSceneMode)(int)x; }
        else if (!strcmp(name,"--alignment")) { if(x<0||x>32||x!=floor(x))return 1;align=(unsigned)x; }
        else if (!strcmp(name,"--rpm")) params.rpm=x;
        else if (!strcmp(name,"--load")) params.load=x;
        else if (!strcmp(name,"--root-per-rpm")) config.root_per_rpm=x;
        else if (!strcmp(name,"--residual-gain")) control.mix.residual_gain=x;
        else if (!strcmp(name,"--body-mix")) control.mix.body_mix=x;
        else if (!strcmp(name,"--intake")) control.mix.intake_gain=x;
        else if (!strcmp(name,"--mechanical")) control.mix.mechanical_gain=x;
        else if (!strcmp(name,"--air")) control.mix.air_gain=x;
        else if (!strcmp(name,"--road")) control.mix.road_gain=x;
        else if (!strcmp(name,"--wind")) control.mix.wind_gain=x;
        else return 1;
    }
    if (config.channels==12) control.mix.spatial=1;
    params.ignition=1;params.start_id=1;
    if (seconds<=0||seconds>60) return 2;
    for(a=0;a<count;++a) { if(!sd_profile_load(model_paths[a],&profiles[a]))return 2;models[a]=&profiles[a]; }
    if (!sa_bank_init(&bank,models,count,align)) return 2;
    if(residual_count) {
        const SrProfile *rp[SA_MAX_ANCHORS];double roots[SA_MAX_ANCHORS];
        if(residual_count!=count)return 2;
        for(a=0;a<count;++a) {
            FILE *f=vsl_fopen(residual_paths[a],"rb");int read_ok;if(!f)return 2;
            read_ok=sr_profile_read(f,&residual_profiles[a]);if(fclose(f))read_ok=0;if(!read_ok)return 2;
            rp[a]=&residual_profiles[a];roots[a]=profiles[a].base_hz;
        }
        if(!ra_bank_init(&residual_bank,rp,roots,count))return 2;config.residual_bank=&residual_bank;
    }
    capture.residual_raw=residual_raw;capture.residual=residual;
    capture.body_raw=body_raw;capture.body=body;
    capture.aux=aux;capture.aux_raw=aux_raw;capture.aux_objects=aux_objects;
    vsl_scenario_apply(scenario,0,&params);inputs(&control,&params);
    if (!ad_render_init(&render,&engine,&config,&control)) return 2;
    /* Check every output before opening any, to preserve previous experiments. */
    for (i=0;i<FILES;++i) {
        const char *name=i<AUDIO_FILES?suffix[i]:i<AUDIO_FILES+VSL_OBJECTS?vsl_object_info(i-AUDIO_FILES)->name:aux_name[i-AUDIO_FILES-VSL_OBJECTS];
        int length=snprintf(paths[i],sizeof paths[i],"%s_%s.wav",argv[3],name);
        if (length<0||length>=(int)sizeof paths[i]||!available(paths[i])) return 3;
        { int previous;for(previous=0;previous<i;++previous) if(!strcmp(paths[i],paths[previous]))return 3; }
    }
    if (snprintf(csv_path,sizeof csv_path,"%s_trace.csv",argv[3])>=(int)sizeof csv_path||
        snprintf(json_path,sizeof json_path,"%s_report.json",argv[3])>=(int)sizeof json_path||
        !available(csv_path)||!available(json_path)) return 3;
    for (i=0;i<FILES;++i) if (!vsl_wav_begin_float(&writers[i],paths[i],48000,
        i==0?(unsigned)config.channels:i==4?1u:i<AUDIO_FILES?2u:1u)) goto done;
    csv=vsl_fopen(csv_path,"wb");if (!csv) goto done;
    fputs("frame,seconds,rpm,speed_kph,load,root_hz,lower,upper,blend,coverage,envelope,gear,lifecycle,operating,shifts,overruns,hits,body_mix,body_envelope,auxiliary_rpm,firing,fuel_mode,rotating_strikes,fired_strikes\n",csv);
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
        for (i=0;i<AUDIO_FILES;++i) if (!vsl_wav_write(&writers[i],buffers[i],n)) goto done;
        for (c=0;c<VSL_OBJECTS;++c) {
            for (j=0;j<n;++j) mono[j]=objects[j*VSL_OBJECTS+c];
            if (!vsl_wav_write(&writers[c+AUDIO_FILES],mono,n)) goto done;
        }
        for(c=0;c<RAW_AUX_FILES;++c) {
            for(j=0;j<n;++j)mono[j]=aux_raw[j*VSL_OBJECTS+aux_source[c]];
            if(!vsl_wav_write(&writers[AUDIO_FILES+VSL_OBJECTS+c],mono,n))goto done;
        }
        for (j=0;j<n;++j) {
            const AdTelemetry *t=&trace[j];
            if (t->coverage<0) ++below;else if(t->coverage>0)++above;else++within;
            if (t->frame%240==0) fprintf(csv,"%llu,%.6f,%.12g,%.12g,%.12g,%.12g,%u,%u,%.12g,%d,%.12g,%d,%d,%d,%u,%u,%u,%.12g,%.12g,%.12g,%.12g,%d,%u,%u\n",
                (unsigned long long)t->frame,t->frame/48000.,t->rpm,t->speed,t->load,t->root_hz,t->lower,t->upper,t->blend,t->coverage,
                t->envelope,t->gear,t->lifecycle,t->operating,t->shifts,t->overruns,t->hits,t->body_mix,t->body_envelope,
                t->auxiliary_rpm,t->firing,t->fuel_mode,t->rotating_strikes,t->fired_strikes);
        }
        at+=n;
    }
    if (ferror(csv)) goto done;
    report=vsl_fopen(json_path,"wb");if(!report)goto done;
    fprintf(report,"{\n  \"schema\":\"vsl.atlas-drive-probe/1\",\n  \"frames\":%u,\"channels\":%d,\"seed\":48271,\"scenario\":%d,\n"
        "  \"source_frame\":%llu,\"owner_frame\":%llu,\"peak\":%.12g,\n"
        "  \"root_per_rpm\":%.17g,\"anchor_count\":%u,\"base_hz\":[",
        frames,config.channels,scenario,(unsigned long long)render.dna.frame,(unsigned long long)engine.frame,peak,config.root_per_rpm,count);
    for(a=0;a<count;++a)fprintf(report,"%s%.17g",a?",":"",profiles[a].base_hz);
    fputs("],\"cycle_offsets\":[",report);
    for(a=0;a<count;++a)fprintf(report,"%s%.17g",a?",":"",bank.offset[a]);
    fprintf(report,"],\n"
        "  \"below_frames\":%u,\"covered_frames\":%u,\"above_frames\":%u,\n"
        "  \"shifts\":%u,\"overruns\":%u,\"procedural_hits\":%u,\"event_gain\":%.12g,\n"
        "  \"process_seconds\":%.9g,\"max_block_seconds\":%.9g,\"block_budget_seconds\":0.005,\n"
        "  \"block_budget_exceedances\":%u,\n"
        "  \"residual_attached\":%s,\"residual_gain\":%.17g,\"body_mix\":%.17g,\n"
        "  \"auxiliary_amounts\":[%.17g,%.17g,%.17g,%.17g,%.17g],\n"
        "  \"accepted\":false,\"limits\":\"Caller-selected acoustic anchors and explicit root/RPM hypothesis; interval coverage does not prove measured load/state or gaps between anchors; optional residual atlas, complementary LF partition, legacy events and engineering auxiliary layers; no physical source separation or source playback\"\n}\n",
        below,within,above,engine.drive.shift_events,
        engine.drive.overrun_events,engine.events.hits,control.mix.event_gain,total_time,max_block,budget_exceeded,
        config.residual_bank?"true":"false",control.mix.residual_gain,control.mix.body_mix,
        control.mix.intake_gain,control.mix.mechanical_gain,control.mix.air_gain,control.mix.road_gain,control.mix.wind_gain);
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
