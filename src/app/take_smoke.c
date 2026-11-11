#include "take_smoke.h"
#include "version.h"
#include "io/take_file.h"
#include "io/take_render.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
void vsl_take_smoke(VslAudio *a,VslTakes *t,const wchar_t *workspace,int locked) {
    wchar_t file[MAX_PATH];char take_path[MAX_PATH*4],wav_path[MAX_PATH*4];
    VslTake loaded={0};VslTakePlayer player;VslEngine *e=malloc(sizeof *e);
    VslDrive expected=a->engine->drive;VslCharacter expected_character=a->engine->character;
    VslResponseShape expected_response=a->engine->response;int response_state=0,device_response=0;
    VslEventColor expected_color=a->engine->color;int color_state=0,device_color=0;
    VslFiringSource expected_pulse=a->engine->firing_source;int pulse_state=0,device_pulse=0;
    float buffer[514];uint64_t hash=0;int saved,load,offline=0,state=0,device=0,interrupted=0,character_state=0,device_character=0;
    double mean=0,max=0,wall=0,seconds=0;unsigned empty=0,blocks=0;ULONGLONG start;
    swprintf(file,MAX_PATH,L"%s\\renders\\%s\\ui_take_smoke.vsltake",workspace,VSL_DIAGNOSTIC_FOLDER_W);
    saved=vsl_takes_save(t,file);WideCharToMultiByte(CP_UTF8,0,file,-1,take_path,sizeof take_path,NULL,NULL);
    swprintf(file,MAX_PATH,L"%s\\renders\\%s\\ui_take_smoke.wav",workspace,VSL_DIAGNOSTIC_FOLDER_W);
    WideCharToMultiByte(CP_UTF8,0,file,-1,wav_path,sizeof wav_path,NULL,NULL);
    load=vsl_take_load(take_path,&loaded);
    if(e&&load&&vsl_take_player_init(&player,e,&loaded)) {
        while(vsl_take_process(&player,e,buffer,257,2,NULL)) { }
        state=!memcmp(&expected,&e->drive,sizeof expected);
        character_state=!memcmp(&expected_character,&e->character,sizeof expected_character);
        response_state=!memcmp(&expected_response,&e->response,sizeof expected_response);
        color_state=!memcmp(&expected_color,&e->color,sizeof expected_color);
        pulse_state=!memcmp(&expected_pulse,&e->firing_source,sizeof expected_pulse);
        offline=player.audio_hash==loaded.audio_hash&&vsl_take_render(&loaded,wav_path,2,NULL,NULL,&hash)&&hash==loaded.audio_hash;
    }
    swprintf(file,MAX_PATH,L"%s\\renders\\%s\\ui_take_smoke.vsltake",workspace,VSL_DIAGNOSTIC_FOLDER_W);
    if(load&&vsl_takes_play(t,a,file)&&vsl_audio_start(a)) {
        start=GetTickCount64();while(a->running&&GetTickCount64()-start<15000)Sleep(10);
        vsl_audio_stop(a);
        device=a->take_hash_match&&!memcmp(&expected,&a->engine->drive,sizeof expected)&&!a->error[0];
        device_character=!memcmp(&expected_character,&a->engine->character,sizeof expected_character);
        device_response=!memcmp(&expected_response,&a->engine->response,sizeof expected_response);
        device_color=!memcmp(&expected_color,&a->engine->color,sizeof expected_color);
        device_pulse=!memcmp(&expected_pulse,&a->engine->firing_source,sizeof expected_pulse);
        blocks=a->rendered_blocks;mean=a->render_ms_total/(blocks?blocks:1);max=a->render_ms_max;
        wall=a->worker_wall_seconds;seconds=a->device_seconds;empty=a->queue_empty_observations;
        if(vsl_takes_play(t,a,file)&&vsl_audio_start(a)) {
            Sleep(110);vsl_audio_stop(a);
            interrupted=!a->running&&!a->thread&&!a->error[0]&&a->engine->frame>0&&a->engine->frame<t->take.frames;
        }
    }
    a->take_mode=0;
    swprintf(file,MAX_PATH,L"%s\\renders\\%s\\ui_take_smoke.json",workspace,VSL_DIAGNOSTIC_FOLDER_W);
    {
        FILE *f=_wfopen(file,L"w");
        if(f) {
            fprintf(f,"{\"character_state_match\":%d,\"device_character_state_match\":%d,\"response_state_match\":%d,\"device_response_state_match\":%d,\"event_color_state_match\":%d,\"device_event_color_state_match\":%d,\"pulse_state_match\":%d,\"device_pulse_state_match\":%d,\"result\":",character_state,device_character,response_state,device_response,color_state,device_color,pulse_state,device_pulse);
            fprintf(f,"{\"dsp\":\"%s\",\"saved\":%d,\"loaded\":%d,\"offline_hash_match\":%d,\"final_drive_state_match\":%d,\"device_replay_hash_and_state_match\":%d,\"manual_replay_stop\":%d,\"controls_locked\":%d,\"muted\":%d,\"frames\":%" PRIu64 ",\"events\":%u,\"audio_hash\":\"%016" PRIx64 "\",\"replay_render_ms_mean\":%.4f,\"replay_render_ms_max\":%.4f,\"replay_device_seconds\":%.4f,\"replay_wall_seconds\":%.4f,\"replay_blocks\":%u,\"replay_queue_empty\":%u}\n",VSL_VERSION,saved,load,offline,state,device,interrupted,locked,a->diagnostic_mute,loaded.frames,loaded.count,loaded.audio_hash,mean,max,seconds,wall,blocks,empty);
            fputs("}\n",f);fclose(f);
        }
    }
    vsl_take_free(&loaded);free(e);
}
