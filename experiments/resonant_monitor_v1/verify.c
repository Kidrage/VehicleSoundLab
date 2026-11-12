#define _CRT_SECURE_NO_WARNINGS
#include "audio.h"
#include "io/wav.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static RsmAssets assets;static RsmAudio audio;static RsmRender offline;
static int replay(const WoStats *s) {
    float pcm[1024];uint64_t at=0;unsigned event=0;
    if(!audio.trace_count||!rsm_render_init(&offline,&audio.config,2,&audio.trace[0].control))return 0;
    while(at<s->frames) {
        unsigned n=(unsigned)(s->frames-at);if(n>512)n=512;
        while(event<audio.trace_count&&audio.trace[event].frame==at)
            if(!rsm_render_set(&offline,&audio.trace[event++].control))return 0;
        if(!rsm_render_process(&offline,pcm,n,at>=audio.stop_frame,NULL)||memcmp(pcm,audio.capture+2*at,n*2*sizeof(float)))return 0;
        at+=n;
    }return event==audio.trace_count;
}
static int healthy(const WoStats *s) {
    return s->opened&&!s->error[0]&&!s->queue_empty&&s->frames&&s->peak<.95&&
        fabs(s->device_seconds-s->frames/48000.)<.06&&
        fabs(s->playback_wall_seconds-s->frames/48000.)<.15&&!audio.trace_overflow;
}
static int save(const char *root,const char *name,const WoStats *s,int equal) {
    char path[4096];FILE *f;VslWavWriter wav={0};unsigned i;int ok;
    snprintf(path,sizeof path,"%s/%s.wav",root,name);if(!vsl_wav_begin_float(&wav,path,48000,2))return 0;
    ok=vsl_wav_write(&wav,audio.capture,(unsigned)s->frames);if(!vsl_wav_end(&wav))ok=0;
    snprintf(path,sizeof path,"%s/%s.json",root,name);f=vsl_fopen(path,"wb");if(!f)return 0;
    fprintf(f,"{\"schema\":\"vsl.resonant-monitor-device/1\",\"muted\":true,\"healthy\":%s,\"offline_float_equal\":%s,"
        "\"frames\":%llu,\"blocks\":%u,\"queue_empty\":%u,\"budget_exceeded\":%u,\"render_mean_ms\":%.9g,\"render_max_ms\":%.9g,"
        "\"device_seconds\":%.9g,\"wall_seconds\":%.9g,\"peak\":%.9g,\"stop_frame\":%llu,\"release\":%u,\"controls\":[",
        healthy(s)?"true":"false",equal?"true":"false",(unsigned long long)s->frames,s->blocks,s->queue_empty,s->budget_exceeded,
        s->render_ms_total/fmax(1,s->blocks),s->render_ms_max,s->device_seconds,s->playback_wall_seconds,s->peak,
        (unsigned long long)audio.stop_frame,audio.render.release);
    for(i=0;i<audio.trace_count;++i){const RsmControl *p=&audio.trace[i].control;
        fprintf(f,"%s{\"frame\":%llu,\"pitch\":%.17g,\"detail\":%.17g,\"low\":%.17g,\"gain\":%.17g,\"width\":%.17g}",
            i?",":"",(unsigned long long)audio.trace[i].frame,p->source.source.pitch,p->source.detail_gain,p->source.source.low_gain,p->gain,p->width);}
    fputs("]}\n",f);ok&=!ferror(f);if(fclose(f))ok=0;return ok;
}
static int device_run(const char *root,const char *name,int selection,int mode) {
    RssConfig cfg;RsmControl p;WoStats s;ULONGLONG deadline;int stage=0,equal;
    uint64_t limit=mode==0?144123:mode==2?24637:0;
    rsm_audio_stop(&audio);if(!rsm_assets_load(&assets,selection))return 0;
    cfg=rsm_assets_config(&assets);p=rsm_assets_control(&assets);rsm_audio_rebind(&audio,&cfg,&p);
    if(!rsm_audio_start(&audio,1,limit))return 0;deadline=GetTickCount64()+10000;
    while(InterlockedCompareExchange(&audio.device.running,0,0)&&GetTickCount64()<deadline) {
        WoStats now=wo_stats(&audio.device);
        if(mode==0&&now.frames>=24000&&stage==0){p.source.source.pitch=.9;p.source.detail_gain=.7;stage=1;}
        else if(mode==0&&now.frames>=48000&&stage==1){p.source.source.low_gain=assets.has_low?.25:0;p.gain=.25;stage=2;}
        else if(mode==0&&now.frames>=72000&&stage==2){p.source.source.pitch=1.1;p.width=.6;stage=3;}
        else if(mode==1&&now.frames>=24000)break;
        else {Sleep(5);continue;}
        if(!rsm_audio_control(&audio,&p)){rsm_audio_stop(&audio);return 0;}
    }
    rsm_audio_stop(&audio);s=wo_stats(&audio.device);equal=replay(&s);
    printf("%s frames%llu queue%u budget%u max%.3fms exact%d\n",name,(unsigned long long)s.frames,s.queue_empty,s.budget_exceeded,s.render_ms_max,equal);
    return save(root,name,&s,equal)&&healthy(&s)&&equal&&(mode==1?audio.render.release==480:s.frames==limit)&&
        (mode!=0||stage==3)&&!audio.device.running&&!audio.device.thread;
}
static int dry_reference(const char *root,int selection,const char *name) {
    RssConfig cfg;RsmControl p;float pcm[1024],dry[1024];RsmCapture tap={NULL,NULL,NULL,dry};
    VslWavWriter wav={0};char path[4096];unsigned at;int ok=1;
    if(!rsm_assets_load(&assets,selection))return 0;cfg=rsm_assets_config(&assets);p=rsm_assets_control(&assets);
    if(!rsm_render_init(&offline,&cfg,2,&p))return 0;
    snprintf(path,sizeof path,"%s/%s_dry.wav",root,name);if(!vsl_wav_begin_float(&wav,path,48000,2))return 0;
    for(at=0;at<8*48000;at+=512){unsigned n=8*48000-at;if(n>512)n=512;
        if(!rsm_render_process(&offline,pcm,n,0,&tap)||!vsl_wav_write(&wav,dry,n)){ok=0;break;}}
    if(!vsl_wav_end(&wav))ok=0;return ok;
}
static int run(const char *root) {
    RssConfig cfg;RsmControl p;int ok;
    if(!rsm_assets_load(&assets,4))return 2;cfg=rsm_assets_config(&assets);p=rsm_assets_control(&assets);
    rsm_audio_init(&audio,&cfg,&p);audio.capture_frames=4*48000;audio.capture=calloc(audio.capture_frames*2,sizeof(float));
    if(!audio.capture){rsm_audio_destroy(&audio);return 2;}
    ok=device_run(root,"moving",4,0);ok&=device_run(root,"low",1,0);
    ok&=device_run(root,"stopped",4,1);ok&=device_run(root,"restart",1,2);
    /* Models change only after worker joins; these exports use the identical monitor DSP. */
    ok&=dry_reference(root,4,"moving_35");ok&=dry_reference(root,1,"idle_add");ok&=dry_reference(root,2,"idle_35");
    free(audio.capture);audio.capture=NULL;rsm_audio_destroy(&audio);
    puts(ok?"PASS: muted device, adopted-control replay, transport and dry captures":"FAIL: inspect saved evidence");return ok?0:3;
}
int wmain(int argc,wchar_t **wide) {
    char root[4096];if(argc!=2||!WideCharToMultiByte(CP_UTF8,0,wide[1],-1,root,sizeof root,NULL,NULL))return 2;
    return run(root);
}
