#define _CRT_SECURE_NO_WARNINGS
#include "audio.h"
#include "models.h"
#include "io/file.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static AmModels models;static SaBank bank;static AmAudio audio;
static StProfile startup_profile;static int startup_enabled;
static CbProfile catch_profile;static int catch_enabled;
static int startup_detail_enabled;

static int replay(const WoStats *s) {
    AmRender *render=calloc(1,sizeof *render);VslEngine *engine=calloc(1,sizeof *engine);
    float pcm[1024];uint64_t at=0;unsigned event=0;int ok=0;
    if(!render||!engine||!audio.trace_count||!am_render_init(render,engine,&audio.config,&audio.trace[0].control))goto done;
    while(at<s->frames) {
        unsigned n=(unsigned)(s->frames-at);if(n>512)n=512;
        while(event<audio.trace_count&&audio.trace[event].frame==at)
            if(!am_render_set(render,&audio.trace[event++].control))goto done;
        if(!am_render_process(render,pcm,n,at>=audio.stop_frame,NULL)||memcmp(pcm,audio.capture+2*at,n*2*sizeof(float)))goto done;
        at+=n;
    }
    ok=event==audio.trace_count;
done:free(render);free(engine);return ok;
}
static int healthy(const WoStats *s) {
    return s->opened&&!s->error[0]&&!s->queue_empty&&s->frames&&s->peak<.95&&
        fabs(s->device_seconds-s->frames/48000.)<.06&&
        fabs(s->playback_wall_seconds-s->frames/48000.)<.15&&!audio.trace_overflow;
}
static int save(const char *root,const char *name,const WoStats *s,int equal) {
    char path[4096];FILE *f;VslWavWriter wav={0};unsigned i;int ok;
    snprintf(path,sizeof path,"%s/%s.wav",root,name);
    if(!vsl_wav_begin_float(&wav,path,48000,2))return 0;
    ok=vsl_wav_write(&wav,audio.capture,(unsigned)s->frames);if(!vsl_wav_end(&wav))ok=0;
    snprintf(path,sizeof path,"%s/%s.json",root,name);f=vsl_fopen(path,"wb");if(!f)return 0;
    fprintf(f,"{\"schema\":\"vsl.atlas-device-evidence/1\",\"muted\":true,\"healthy\":%s,\"offline_float_equal\":%s,"
        "\"frames\":%llu,\"blocks\":%u,\"queue_empty\":%u,\"budget_exceeded\":%u,\"render_mean_ms\":%.9g,\"render_max_ms\":%.9g,"
        "\"device_seconds\":%.9g,\"playback_wall_seconds\":%.9g,\"startup_seconds\":%.9g,\"peak\":%.9g,\"stop_frame\":%llu,"
        "\"shifts\":%u,\"overruns\":%u,\"trace_overflow\":%u,\"controls\":[",
        healthy(s)?"true":"false",equal?"true":"false",(unsigned long long)s->frames,s->blocks,s->queue_empty,s->budget_exceeded,
        s->render_ms_total/fmax(1,s->blocks),s->render_ms_max,s->device_seconds,s->playback_wall_seconds,s->startup_seconds,s->peak,
        (unsigned long long)audio.stop_frame,audio.engine.drive.shift_events,audio.engine.drive.overrun_events,audio.trace_overflow);
    for(i=0;i<audio.trace_count;++i) {
        const AdControl *c=&audio.trace[i].control;
        fprintf(f,"%s{\"frame\":%llu,\"mode\":%d,\"ignition\":%d,\"start_id\":%d,\"gear\":%d,\"automatic\":%d,\"backfire\":%d,"
            "\"rpm\":%.17g,\"load\":%.17g,\"throttle\":%.17g,\"brake\":%.17g,\"gain\":%.17g,\"detail\":%.17g,\"event_gain\":%.17g,"
            "\"width\":%.17g,\"room\":%.17g,\"perspective\":%.17g,\"spatial\":%d,\"propagation\":%d,\"residual_gain\":%.17g,\"body_mix\":%.17g,"
            "\"intake_gain\":%.17g,\"mechanical_gain\":%.17g,\"air_gain\":%.17g,\"road_gain\":%.17g,\"wind_gain\":%.17g,\"startup_gain\":%.17g,\"catch_gain\":%.17g}",i?",":"",
            (unsigned long long)audio.trace[i].frame,c->drive.mode,c->drive.ignition,c->drive.start_id,c->drive.gear,c->drive.automatic,c->drive.backfire,
            c->drive.rpm,c->drive.load,c->drive.throttle,c->drive.brake,c->mix.gain,c->mix.detail,c->mix.event_gain,c->mix.width,c->mix.room,
            c->mix.perspective,c->mix.spatial,c->mix.propagation,c->mix.residual_gain,c->mix.body_mix,
            c->mix.intake_gain,c->mix.mechanical_gain,c->mix.air_gain,c->mix.road_gain,c->mix.wind_gain,c->mix.startup_gain,c->mix.catch_gain);
    }
    fputs("]}\n",f);ok&=!ferror(f);if(fclose(f))ok=0;return ok;
}
static int finite_run(const char *out,const char *name,int pedals) {
    AdControl c=am_default_control();uint64_t limit=(pedals?12u:6u)*48000;
    ULONGLONG deadline;int stage=0,equal;WoStats s;
    c.drive.ignition=1;c.drive.start_id=1;
    if(startup_enabled)c.mix.startup_gain=.5;
    if(catch_enabled)c.mix.catch_gain=.7;
    c.mix.residual_gain=.5;c.mix.body_mix=.6;
    if(!audio.config.residual_bank)c.mix.residual_gain=0;
    if(!pedals){c.drive.mode=VSL_BENCH;c.drive.automatic=0;c.drive.rpm=3600;}
    if(!am_audio_control(&audio,&c)||!am_audio_start(&audio,1,limit))return 0;
    deadline=GetTickCount64()+20000;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline) {
        WoStats now=wo_stats(&audio.device);
        if(now.frames>=48000&&stage==0){c.drive.throttle=.85;c.drive.rpm=5700;stage=1;}
        else if(now.frames>=3*48000&&stage==1){c.mix.spatial=1;c.mix.room=.25;c.mix.residual_gain=.8;c.mix.body_mix=1;stage=2;}
        else if(now.frames>=4*48000&&stage==2){c.mix.width=.25;c.drive.rpm=7200;c.mix.residual_gain=.35;c.mix.body_mix=0;stage=3;}
        else if(pedals&&now.frames>=5*48000&&stage==3){c.drive.throttle=0;stage=4;}
        else if(pedals&&now.frames>=6*48000&&stage==4){c.drive.brake=.45;stage=5;}
        else if(pedals&&now.frames>=7*48000&&stage==5){c.drive.brake=0;c.drive.throttle=.7;stage=6;}
        else if(pedals&&now.frames>=9*48000&&stage==6){c.drive.ignition=0;c.drive.throttle=0;stage=7;}
        else {Sleep(5);continue;}
        if(!audio.config.residual_bank)c.mix.residual_gain=0;
        if(!am_audio_control(&audio,&c)){am_audio_stop(&audio);return 0;}
    }
    am_audio_stop(&audio);s=wo_stats(&audio.device);equal=replay(&s);
    printf("%s frames%llu queue%u max%.3fms replay%d\n",name,(unsigned long long)s.frames,s.queue_empty,s.render_ms_max,equal);
    return save(out,name,&s,equal)&&healthy(&s)&&equal&&s.frames==limit&&stage==(pedals?7:3)&&(!pedals||audio.engine.drive.shift_events>1);
}
static int run(int argc,char **argv) {
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR,&models.residual};
    WoStats s;AdControl c;ULONGLONG deadline;int ok,equal;
    {int i;for(i=2;i<argc;++i)if(!strcmp(argv[i],"--stereo-bed"))config.scene_mode=AD_SCENE_STEREO_BED;
        else if(!strcmp(argv[i],"--startup"))startup_enabled=1;
        else if(!strcmp(argv[i],"--catch")){catch_enabled=1;startup_enabled=1;}
        else if(!strcmp(argv[i],"--startup-detail")){startup_detail_enabled=1;catch_enabled=1;startup_enabled=1;}else return 2;}
    if(argc<2||!am_models_load_variant(&models,catch_enabled?2:startup_enabled?1:0,startup_detail_enabled)||!am_models_bank(&models,&bank))return 2;
    if(startup_enabled){if(!am_startup_load(&startup_profile))return 2;config.startup_profile=&startup_profile;}
    if(catch_enabled) {
        if(!am_catch_load(&catch_profile))return 2;config.catch_profile=&catch_profile;
        config.residual_bank=startup_detail_enabled?&models.residual:NULL;
        config.root_per_rpm=models.profile[0].base_hz/vsl_profile(VSL_V10)->idle_rpm;
    }
    am_audio_init(&audio,&config);audio.capture_frames=13*48000;audio.capture=calloc(audio.capture_frames*2,sizeof(float));
    if(!audio.capture){am_audio_destroy(&audio);return 2;}
    ok=finite_run(argv[1],"bench",0);ok&=finite_run(argv[1],"pedals",1);
    c=am_default_control();c.drive.ignition=1;c.drive.start_id=1;
    if(catch_enabled){c.mix.catch_gain=.7;c.mix.startup_gain=.5;}
    if(!am_audio_control(&audio,&c)||!am_audio_start(&audio,1,0)){ok=0;goto done;}
    deadline=GetTickCount64()+5000;
    while(wo_stats(&audio.device).frames<24000&&InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline)Sleep(5);
    am_audio_stop(&audio);s=wo_stats(&audio.device);equal=replay(&s);
    ok&=save(argv[1],"stopped",&s,equal)&&healthy(&s)&&equal&&audio.render.release==480;
    if(!am_models_load_variant(&models,catch_enabled?2:1,startup_detail_enabled)||!am_models_bank(&models,&bank)){ok=0;goto done;}
    c.drive.mode=VSL_BENCH;c.drive.rpm=7600;c.mix.residual_gain=.5;c.mix.body_mix=1;
    if(!audio.config.residual_bank)c.mix.residual_gain=0;
    if(!am_audio_control(&audio,&c)||!am_audio_start(&audio,1,48000)){ok=0;goto done;}
    deadline=GetTickCount64()+5000;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline)Sleep(5);
    am_audio_stop(&audio);s=wo_stats(&audio.device);equal=replay(&s);
    ok&=save(argv[1],"cabin_restart",&s,equal)&&healthy(&s)&&equal&&s.frames==48000;
    audio.config.channels=12;ok&=!am_audio_start(&audio,1,48000);audio.config.channels=2;
done:
    am_audio_stop(&audio);free(audio.capture);am_audio_destroy(&audio);
    puts(ok?"PASS: atlas muted device, control adoption replay, transport and context switch":"FAIL: inspect saved device evidence");
    return ok?0:3;
}
int wmain(int argc,wchar_t **wide) {
    char **args=calloc((size_t)argc,sizeof *args);int i,result=2;
    if(!args)return 2;
    for(i=0;i<argc;++i) {
        int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!n||!(args[i]=malloc((size_t)n))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL))goto done;
    }
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
