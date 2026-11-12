#define _CRT_SECURE_NO_WARNINGS
#include "../atlas_monitor_v1/audio.h"
#include "../atlas_monitor_v1/models.h"
#include "resonant_detail_io/profile.h"
#include "atlas_take_io/file.h"
#include "io/wav.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static AmModels models;static SaBank bank;static DrsBank detail;static RdtProfile profile;static AmAudio audio;
#define CHECK(x) do{if(!(x)){fprintf(stderr,"resonant device line%d: %s\n",__LINE__,#x);ok=0;goto done;}}while(0)
static int wait_end(unsigned ms) {
    ULONGLONG deadline=GetTickCount64()+ms;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline)Sleep(5);
    return !InterlockedCompareExchange(&audio.device.running,0,0);
}
static int healthy(const WoStats *s) {
    return s->opened&&!s->error[0]&&s->frames&&!s->queue_empty&&s->peak<.95&&
        fabs(s->device_seconds-s->frames/48000.)<.06&&fabs(s->playback_wall_seconds-s->frames/48000.)<.15;
}
static int run(const char *root) {
    AdConfig cfg={0};AdControl c;AtTake loaded={0};WoStats recorded={0},played={0},cancelled={0};
    const RdtProfile *profiles[SA_MAX_ANCHORS]={&profile};int initialized=0,ok=1,stage=0,active=0,inactive=0;
    ULONGLONG deadline;char path[4096];FILE *report=NULL;VslWavWriter wav={0};
    CHECK(am_models_load(&models,0)&&am_models_bank(&models,&bank));
    CHECK(rdt_profile_load("voices/resonant_detail_c_v1/idle_add.rdetail",&profile)&&drs_bank_init(&detail,&bank,profiles));
    cfg.bank=&bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=2;cfg.root_per_rpm=1./120;
    cfg.scene_mode=AD_SCENE_STEREO_BED;cfg.resonant_bank=&detail;
    am_audio_init(&audio,&cfg);initialized=1;audio.capture_frames=4*48000;audio.capture=calloc(audio.capture_frames*2,sizeof(float));CHECK(audio.capture);
    c=am_default_control();c.drive.mode=VSL_BENCH;c.drive.ignition=1;c.drive.start_id=1;c.drive.automatic=0;
    c.drive.rpm=profile.base_hz*120;c.mix.width=1;c.mix.resonant_gain=.7;
    CHECK(am_audio_control(&audio,&c)&&am_audio_record(&audio,1,144123));deadline=GetTickCount64()+10000;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline) {
        WoStats s=wo_stats(&audio.device);AdTelemetry t=am_audio_latest(&audio);
        if(t.resonant_support>.5)active=1;if(s.frames>60000&&t.resonant_support==0)inactive=1;
        if(stage==0&&s.frames>=24000){c.drive.rpm=1300;c.mix.resonant_gain=1;CHECK(am_audio_control(&audio,&c));stage=1;}
        else if(stage==1&&s.frames>=48000){c.drive.rpm=6000;CHECK(am_audio_control(&audio,&c));stage=2;}
        else if(stage==2&&s.frames>=72000){c.drive.rpm=profile.base_hz*120;c.mix.resonant_gain=.4;CHECK(am_audio_control(&audio,&c));stage=3;}
        Sleep(5);
    }
    CHECK(wait_end(1000));am_audio_stop(&audio);recorded=wo_stats(&audio.device);
    CHECK(stage==3&&active&&inactive&&audio.ready&&recorded.frames==144123&&healthy(&recorded));
    snprintf(path,sizeof path,"%s/recorded.wav",root);CHECK(vsl_wav_begin_float(&wav,path,48000,2));
    CHECK(vsl_wav_write(&wav,audio.capture,(unsigned)recorded.frames)&&vsl_wav_end(&wav));
    snprintf(path,sizeof path,"%s/detail_schema6.vslrun",root);CHECK(at_take_save(&audio.take,path)&&at_take_load(&loaded,path));
    CHECK(loaded.assets->config.resonant_bank==&loaded.assets->resonant&&loaded.assets->resonant.enabled[0]);
    at_take_free(&audio.take);audio.take=loaded;memset(&loaded,0,sizeof loaded);
    memset(&models,0,sizeof models);memset(&bank,0,sizeof bank);memset(&profile,0,sizeof profile);memset(&detail,0,sizeof detail);
    CHECK(am_audio_replay(&audio,1)&&!am_audio_control(&audio,&c)&&wait_end(10000));am_audio_stop(&audio);played=wo_stats(&audio.device);
    CHECK(healthy(&played)&&played.frames==recorded.frames&&played.output_hash==recorded.output_hash&&audio.replay_result==1);
    CHECK(am_audio_replay(&audio,1));deadline=GetTickCount64()+5000;
    while(wo_stats(&audio.device).frames<24000&&audio.device.running&&GetTickCount64()<deadline)Sleep(5);
    am_audio_stop(&audio);cancelled=wo_stats(&audio.device);CHECK(healthy(&cancelled)&&cancelled.frames<recorded.frames&&audio.replay_result==2);
    snprintf(path,sizeof path,"%s/device.json",root);report=vsl_fopen(path,"wb");CHECK(report);
    fprintf(report,"{\"result\":\"pass\",\"muted\":true,\"schema\":6,\"fields\":28,\"frames\":%llu,\"owned_models_destroyed_before_replay\":true,"
        "\"record_hash\":\"%016llx\",\"play_hash\":\"%016llx\",\"record_queue_empty\":%u,\"play_queue_empty\":%u,"
        "\"record_budget_exceeded\":%u,\"play_budget_exceeded\":%u,\"record_max_ms\":%.9g,\"play_max_ms\":%.9g,"
        "\"active_and_missing_support_observed\":true,\"cancel_frames\":%llu,\"controls\":[",
        (unsigned long long)recorded.frames,(unsigned long long)recorded.output_hash,(unsigned long long)played.output_hash,
        recorded.queue_empty,played.queue_empty,recorded.budget_exceeded,played.budget_exceeded,recorded.render_ms_max,played.render_ms_max,
        (unsigned long long)cancelled.frames);
    for(unsigned i=0;i<audio.trace_count;++i)fprintf(report,"%s{\"frame\":%llu,\"rpm\":%.17g,\"resonant_gain\":%.17g}",i?",":"",
        (unsigned long long)audio.trace[i].frame,audio.trace[i].control.drive.rpm,audio.trace[i].control.mix.resonant_gain);
    fputs("]}\n",report);
    puts("PASS: one-driver local detail, owned schema6 muted device replay and cancellation");
done:
    if(wav.file)vsl_wav_end(&wav);if(report&&fclose(report))ok=0;at_take_free(&loaded);
    if(initialized){am_audio_stop(&audio);free(audio.capture);audio.capture=NULL;am_audio_destroy(&audio);}return ok?0:3;
}
int wmain(int argc,wchar_t **argv) {
    char root[4096];if(argc!=2||!WideCharToMultiByte(CP_UTF8,0,argv[1],-1,root,sizeof root,NULL,NULL))return 2;return run(root);
}
