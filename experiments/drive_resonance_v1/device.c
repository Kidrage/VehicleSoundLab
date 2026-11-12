#define _CRT_SECURE_NO_WARNINGS
#include "../atlas_monitor_v1/audio.h"
#include "../atlas_monitor_v1/models.h"
#include "resonant_detail_io/profile.h"
#include "stereo_resonance_io/profile.h"
#include "atlas_take_io/file.h"
#include "io/wav.h"
#include "io/file.h"
#include "drive/scenarios.h"
#include "inspect.h"
#include "../full_recipe_drive_v1/models.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static AmModels models;static SaBank bank;static DrsBank detail;static RdtProfile profile;static AmAudio audio;
static RvsProfile stereo_profile;
static FrModels full_models;
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
static int run(const char *root,int pedals,int stereo,int full) {
    AdConfig cfg={0};AdControl c;AtTake loaded={0};WoStats recorded={0},played={0},cancelled={0};
    const RdtProfile *profiles[SA_MAX_ANCHORS]={&profile};int initialized=0,ok=1,stage=0,active=0,inactive=0;
    const RvsProfile *stereos[SA_MAX_ANCHORS]={&stereo_profile};double base,root_per_rpm;
    ULONGLONG deadline;char path[4096];FILE *report=NULL;VslWavWriter wav={0};
    uint64_t frames=pedals?16*UINT64_C(48000)+123:144123;
    VslParams params=vsl_default_params(VSL_V10);
    if(full)CHECK(fr_models_load(&full_models));
    else {
        CHECK(am_models_load(&models,stereo?2:0)&&am_models_bank(&models,&bank));
        if(stereo)CHECK(rvs_profile_load("voices/stereo_resonance_v1/A cabin settle.sres",&stereo_profile)&&drs_bank_init_stereo(&detail,&bank,stereos));
        else CHECK(rdt_profile_load("voices/resonant_detail_c_v1/idle_add.rdetail",&profile)&&drs_bank_init(&detail,&bank,profiles));
    }
    base=full?full_models.dna.base_hz:stereo?stereo_profile.base_hz:profile.base_hz;root_per_rpm=stereo?base/vsl_profile(VSL_V10)->idle_rpm:1./120;
    cfg.bank=&bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=2;cfg.root_per_rpm=root_per_rpm;
    cfg.scene_mode=AD_SCENE_STEREO_BED;cfg.resonant_bank=&detail;
    if(full){cfg.bank=&full_models.bank;cfg.resonant_bank=&full_models.resonance;cfg.recipe_bank=&full_models.recipe;}
    am_audio_init(&audio,&cfg);initialized=1;audio.capture_frames=(size_t)frames+1024;audio.capture=calloc(audio.capture_frames*2,sizeof(float));CHECK(audio.capture);
    c=am_default_control();c.drive.mode=VSL_BENCH;c.drive.ignition=1;c.drive.start_id=1;c.drive.automatic=0;
    c.drive.rpm=base/root_per_rpm;c.mix.width=1;c.mix.resonant_gain=.7;
    if(full){c.mix.resonant_gain=1;c.mix.coherent_low_gain=1;}
    if(pedals){vsl_scenario_apply(VSL_SCENARIO_SHIFTS,0,&params);c.drive.mode=VSL_PEDALS;}
    CHECK(am_audio_control(&audio,&c)&&am_audio_record(&audio,1,frames));deadline=GetTickCount64()+(pedals?25000:10000);
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline) {
        WoStats s=wo_stats(&audio.device);AdTelemetry t=am_audio_latest(&audio);
        if(t.resonant_support>.5)active=1;if(s.frames>60000&&t.resonant_support==0)inactive=1;
        if(pedals) {
            vsl_scenario_apply(VSL_SCENARIO_SHIFTS,s.frames/48000.,&params);
            if(c.drive.ignition!=params.ignition||c.drive.gear!=params.gear||c.drive.throttle!=params.throttle||c.drive.brake!=params.brake){
                c.drive.ignition=params.ignition;c.drive.gear=params.gear;c.drive.throttle=params.throttle;c.drive.brake=params.brake;
                CHECK(am_audio_control(&audio,&c));++stage;
            }
        }
        else if(stage==0&&s.frames>=24000){c.drive.rpm=stereo||full?1.04*base/root_per_rpm:1300;c.mix.resonant_gain=1;if(full)c.mix.coherent_low_gain=.3;CHECK(am_audio_control(&audio,&c));stage=1;}
        else if(stage==1&&s.frames>=48000){c.drive.rpm=full?8000:6000;CHECK(am_audio_control(&audio,&c));stage=2;}
        else if(stage==2&&s.frames>=72000){c.drive.rpm=base/root_per_rpm;c.mix.resonant_gain=.4;if(full)c.mix.coherent_low_gain=.8;CHECK(am_audio_control(&audio,&c));stage=3;}
        Sleep(5);
    }
    CHECK(wait_end(1000));am_audio_stop(&audio);recorded=wo_stats(&audio.device);
    CHECK((pedals?stage>=6:stage==3&&active&&inactive)&&audio.ready&&recorded.frames==frames&&healthy(&recorded));
    snprintf(path,sizeof path,"%s/recorded.wav",root);CHECK(vsl_wav_begin_float(&wav,path,48000,2));
    CHECK(vsl_wav_write(&wav,audio.capture,(unsigned)recorded.frames)&&vsl_wav_end(&wav));
    snprintf(path,sizeof path,"%s/detail_schema8.vslrun",root);CHECK(at_take_save(&audio.take,path)&&at_take_load(&loaded,path));
    CHECK(loaded.assets->config.resonant_bank==&loaded.assets->resonant&&loaded.assets->resonant.enabled[0]);
    CHECK(loaded.assets->resonant.kind[0]==(unsigned)(stereo?DRS_STEREO:DRS_RDT));
    if(full)CHECK(loaded.assets->config.recipe_bank==&loaded.assets->recipe&&loaded.assets->recipe.has_low[0]);
    at_take_free(&audio.take);audio.take=loaded;memset(&loaded,0,sizeof loaded);
    memset(&models,0,sizeof models);memset(&bank,0,sizeof bank);memset(&profile,0,sizeof profile);memset(&detail,0,sizeof detail);
    memset(&stereo_profile,0,sizeof stereo_profile);
    memset(&full_models,0,sizeof full_models);
    CHECK(am_audio_replay(&audio,1)&&!am_audio_control(&audio,&c)&&wait_end(pedals?25000:10000));am_audio_stop(&audio);played=wo_stats(&audio.device);
    CHECK(healthy(&played)&&played.frames==recorded.frames&&played.output_hash==recorded.output_hash&&audio.replay_result==1);
    CHECK(am_audio_replay(&audio,1));deadline=GetTickCount64()+5000;
    while(wo_stats(&audio.device).frames<24000&&audio.device.running&&GetTickCount64()<deadline)Sleep(5);
    am_audio_stop(&audio);cancelled=wo_stats(&audio.device);CHECK(healthy(&cancelled)&&cancelled.frames<recorded.frames&&audio.replay_result==2);
    CHECK(drp_inspect(&audio.take,root));
    snprintf(path,sizeof path,"%s/device.json",root);report=vsl_fopen(path,"wb");CHECK(report);
    fprintf(report,"{\"result\":\"pass\",\"muted\":true,\"schema\":8,\"fields\":29,\"frames\":%llu,\"owned_models_destroyed_before_replay\":true,"
        "\"record_hash\":\"%016llx\",\"play_hash\":\"%016llx\",\"record_queue_empty\":%u,\"play_queue_empty\":%u,"
        "\"record_budget_exceeded\":%u,\"play_budget_exceeded\":%u,\"record_max_ms\":%.9g,\"play_max_ms\":%.9g,"
        "\"active_and_missing_support_observed\":%s,\"pedal_scenario\":%s,\"cancel_frames\":%llu,\"controls\":[",
        (unsigned long long)recorded.frames,(unsigned long long)recorded.output_hash,(unsigned long long)played.output_hash,
        recorded.queue_empty,played.queue_empty,recorded.budget_exceeded,played.budget_exceeded,recorded.render_ms_max,played.render_ms_max,
        active&&inactive?"true":"false",pedals?"true":"false",(unsigned long long)cancelled.frames);
    for(unsigned i=0;i<audio.take.count;++i)fprintf(report,"%s{\"frame\":%llu,\"mode\":%d,\"rpm_input\":%.17g,\"throttle\":%.17g,\"brake\":%.17g,\"gear_request\":%d,\"ignition\":%d,\"resonant_gain\":%.17g,\"coherent_low_gain\":%.17g}",i?",":"",
        (unsigned long long)audio.take.events[i].frame,audio.take.events[i].control.drive.mode,audio.take.events[i].control.drive.rpm,
        audio.take.events[i].control.drive.throttle,audio.take.events[i].control.drive.brake,audio.take.events[i].control.drive.gear,
        audio.take.events[i].control.drive.ignition,audio.take.events[i].control.mix.resonant_gain,audio.take.events[i].control.mix.coherent_low_gain);
    fprintf(report,"],\"stereo_kernel\":%s,\"full_recipe\":%s}\n",stereo?"true":"false",full?"true":"false");
    puts("PASS: one-driver local recipe, owned schema8 muted device replay and cancellation");
done:
    if(wav.file)vsl_wav_end(&wav);if(report&&fclose(report))ok=0;at_take_free(&loaded);
    if(initialized){am_audio_stop(&audio);free(audio.capture);audio.capture=NULL;am_audio_destroy(&audio);}return ok?0:3;
}
int wmain(int argc,wchar_t **argv) {
    char root[4096];int i,pedals=0,stereo=0,full=0;
    if(argc<2||argc>4||!WideCharToMultiByte(CP_UTF8,0,argv[1],-1,root,sizeof root,NULL,NULL))return 2;
    for(i=2;i<argc;++i)if(!wcscmp(argv[i],L"--pedals")&&!pedals)pedals=1;
        else if(!wcscmp(argv[i],L"--stereo")&&!stereo)stereo=1;
        else if(!wcscmp(argv[i],L"--full")&&!full)full=1;else return 2;
    if(full&&stereo)return 2;return run(root,pedals,stereo,full);
}
