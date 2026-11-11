#define _CRT_SECURE_NO_WARNINGS
#include "smoke.h"
#include "io/wav.h"
#include <commctrl.h>
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#define SM_REVIEW_DIR "references/analysis/sustain_monitor_v4/"
static int save_capture(SmAudio *a,const char *name,uint64_t frames){
    char path[256];VslWavWriter w={0};int ok;sprintf(path,SM_REVIEW_DIR "%s.wav",name);
    if(frames>a->capture_frames||!vsl_wav_begin_float(&w,path,48000,2))return 0;
    ok=vsl_wav_write(&w,a->capture,(unsigned)frames);return vsl_wav_end(&w)&&ok;
}
static void set(HWND window,HWND slider,int value){SendMessageW(slider,TBM_SETPOS,TRUE,value);SendMessageW(window,WM_HSCROLL,TB_THUMBPOSITION,(LPARAM)slider);}
int sm_smoke_prepare(SmSmoke *t,SmAudio *a){
    t->passed=t->isolated=1;a->frame_limit=384000;a->capture_frames=384000;
    a->capture=calloc(a->capture_frames*2,sizeof(float));return a->capture!=NULL;
}
static int valid(SmStats s){double ratio=s.device_seconds/s.playback_wall_seconds;
    return s.opened&&!s.error[0]&&s.frames==384000&&s.queue_empty==0&&ratio>.95&&ratio<1.03&&s.render_ms_total/s.blocks<512000./48000;
}
static void stats(FILE *f,const char *name,SmStats s){
    fprintf(f,"  \"%s\":{\"frames\":%" PRIu64 ",\"raw_float_hash\":\"%016" PRIx64 "\",\"opened\":%s,\"queue_empty\":%u,\"device_seconds\":%.9f,\"wall_seconds\":%.9f,\"startup_seconds\":%.9f,\"playback_wall_seconds\":%.9f,\"render_ms_mean\":%.9f,\"render_ms_max\":%.9f,\"min_pitch\":%.9f,\"max_pitch\":%.9f,\"min_detail\":%.9f,\"max_detail\":%.9f,\"min_attenuation\":%.9f,\"min_rumble\":%.9f,\"max_rumble\":%.9f,\"peak\":%.9f,\"error\":%s}",
        name,s.frames,s.raw_hash,s.opened?"true":"false",s.queue_empty,s.device_seconds,s.wall_seconds,s.startup_seconds,s.playback_wall_seconds,
        s.blocks?s.render_ms_total/s.blocks:0,s.render_ms_max,s.min_pitch,s.max_pitch,s.min_detail,s.max_detail,s.min_attenuation,s.min_rumble,s.max_rumble,s.peak,s.error[0]?"true":"false");
}
static void screenshot(HWND window){
    RECT r;HDC dc,memory;HBITMAP bitmap,old;BITMAPINFO info={0};BITMAPFILEHEADER header={0};unsigned char *pixels;FILE *f;int width,height;
    GetWindowRect(window,&r);width=r.right-r.left;height=r.bottom-r.top;r.left=r.top=0;r.right=width;r.bottom=height;
    dc=GetWindowDC(window);memory=CreateCompatibleDC(dc);bitmap=CreateCompatibleBitmap(dc,width,height);old=SelectObject(memory,bitmap);
    FillRect(memory,&r,GetSysColorBrush(COLOR_WINDOW));SendMessageW(window,WM_PRINT,(WPARAM)memory,PRF_NONCLIENT|PRF_CLIENT|PRF_ERASEBKGND|PRF_CHILDREN);
    info.bmiHeader.biSize=sizeof info.bmiHeader;info.bmiHeader.biWidth=width;info.bmiHeader.biHeight=-height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;
    pixels=malloc((size_t)width*height*4);SelectObject(memory,old);
    if(pixels&&GetDIBits(dc,bitmap,0,(UINT)height,pixels,&info,DIB_RGB_COLORS)){
        header.bfType=0x4d42;header.bfOffBits=sizeof header+sizeof info.bmiHeader;header.bfSize=header.bfOffBits+width*height*4;
        f=fopen(SM_REVIEW_DIR "native_preview.bmp","wb");if(f){fwrite(&header,sizeof header,1,f);fwrite(&info.bmiHeader,sizeof info.bmiHeader,1,f);fwrite(pixels,4,(size_t)width*height,f);fclose(f);}}
    free(pixels);DeleteObject(bitmap);DeleteDC(memory);ReleaseDC(window,dc);
}
static void mode_set(HWND w,HWND mode,int value){SendMessageW(mode,CB_SETCURSEL,value,0);SendMessageW(w,WM_COMMAND,MAKEWPARAM(32,CBN_SELCHANGE),(LPARAM)mode);}
void sm_smoke_tick(SmSmoke *t,SmAudio *a,HWND w,HWND pitch,HWND detail,HWND level,HWND rumble,HWND mode){
    SmStats s=sm_audio_stats(a);
    if(t->stage==0&&!a->running){
        t->baseline=s;sm_audio_stop(a);t->passed&=valid(s)&&save_capture(a,"baseline_device",s.frames);
        set(w,pitch,900);t->isolated&=a->pitch==900&&a->detail==1000&&a->db==0&&a->rumble==600&&a->mode==0;
        if(!sm_audio_start(a)){t->passed=0;DestroyWindow(w);return;}t->stage=1;
    }else if(t->stage>=1&&t->stage<=6){
        if(t->stage==1&&s.frames>=96000){set(w,pitch,1100);t->isolated&=a->pitch==1100&&a->detail==1000&&a->db==0;t->stage=2;}
        if(t->stage==2&&s.frames>=192000){set(w,detail,0);t->isolated&=a->pitch==1100&&a->detail==0&&a->db==0&&a->rumble==600;
            set(w,rumble,1000);t->isolated&=a->pitch==1100&&a->detail==0&&a->db==0&&a->rumble==1000&&a->mode==0;t->stage=3;}
        if(t->stage==3&&s.frames>=240000){set(w,level,6);t->isolated&=a->pitch==1100&&a->detail==0&&a->db==-6&&a->rumble==1000;
            mode_set(w,mode,2);t->isolated&=a->mode==2&&a->rumble==1000&&a->detail==0;t->stage=4;}
        if(t->stage==4&&s.frames>=288000){set(w,detail,1000);t->isolated&=a->pitch==1100&&a->detail==1000&&a->db==-6&&a->mode==2;
            set(w,rumble,0);t->isolated&=a->rumble==0&&a->detail==1000&&a->mode==2;mode_set(w,mode,0);t->stage=5;}
        if(t->stage==5&&s.frames>=336000){set(w,level,0);t->stage=6;}
        if(!a->running){t->live=s;sm_audio_stop(a);t->passed&=t->stage==6&&valid(s)&&save_capture(a,"live_device",s.frames);
            set(w,pitch,1000);set(w,detail,1000);set(w,level,0);set(w,rumble,600);a->frame_limit=0;
            SendMessageW(w,WM_COMMAND,10,0);t->stage=7;}
    }else if(t->stage==7&&s.frames>=24000){
        SendMessageW(w,WM_COMMAND,11,0);t->stopped=sm_audio_stats(a);
        t->passed&=!a->running&&a->render.release==480&&a->thread==NULL;
        t->passed&=save_capture(a,"stopped_device",t->stopped.frames);
        SendMessageW(w,WM_COMMAND,10,0);t->stage=8;
    }else if(t->stage==8&&s.frames>=24000){t->stage=9;screenshot(w);SendMessageW(w,WM_CLOSE,0,0);}
}
void sm_smoke_finish(SmSmoke *t,SmAudio *a,HWND window){
    SmStats closed=sm_audio_stats(a);FILE *f;
    t->passed&=t->stage==9&&!a->running&&a->render.release==480&&closed.opened&&!closed.error[0]&&closed.queue_empty==0;
    t->passed&=t->isolated&&t->live.min_pitch<.901&&t->live.max_pitch>1.099&&t->live.min_detail<.001&&t->live.max_detail>.999&&t->live.min_attenuation<.502&&t->live.min_rumble<.001&&t->live.max_rumble>.999;
    f=fopen(SM_REVIEW_DIR "native_preview.json","wb");if(f){fprintf(f,"{\n  \"result\":\"%s\",\n  \"device_muted\":true,\n  \"controls_isolated\":%s,\n  \"stop_and_restart\":%s,\n  \"close_while_playing\":%s,\n",t->passed?"pass":"fail",t->isolated?"true":"false",a->thread==NULL?"true":"false",t->stage==9?"true":"false");
        stats(f,"baseline",t->baseline);fprintf(f,",\n");stats(f,"live",t->live);fprintf(f,",\n");stats(f,"stopped",t->stopped);fprintf(f,",\n");stats(f,"closed",closed);fprintf(f,"\n}\n");fclose(f);
    }else t->passed=0;
    (void)window;free(a->capture);a->capture=NULL;
}

