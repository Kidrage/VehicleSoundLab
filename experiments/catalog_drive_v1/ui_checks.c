#define _CRT_SECURE_NO_WARNINGS
#include "ui_checks.h"
#include "atlas_take_io/file.h"
#include <commctrl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{++checks;if(!(x)){line=__LINE__;goto done;}}while(0)
#define FRAMES 64123u
/* Program-owned window only. No external app or desktop automation. */
static int capture(HWND w,const wchar_t *path) {
    RECT r;HDC dc,m;HBITMAP b,old;BITMAPINFO info={0};BITMAPFILEHEADER h={0};void *pixels;FILE *f;int ok=0;DWORD bytes;
    GetWindowRect(w,&r);dc=GetWindowDC(w);m=CreateCompatibleDC(dc);info.bmiHeader.biSize=sizeof info.bmiHeader;
    info.bmiHeader.biWidth=r.right-r.left;info.bmiHeader.biHeight=r.top-r.bottom;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;
    b=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&pixels,NULL,0);if(!b){DeleteDC(m);ReleaseDC(w,dc);return 0;}
    old=SelectObject(m,b);ShowWindow(w,SW_SHOWNOACTIVATE);RedrawWindow(w,NULL,NULL,RDW_INVALIDATE|RDW_ERASE|RDW_FRAME|RDW_ALLCHILDREN|RDW_UPDATENOW);
    if(!PrintWindow(w,m,0))goto done;
    bytes=(DWORD)(info.bmiHeader.biWidth*-info.bmiHeader.biHeight*4);h.bfType=0x4d42;h.bfOffBits=sizeof h+sizeof info.bmiHeader;h.bfSize=h.bfOffBits+bytes;
    f=_wfopen(path,L"wb");if(!f)goto done;ok=fwrite(&h,sizeof h,1,f)==1&&fwrite(&info.bmiHeader,sizeof info.bmiHeader,1,f)==1&&fwrite(pixels,bytes,1,f)==1;if(fclose(f))ok=0;
done:SelectObject(m,old);DeleteObject(b);DeleteDC(m);ReleaseDC(w,dc);return ok;
}
static int wait_end(AmAudio *a,unsigned ms) {
    ULONGLONG deadline=GetTickCount64()+ms;
    while(InterlockedCompareExchange(&a->device.running,0,0)&&GetTickCount64()<deadline)Sleep(5);
    return !InterlockedCompareExchange(&a->device.running,0,0);
}
static void choose(HWND w,HWND control,int value) {
    SendMessageW(control,CB_SETCURSEL,value,0);SendMessageW(w,WM_COMMAND,MAKEWPARAM(GetDlgCtrlID(control),CBN_SELCHANGE),(LPARAM)control);
}
int cd_ui_check(HWND w,AmAudio *a,CdSession *session,const wchar_t *path) {
    unsigned checks=0,empty[DC_COUNT]={0},budget[DC_COUNT]={0};uint64_t hashes[DC_COUNT]={0};
    int line=0,ok=0;FILE *report=NULL;wchar_t name[4096];HWND voices=GetDlgItem(w,40),aux=GetDlgItem(w,43),listen_choice=GetDlgItem(w,44);
    AdControl c,live;float *capture_pcm=NULL,*heard=NULL;
    const int order[]={DC_DECEL,DC_STATIONARY5,DC_FINE_IDLE,DC_MOVING,DC_EXTERIOR,DC_CABIN,DC_SETTLE,DC_WARM,DC_HOLLOW};
    unsigned visited=0;
    CHECK(sizeof order/sizeof *order==DC_COUNT);
    CHECK(voices&&aux&&SendMessageW(voices,CB_GETCOUNT,0,0)==DC_COUNT+1&&SendMessageW(aux,CB_GETCOUNT,0,0)==DC_AUX_COUNT);
    CHECK(dc_preset_selection(session->preset)==DC_FINE_IDLE&&!a->device.running&&!am_audio_get(a).drive.ignition);
    swprintf(name,4096,L"%ls.default.bmp",path);CHECK(capture(w,name));
    capture_pcm=calloc((FRAMES+1024)*2,sizeof(float));heard=calloc((FRAMES+1024)*2,sizeof(float));CHECK(capture_pcm&&heard);
    a->capture=capture_pcm;a->heard=heard;a->capture_frames=FRAMES+1024;
    /* Test the new observation first; retain Hollow as the last recording
       so the existing cross-profile embedded-replay test still tests SCIFI. */
    for(int pass=0;pass<DC_COUNT;++pass) {
        int k=order[pass];CHECK(k>=0&&k<DC_COUNT&&!(visited&(1u<<k)));visited|=1u<<k;
        choose(w,voices,k);c=am_audio_get(a);
        CHECK(dc_preset_selection(session->preset)==k&&!a->device.running&&!c.drive.ignition&&a->transport==0);
        CHECK(a->config.profile==dc_info(k)->profile&&IsWindowEnabled(voices));
        CHECK(IsWindowEnabled(GetDlgItem(w,26))==(a->config.resonant_bank||a->config.residual_bank));
        CHECK(IsWindowEnabled(GetDlgItem(w,27))==dc_body_enabled(&a->config));
        if(k==DC_STATIONARY5){swprintf(name,4096,L"%ls.stationary.bmp",path);CHECK(capture(w,name));}
        if(k==DC_DECEL){swprintf(name,4096,L"%ls.decel.bmp",path);CHECK(capture(w,name));}
        for(int j=0;j<DC_AUX_COUNT;++j) {
            choose(w,aux,j);CHECK(IsWindowEnabled(GetDlgItem(w,28))==dc_aux_enabled(&a->config,j));
            if(dc_aux_enabled(&a->config,j)) {
                SendMessageW(GetDlgItem(w,28),TBM_SETPOS,TRUE,37);SendMessageW(w,WM_HSCROLL,TB_THUMBPOSITION,(LPARAM)GetDlgItem(w,28));
                c=am_audio_get(a);CHECK(*dc_aux_amount(&c,j)==.37);
            }
        }
        /* Reload restores the unchanged recipe after checking every binding. */
        choose(w,voices,k);SendMessageW(w,WM_COMMAND,12,0);CHECK(am_audio_get(a).drive.ignition);
        if(k==DC_STATIONARY5) {
            choose(w,GetDlgItem(w,41),0);choose(w,GetDlgItem(w,42),1);
            SendMessageW(GetDlgItem(w,20),TBM_SETPOS,TRUE,37);
            SendMessageW(w,WM_HSCROLL,TB_THUMBPOSITION,(LPARAM)GetDlgItem(w,20));
            c=am_audio_get(a);CHECK(c.drive.mode==VSL_PEDALS&&c.drive.gear==0&&!c.drive.automatic&&c.drive.throttle==.37);
        }
        CHECK(am_audio_listen_set(a,0)&&am_audio_record(a,1,FRAMES));SendMessageW(w,WM_TIMER,1,0);
        CHECK(!IsWindowEnabled(voices)&&IsWindowEnabled(listen_choice)&&!cd_session_commit(session,a,NULL));
        CHECK(!cd_session_commit(session,a,session->preset)&&a->device.running);
        CHECK(wait_end(a,5000));am_audio_stop(a);
        {WoStats s=wo_stats(&a->device);CHECK(s.opened&&!s.error[0]&&s.frames==FRAMES&&a->ready);
            CHECK(a->take.audio_hash==s.output_hash&&s.output_hash==at_hash_samples(AT_HASH_INITIAL,capture_pcm,FRAMES*2));
            hashes[k]=s.output_hash;empty[k]=s.queue_empty;budget[k]=s.budget_exceeded;}
        CHECK(am_audio_replay(a,1)&&am_audio_listen_set(a,LM_DNA+1)&&wait_end(a,5000));am_audio_stop(a);
        CHECK(a->replay_result==1&&a->canonical_hash==hashes[k]);
        if(k==DC_HOLLOW){SendMessageW(w,WM_TIMER,1,0);swprintf(name,4096,L"%ls.replay.bmp",path);CHECK(capture(w,name));}
    }
    CHECK(visited==(1u<<DC_COUNT)-1);
    /* Replay a synthetic embedded take while live preset is the V10 fine idle. */
    choose(w,voices,DC_FINE_IDLE);live=am_audio_get(a);cd_session_before_replay(session,a);
    CHECK(a->config.fine_idle_profile&&am_audio_replay(a,1));SendMessageW(w,WM_TIMER,1,0);
    CHECK(SendMessageW(voices,CB_GETCURSEL,0,0)==DC_COUNT&&!IsWindowEnabled(GetDlgItem(w,26)));
    CHECK(a->take.assets->config.profile==VSL_SCIFI&&a->config.profile==VSL_V10&&wait_end(a,5000));am_audio_stop(a);
    SendMessageW(w,WM_TIMER,1,0);CHECK(!IsWindowEnabled(GetDlgItem(w,12))&&IsWindowEnabled(voices));
    a->capture=a->heard=NULL;SendMessageW(w,WM_COMMAND,10,0);CHECK(a->device.running&&a->transport==0);
    c=am_audio_get(a);CHECK(!memcmp(&c,&live,sizeof c)&&a->config.fine_idle_profile);
    SendMessageW(w,WM_COMMAND,11,0);CHECK(!a->device.running);SendMessageW(w,WM_TIMER,1,0);
    swprintf(name,4096,L"%ls.restored.bmp",path);CHECK(capture(w,name));ok=1;
done:
    am_audio_stop(a);a->capture=a->heard=NULL;free(capture_pcm);free(heard);
    report=_wfopen(path,L"wb");if(!report)return 0;
    fprintf(report,"{\"result\":\"%s\",\"checks\":%u,\"failed_line\":%d,\"muted\":true,\"voices\":%d,\"frames_per_record\":%u,"
        "\"own_program_controls\":true,\"manual_mouse_verified\":false,\"cross_voice_replay_and_live_restore\":%s,\"records\":[",ok?"pass":"fail",checks,line,DC_COUNT,FRAMES,ok?"true":"false");
    for(int k=0;k<DC_COUNT;++k)fprintf(report,"%s{\"selection\":%d,\"hash\":\"%016llx\",\"queue_empty\":%u,\"budget_exceeded\":%u}",k?",":"",k,(unsigned long long)hashes[k],empty[k],budget[k]);
    fputs("]}\n",report);if(fclose(report))ok=0;return ok;
}
