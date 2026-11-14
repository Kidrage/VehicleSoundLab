#define _CRT_SECURE_NO_WARNINGS
#include "../fine_idle_drive_v1/models.h"
#include "../full_recipe_drive_v1/models.h"
#include "../atlas_monitor_v1/audio.h"
#include "atlas_take_io/file.h"
#include "io/file.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static FidModels idle;static FrModels moving;static AmAudio audio;static AtPlayer portable;static VslEngine owner;
#define FRAMES 288123u
#define CHECK(x) do{if(!(x)){fprintf(stderr,"layer device%d: %s\n",__LINE__,#x);ok=0;goto done;}}while(0)
static int wait_end(unsigned ms) {
    ULONGLONG until=GetTickCount64()+ms;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<until)Sleep(5);
    return !InterlockedCompareExchange(&audio.device.running,0,0);
}
static int healthy(WoStats s){return s.opened&&!s.error[0]&&s.frames&&s.peak<.95;}
static int wave(const char *root,const char *name,const float *pcm) {
    char path[4096];VslWavWriter w={0};int ok;
    snprintf(path,sizeof path,"%s/%s.wav",root,name);
    if(!vsl_wav_begin_float(&w,path,48000,2))return 0;
    ok=vsl_wav_write(&w,pcm,FRAMES);return vsl_wav_end(&w)&&ok;
}
int wmain(int argc,wchar_t **argv) {
    char root[4096],path[4096];AdConfig cfg={0};AdControl c;AtTake loaded={0};
    WoStats record={0},solo={0},full={0},cancel={0};float *reference=NULL;FILE *report=NULL;
    unsigned choices=0,changes=0,old_count=0;uint64_t generation=0;int ok=1,initialized=0;ULONGLONG until;
    if(argc!=2||!WideCharToMultiByte(CP_UTF8,0,argv[1],-1,root,sizeof root,NULL,NULL))return 2;
    CHECK(fid_models_load(&idle)&&fr_models_load(&moving));
    cfg.bank=&moving.bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=2;cfg.root_per_rpm=1./120;
    cfg.scene_mode=AD_SCENE_STEREO_BED;cfg.resonant_bank=&moving.resonance;cfg.recipe_bank=&moving.recipe;cfg.fine_idle_profile=&idle.idle;
    am_audio_init(&audio,&cfg);initialized=1;audio.capture_frames=FRAMES+1024;
    audio.capture=calloc(audio.capture_frames*2,sizeof(float));audio.heard=calloc(audio.capture_frames*2,sizeof(float));
    reference=calloc(FRAMES*2,sizeof(float));CHECK(audio.capture&&audio.heard&&reference);
    c=am_default_control();c.drive.mode=VSL_BENCH;c.drive.ignition=c.drive.start_id=1;c.drive.rpm=850;c.drive.load=0;
    c.mix.gain=.18;c.mix.idle_mix=c.mix.idle_detail=c.mix.resonant_gain=c.mix.coherent_low_gain=c.mix.width=1;c.mix.idle_motion=.5;
    c.mix.intake_gain=c.mix.mechanical_gain=c.mix.air_gain=.12;
    CHECK(am_audio_control(&audio,&c)&&am_audio_record(&audio,1,FRAMES));until=GetTickCount64()+12000;
    while(audio.device.running&&GetTickCount64()<until) {
        uint64_t at=wo_stats(&audio.device).frames;
        if(choices<7&&at>=24000+choices*30000) {
            generation=audio.generation;CHECK(am_audio_listen_set(&audio,1+(int)(choices%6))&&audio.generation==generation);++choices;
        }
        if(changes<3&&at>=96000+changes*72000) {
            if(changes==0){c.drive.rpm=2400;c.drive.load=.7;}
            if(changes==1){c.drive.rpm=850;c.drive.load=0;}
            if(changes==2)c.drive.ignition=0;
            CHECK(am_audio_control(&audio,&c));++changes;
        }
        Sleep(5);
    }
    CHECK(wait_end(1000));am_audio_stop(&audio);record=wo_stats(&audio.device);
    CHECK(healthy(record)&&record.frames==FRAMES&&choices==7&&changes==3&&audio.ready&&audio.take.count==4);
    CHECK(audio.take.audio_hash==at_hash_samples(AT_HASH_INITIAL,audio.capture,FRAMES*2));
    CHECK(record.output_hash==at_hash_samples(AT_HASH_INITIAL,audio.heard,FRAMES*2)&&record.output_hash!=audio.take.audio_hash);
    CHECK(wave(root,"canonical_record",audio.capture)&&wave(root,"heard_record",audio.heard));
    snprintf(path,sizeof path,"%s/layer_monitor_schema10.vslrun",root);CHECK(at_take_save(&audio.take,path)&&at_take_load(&loaded,path));
    at_take_free(&audio.take);audio.take=loaded;memset(&loaded,0,sizeof loaded);old_count=audio.take.count;
    memset(&idle,0,sizeof idle);memset(&moving,0,sizeof moving); /*Replay owns its models. */
    CHECK(at_player_init(&portable,&owner,&audio.take,2));
    for(unsigned at=0;at<FRAMES;) {
        unsigned n=FRAMES-at>379?379:FRAMES-at;
        CHECK(at_player_process(&portable,reference+2*at,n,NULL)==n);at+=n;
    }
    CHECK(at_player_verified(&portable)&&!memcmp(reference,audio.capture,FRAMES*2*sizeof(float)));at_player_dispose(&portable);
    CHECK(am_audio_listen_set(&audio,LM_LOW+1)&&am_audio_replay(&audio,1));until=GetTickCount64()+12000;choices=0;
    CHECK(!am_audio_control(&audio,&c));
    while(audio.device.running&&GetTickCount64()<until) {
        if(choices<6&&wo_stats(&audio.device).frames>=24000+choices*36000) {
            generation=audio.generation;CHECK(am_audio_listen_set(&audio,(int)choices+1)&&audio.generation==generation);++choices;
        }
        Sleep(5);
    }
    CHECK(wait_end(1000));am_audio_stop(&audio);solo=wo_stats(&audio.device);
    CHECK(healthy(solo)&&solo.frames==FRAMES&&choices==6&&audio.replay_result==1&&audio.take.count==old_count);
    CHECK(audio.canonical_hash==audio.take.audio_hash&&solo.output_hash==at_hash_samples(AT_HASH_INITIAL,audio.heard,FRAMES*2));
    CHECK(solo.output_hash!=audio.take.audio_hash&&wave(root,"heard_replay",audio.heard));
    CHECK(am_audio_listen_set(&audio,0)&&am_audio_replay(&audio,1)&&wait_end(12000));am_audio_stop(&audio);full=wo_stats(&audio.device);
    CHECK(healthy(full)&&full.frames==FRAMES&&audio.replay_result==1&&full.output_hash==audio.take.audio_hash);
    CHECK(!memcmp(audio.heard,reference,FRAMES*2*sizeof(float)));
    CHECK(am_audio_listen_set(&audio,LM_DNA+1)&&am_audio_replay(&audio,1));until=GetTickCount64()+4000;
    while(audio.device.running&&wo_stats(&audio.device).frames<12000&&GetTickCount64()<until)Sleep(5);
    am_audio_stop(&audio);cancel=wo_stats(&audio.device);
    CHECK(healthy(cancel)&&cancel.frames<FRAMES&&audio.replay_result==2&&audio.take.count==old_count);
    snprintf(path,sizeof path,"%s/device.json",root);report=vsl_fopen(path,"wb");CHECK(report);
    fprintf(report,"{\"result\":\"pass\",\"muted\":true,\"frames\":%u,\"schema\":10,\"fields\":32,\"control_events\":%u,"
        "\"owned_models_destroyed\":true,\"record_solos\":7,\"replay_solos\":6,\"canonical_portable_pcm_exact\":true,"
        "\"canonical_hash\":\"%016llx\",\"heard_record_hash\":\"%016llx\",\"heard_solo_replay_hash\":\"%016llx\",\"heard_full_replay_hash\":\"%016llx\","
        "\"queue_empty\":[%u,%u,%u],\"over_budget\":[%u,%u,%u],\"max_ms\":[%.9g,%.9g,%.9g],\"cancel_frames\":%llu}\n",
        FRAMES,old_count,(unsigned long long)audio.take.audio_hash,(unsigned long long)record.output_hash,(unsigned long long)solo.output_hash,
        (unsigned long long)full.output_hash,record.queue_empty,solo.queue_empty,full.queue_empty,record.budget_exceeded,solo.budget_exceeded,full.budget_exceeded,
        record.render_ms_max,solo.render_ms_max,full.render_ms_max,(unsigned long long)cancel.frames);
    puts("PASS native muted record/solo replay/full exact bypass/cancel; canonical full PCM retained and owned playback exact");
done:
    if(report&&fclose(report))ok=0;at_take_free(&loaded);at_player_dispose(&portable);free(reference);
    if(initialized){am_audio_stop(&audio);free(audio.capture);free(audio.heard);audio.capture=audio.heard=NULL;am_audio_destroy(&audio);}return ok?0:3;
}
