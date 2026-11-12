#define _CRT_SECURE_NO_WARNINGS
#include "ui_checks.h"
#include <commctrl.h>
#include <stdio.h>
#include <math.h>
/* Internal instrumentation of this application's own controls and window. */
static void slider(HWND w,int id,int v) {
    HWND item=GetDlgItem(w,id);SendMessageW(item,TBM_SETPOS,TRUE,v);
    SendMessageW(w,WM_HSCROLL,MAKEWPARAM(TB_THUMBPOSITION,v),(LPARAM)item);
}
static void select_voice(HWND w,int selection) {
    HWND item=GetDlgItem(w,40);SendMessageW(item,CB_SETCURSEL,selection,0);
    SendMessageW(w,WM_COMMAND,MAKEWPARAM(40,CBN_SELCHANGE),(LPARAM)item);
}
static int capture(HWND w,const wchar_t *directory,const wchar_t *name) {
    RECT rect;HDC dc,memory;HBITMAP bitmap,old;BITMAPINFO info={0};BITMAPFILEHEADER head={0};
    void *pixels;wchar_t path[4096];FILE *file;DWORD bytes;int ok=0;
    GetWindowRect(w,&rect);dc=GetWindowDC(w);memory=CreateCompatibleDC(dc);
    info.bmiHeader.biSize=sizeof info.bmiHeader;info.bmiHeader.biWidth=rect.right-rect.left;
    info.bmiHeader.biHeight=-(rect.bottom-rect.top);info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;
    bitmap=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&pixels,NULL,0);
    if(!bitmap){DeleteDC(memory);ReleaseDC(w,dc);return 0;}old=SelectObject(memory,bitmap);
    RedrawWindow(w,NULL,NULL,RDW_INVALIDATE|RDW_ERASE|RDW_FRAME|RDW_ALLCHILDREN|RDW_UPDATENOW);
    if(!PrintWindow(w,memory,0))goto done;
    bytes=(DWORD)(info.bmiHeader.biWidth*-info.bmiHeader.biHeight*4);
    head.bfType=0x4d42;head.bfOffBits=sizeof head+sizeof info.bmiHeader;head.bfSize=head.bfOffBits+bytes;
    swprintf(path,4096,L"%ls/%ls.bmp",directory,name);file=_wfopen(path,L"wb");if(!file)goto done;
    ok=fwrite(&head,sizeof head,1,file)==1&&fwrite(&info.bmiHeader,sizeof info.bmiHeader,1,file)==1&&fwrite(pixels,bytes,1,file)==1;
    if(fclose(file))ok=0;
done:SelectObject(memory,old);DeleteObject(bitmap);DeleteDC(memory);ReleaseDC(w,dc);return ok;
}
void rsm_ui_checks_tick(RsmUiChecks *t,HWND w,RsmAudio *a) {
    WoStats s=wo_stats(&a->device);RsmControl p;int i;
    if(!t->enabled)return;
    if(t->stage==0) {
        t->passed=!a->device.running;t->controls_ok=1;
        for(i=0;i<5;++i) {
            int detail=i==1||i==2||i==4,low=i>=3;
            select_voice(w,i);p=rsm_audio_get(a);
            t->controls_ok&=IsWindowEnabled(GetDlgItem(w,21))==detail&&IsWindowEnabled(GetDlgItem(w,22))==low;
            t->controls_ok&=p.source.detail_gain==(detail?1:0)&&p.source.source.low_gain==(low?1:0);
        }
        t->passed&=capture(w,t->directory,L"moving");
        SendMessageW(w,WM_COMMAND,10,0);t->stage=1;
    } else if(t->stage==1&&s.frames>=24000) {
        slider(w,20,900);slider(w,21,70);p=rsm_audio_get(a);
        t->controls_ok&=p.source.source.pitch==.9&&p.source.detail_gain==.7;t->stage=2;
    } else if(t->stage==2&&s.frames>=48000) {
        slider(w,22,25);slider(w,23,-6);p=rsm_audio_get(a);
        t->controls_ok&=p.source.source.low_gain==.25&&fabs(p.gain-.5*pow(10,-6./20))<1e-15;t->stage=3;
    } else if(t->stage==3&&s.frames>=72000) {
        slider(w,20,1100);p=rsm_audio_get(a);t->controls_ok&=p.source.source.pitch==1.1;t->stage=4;
    } else if(t->stage==4&&s.frames>=96000) {
        SendMessageW(w,WM_COMMAND,11,0);
        t->passed&=!a->device.running&&!a->device.thread&&a->render.release==480&&a->trace_count>=4;
        select_voice(w,1);t->passed&=capture(w,t->directory,L"low");
        SendMessageW(w,WM_COMMAND,10,0);t->stage=5;
    } else if(t->stage==5&&s.frames>=24000) {
        t->stage=6;SendMessageW(w,WM_CLOSE,0,0);
    }
}
void rsm_ui_checks_finish(RsmUiChecks *t,RsmAudio *a) {
    WoStats s;wchar_t path[4096];FILE *f;
    if(!t->enabled)return;s=wo_stats(&a->device);
    t->passed&=t->stage==6&&t->controls_ok&&!a->device.running&&!a->device.thread&&a->render.release==480&&
        s.opened&&!s.error[0]&&!s.queue_empty;
    swprintf(path,4096,L"%ls/ui.json",t->directory);f=_wfopen(path,L"wb");if(!f){t->passed=0;return;}
    fprintf(f,"{\"result\":\"%s\",\"own_program_control_test\":true,\"manual_mouse_interaction\":false,"
        "\"muted_device\":true,\"all5presets\":%s,\"controls\":%s,\"stop_restart_close\":%s,\"queue_empty\":%u,\"budget_exceeded\":%u}\n",
        t->passed?"pass":"fail",t->controls_ok?"true":"false",t->controls_ok?"true":"false",t->stage==6?"true":"false",s.queue_empty,s.budget_exceeded);
    fclose(f);
}
