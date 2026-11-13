#define _CRT_SECURE_NO_WARNINGS
#include "models.h"
#include "../full_recipe_drive_v1/models.h"
#include "../atlas_monitor_v1/audio.h"
#include "atlas_take_io/file.h"
#include "io/file.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static FidModels idle;
static FrModels moving;
static AmAudio audio;
static AtPlayer player;
static VslEngine engine;
#define CHECK(x) do{if(!(x)){fprintf(stderr,"idle device line%d: %s\n",__LINE__,#x);ok=0;goto done;}}while(0)
static int wait_end(unsigned ms) {
    ULONGLONG deadline=GetTickCount64()+ms;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline)Sleep(5);
    return !InterlockedCompareExchange(&audio.device.running,0,0);
}
static int healthy(const WoStats *s) {
    return s->opened&&!s->error[0]&&s->frames&&!s->queue_empty&&s->peak<.95&&
        fabs(s->device_seconds-s->frames/48000.)<.06&&fabs(s->playback_wall_seconds-s->frames/48000.)<.15;
}
int wmain(int argc,wchar_t **argv) {
    AdConfig cfg={0};AdControl c;AtTake loaded={0};WoStats recorded={0},played={0},cancelled={0};
    char root[4096],path[4096];FILE *report=NULL;VslWavWriter wav={0};
    int ok=1,initialized=0,step=0,active=0,inactive=0;
    const uint64_t frames=UINT64_C(48000)*8+123;
    const uint64_t targets[]={72000,96000,168000,240000,288000,336000};
    ULONGLONG deadline;
    if(argc!=2||!WideCharToMultiByte(CP_UTF8,0,argv[1],-1,root,sizeof root,NULL,NULL))return 2;
    CHECK(fid_models_load(&idle)&&fr_models_load(&moving));
    cfg.bank=&moving.bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=2;cfg.root_per_rpm=1./120;
    cfg.scene_mode=AD_SCENE_STEREO_BED;cfg.resonant_bank=&moving.resonance;cfg.recipe_bank=&moving.recipe;cfg.fine_idle_profile=&idle.idle;
    am_audio_init(&audio,&cfg);initialized=1;audio.capture_frames=(size_t)frames+1024;
    audio.capture=calloc(audio.capture_frames*2,sizeof(float));CHECK(audio.capture);
    c=am_default_control();c.drive.mode=VSL_BENCH;c.drive.ignition=1;c.drive.start_id=1;c.drive.rpm=850;c.drive.load=0;
    c.mix.idle_motion=.5;c.mix.idle_detail=1;
    c.mix.width=c.mix.resonant_gain=c.mix.coherent_low_gain=c.mix.idle_mix=1;
    CHECK(am_audio_control(&audio,&c)&&am_audio_record(&audio,1,frames));deadline=GetTickCount64()+15000;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline) {
        WoStats s=wo_stats(&audio.device);AdTelemetry t=am_audio_latest(&audio);
        if(t.idle_weight>.99)active=1;if(s.frames>60000&&t.idle_weight==0)inactive=1;
        if(step<6&&s.frames>=targets[step]) {
            if(step==0){c.mix.idle_mix=.35;c.mix.idle_motion=1;c.mix.idle_detail=.5;}
            if(step==1){c.drive.rpm=2200;c.drive.load=.6;}
            if(step==2){c.drive.rpm=850;c.drive.load=0;}
            if(step==3)c.mix.idle_mix=0;
            if(step==4)c.mix.idle_mix=1;
            if(step==5)c.drive.ignition=0;
            CHECK(am_audio_control(&audio,&c));++step;
        }
        Sleep(5);
    }
    CHECK(wait_end(1000));am_audio_stop(&audio);recorded=wo_stats(&audio.device);
    CHECK(step==6&&active&&inactive&&audio.ready&&recorded.frames==frames&&healthy(&recorded));
    snprintf(path,sizeof path,"%s/recorded.wav",root);CHECK(vsl_wav_begin_float(&wav,path,48000,2));
    CHECK(vsl_wav_write(&wav,audio.capture,(unsigned)recorded.frames)&&vsl_wav_end(&wav));
    snprintf(path,sizeof path,"%s/fine_idle_schema10.vslrun",root);CHECK(at_take_save(&audio.take,path)&&at_take_load(&loaded,path));
    CHECK(loaded.assets->config.fine_idle_profile==&loaded.assets->fine_idle&&loaded.assets->fine_idle.modal==&loaded.assets->fine_modal);
    at_take_free(&audio.take);audio.take=loaded;memset(&loaded,0,sizeof loaded);
    memset(&idle,0,sizeof idle);memset(&moving,0,sizeof moving);
    CHECK(am_audio_replay(&audio,1)&&!am_audio_control(&audio,&c)&&wait_end(15000));am_audio_stop(&audio);played=wo_stats(&audio.device);
    CHECK(healthy(&played)&&played.frames==recorded.frames&&played.output_hash==recorded.output_hash&&audio.replay_result==1);
    CHECK(at_player_init(&player,&engine,&audio.take,12));
    {float pcm[512*12];uint64_t at=0;unsigned n;
        while(at<frames){n=frames-at>512?512:(unsigned)(frames-at);CHECK(at_player_process(&player,pcm,n,NULL)==n);
            for(unsigned j=0;j<n;++j){CHECK(pcm[j*12]==audio.capture[2*(at+j)]&&pcm[j*12+1]==audio.capture[2*(at+j)+1]);
                for(unsigned ch=2;ch<12;++ch)CHECK(pcm[j*12+ch]==0);}at+=n;}
        CHECK(at_player_verified(&player));}
    CHECK(am_audio_replay(&audio,1));deadline=GetTickCount64()+5000;
    while(wo_stats(&audio.device).frames<12000&&audio.device.running&&GetTickCount64()<deadline)Sleep(5);
    am_audio_stop(&audio);cancelled=wo_stats(&audio.device);CHECK(healthy(&cancelled)&&cancelled.frames<recorded.frames&&audio.replay_result==2);
    snprintf(path,sizeof path,"%s/device.json",root);report=vsl_fopen(path,"wb");CHECK(report);
    fprintf(report,"{\"result\":\"pass\",\"schema\":10,\"fields\":32,\"muted\":true,\"frames\":%llu,"
        "\"external_models_destroyed\":true,\"two_twelve_front_and_source_exact\":true,"
        "\"record_hash\":\"%016llx\",\"play_hash\":\"%016llx\",\"record_queue_empty\":%u,\"play_queue_empty\":%u,"
        "\"record_budget_exceeded\":%u,\"play_budget_exceeded\":%u,\"record_max_ms\":%.9g,\"play_max_ms\":%.9g,"
        "\"cancel_frames\":%llu,\"controls\":[",(unsigned long long)recorded.frames,
        (unsigned long long)recorded.output_hash,(unsigned long long)played.output_hash,recorded.queue_empty,played.queue_empty,
        recorded.budget_exceeded,played.budget_exceeded,recorded.render_ms_max,played.render_ms_max,(unsigned long long)cancelled.frames);
    for(unsigned i=0;i<audio.take.count;++i)fprintf(report,"%s{\"frame\":%llu,\"rpm_input\":%.17g,\"idle_mix\":%.17g,\"ignition\":%d}",i?",":"",
        (unsigned long long)audio.take.events[i].frame,audio.take.events[i].control.drive.rpm,audio.take.events[i].control.mix.idle_mix,audio.take.events[i].control.drive.ignition);
    fputs("],\"timbre_accepted\":false,\"native_UI_visual_or_interaction_verified\":false}\n",report);
    puts("PASS muted device8s, amount/state adopted frames, owned schema10 replay,2/12front/source and cancellation");
done:
    if(wav.file)vsl_wav_end(&wav);if(report&&fclose(report))ok=0;at_take_free(&loaded);
    at_player_dispose(&player);if(initialized){am_audio_stop(&audio);free(audio.capture);audio.capture=NULL;am_audio_destroy(&audio);}return ok?0:3;
}
