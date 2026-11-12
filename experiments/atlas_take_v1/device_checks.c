#define _CRT_SECURE_NO_WARNINGS
#include "../atlas_monitor_v1/audio.h"
#include "../atlas_monitor_v1/models.h"
#include "atlas_take_io/file.h"
#include "io/file.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static AmModels models;static SaBank bank;static AmAudio audio;
typedef struct {unsigned calls,committed;uint64_t hash;} SubmissionCheck;
static int bad_output(void *context,float *pcm,unsigned frames,int stopping) {
    SubmissionCheck *s=context;unsigned i;(void)stopping;
    for(i=0;i<frames*2;++i)pcm[i]=s->calls?INFINITY:.02f;++s->calls;return 0;
}
static void count_submission(void *context,unsigned frames,uint64_t hash) {
    SubmissionCheck *s=context;s->committed+=frames;s->hash=hash;
}
static int rejected_block(void) {
    SubmissionCheck check={0};WoDevice device;WoStats stats;ULONGLONG deadline;
    float first[1024];unsigned i;
    wo_init(&device,bad_output,&check);device.submitted=count_submission;
    if(!wo_start(&device,1,0)){wo_destroy(&device);return 0;}
    deadline=GetTickCount64()+4000;
    while(InterlockedCompareExchange(&device.running,0,0)&&GetTickCount64()<deadline)Sleep(5);
    wo_stop(&device);stats=wo_stats(&device);wo_destroy(&device);
    for(i=0;i<1024;++i)first[i]=.02f;
    return stats.error[0]&&stats.frames==512&&check.committed==512&&stats.output_hash==check.hash&&
        check.hash==at_hash_samples(AT_HASH_INITIAL,first,1024);
}
#define CHECK(x) do{if(!(x)){fprintf(stderr,"device take check line%d: %s\n",__LINE__,#x);ok=0;goto done;}}while(0)
static int wait_end(unsigned timeout) {
    ULONGLONG deadline=GetTickCount64()+timeout;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline)Sleep(5);
    return !InterlockedCompareExchange(&audio.device.running,0,0);
}
static int run(const char *path,AdSceneMode scene_mode) {
    AtTake loaded={0};AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR,&models.residual};
    AdControl c=am_default_control();WoStats recorded={0},played={0},cancelled={0};uint64_t length,hash;int ok=1,stage=0,initialized=0;
    ULONGLONG deadline;FILE *report=NULL;char report_path[16384];
    config.scene_mode=scene_mode;
    CHECK(rejected_block());
    CHECK(am_models_load(&models,0)&&am_models_bank(&models,&bank));am_audio_init(&audio,&config);initialized=1;
    c.drive.mode=VSL_BENCH;c.drive.ignition=1;c.drive.start_id=1;c.drive.rpm=4000;c.mix.body_mix=.6;c.mix.residual_gain=.5;
    c.mix.intake_gain=.5;c.mix.mechanical_gain=.5;c.mix.air_gain=.5;c.mix.road_gain=.5;c.mix.wind_gain=.5;
    CHECK(am_audio_control(&audio,&c)&&am_audio_record(&audio,1,144123));
    deadline=GetTickCount64()+10000;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline) {
        WoStats s=wo_stats(&audio.device);
        if(!stage&&s.frames>=24000){c.drive.rpm=5800;c.mix.body_mix=1;c.mix.residual_gain=.8;c.mix.intake_gain=.8;c.mix.mechanical_gain=.2;CHECK(am_audio_control(&audio,&c));stage=1;}
        if(stage==1&&s.frames>=72000){c.mix.spatial=1;c.mix.room=.2;c.mix.body_mix=0;c.mix.air_gain=.1;c.mix.road_gain=1;c.mix.wind_gain=0;CHECK(am_audio_control(&audio,&c));stage=2;}
        Sleep(5);
    }
    CHECK(wait_end(1000));am_audio_stop(&audio);recorded=wo_stats(&audio.device);
    CHECK(audio.ready&&audio.take.frames==recorded.frames&&recorded.frames==144123&&!recorded.error[0]&&stage==2);
    CHECK(audio.take.audio_hash==recorded.output_hash&&at_take_save(&audio.take,path)&&at_take_load(&loaded,path));
    CHECK(loaded.assets->config.scene_mode==scene_mode);
    length=audio.take.frames;hash=audio.take.audio_hash;at_take_free(&audio.take);audio.take=loaded;memset(&loaded,0,sizeof loaded);
    memset(&models,0,sizeof models);memset(&bank,0,sizeof bank);
    CHECK(am_audio_replay(&audio,1)&&!am_audio_control(&audio,&c)&&wait_end(10000));am_audio_stop(&audio);played=wo_stats(&audio.device);
    CHECK(!played.error[0]&&played.frames==length&&played.output_hash==hash&&InterlockedCompareExchange(&audio.replay_result,0,0)==1);
    CHECK(am_audio_replay(&audio,1));deadline=GetTickCount64()+5000;
    while(wo_stats(&audio.device).frames<24000&&InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline)Sleep(5);
    am_audio_stop(&audio);cancelled=wo_stats(&audio.device);
    CHECK(!cancelled.error[0]&&cancelled.frames<length&&InterlockedCompareExchange(&audio.replay_result,0,0)==2&&audio.take.audio_hash==hash);
    CHECK(am_models_load(&models,1)&&am_models_bank(&models,&bank));c.drive.rpm=7600;
    CHECK(am_audio_control(&audio,&c)&&am_audio_record(&audio,1,0));deadline=GetTickCount64()+5000;
    while(wo_stats(&audio.device).frames<24000&&InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline)Sleep(5);
    am_audio_stop(&audio);CHECK(audio.ready&&audio.take.stop_frame<UINT64_MAX&&audio.render.release==480);
    CHECK(!at_take_load(&audio.take,"no-such-recording.vslrun")&&audio.ready&&am_audio_replay(&audio,1)&&wait_end(5000));am_audio_stop(&audio);
    CHECK(InterlockedCompareExchange(&audio.replay_result,0,0)==1);
    snprintf(report_path,sizeof report_path,"%s.json",path);report=vsl_fopen(report_path,"wb");CHECK(report);
    fprintf(report,"{\"schema\":\"vsl.atlas-take-device/1\",\"muted\":true,\"verified\":true,\"rejected_block_excluded\":true,\"frames\":%llu,\"record_hash\":\"%016llx\","
        "\"play_hash\":\"%016llx\",\"record_queue_empty\":%u,\"play_queue_empty\":%u,\"record_over_budget\":%u,\"play_over_budget\":%u,"
        "\"record_max_ms\":%.9g,\"play_max_ms\":%.9g,\"record_device_seconds\":%.9g,\"record_wall_seconds\":%.9g,"
        "\"play_device_seconds\":%.9g,\"play_wall_seconds\":%.9g,\"cancel_frames\":%llu,\"manual_stop_frames\":%llu,\"render_id\":\"%s\"}\n",
        (unsigned long long)length,(unsigned long long)hash,(unsigned long long)played.output_hash,recorded.queue_empty,played.queue_empty,
        recorded.budget_exceeded,played.budget_exceeded,recorded.render_ms_max,played.render_ms_max,recorded.device_seconds,recorded.playback_wall_seconds,
        played.device_seconds,played.playback_wall_seconds,(unsigned long long)cancelled.frames,(unsigned long long)audio.take.frames,at_render_id());
done:if(report&&fclose(report))ok=0;at_take_free(&loaded);if(initialized)am_audio_destroy(&audio);return ok?0:3;
}
int wmain(int argc,wchar_t **wide) {
    char path[16384];if((argc!=2&&argc!=3)||(argc==3&&wcscmp(wide[2],L"--stereo-bed"))||!WideCharToMultiByte(CP_UTF8,0,wide[1],-1,path,sizeof path,NULL,NULL))return 2;
    return run(path,argc==3?AD_SCENE_STEREO_BED:AD_SCENE_OBJECTS);
}
