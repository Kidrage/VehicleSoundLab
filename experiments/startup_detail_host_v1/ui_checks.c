#define _CRT_SECURE_NO_WARNINGS
#include "ui_checks.h"
#include <commctrl.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{++checks;if(!(x)){line=__LINE__;goto done;}}while(0)
int am_startup_detail_ui_check(HWND w,AmAudio *a,AmModels *m,int detail_study,const wchar_t *path) {
    unsigned checks=0;int line=0,ok=0;FILE *f=NULL;AdControl c;
    HWND detail=GetDlgItem(w,26),source=GetDlgItem(w,40),mode=GetDlgItem(w,41);
    c=am_audio_get(a);
    CHECK(a->config.scene_mode==AD_SCENE_STEREO_BED&&m->count==1&&a->config.startup_profile&&a->config.catch_profile);
    CHECK(!InterlockedCompareExchange(&a->device.running,0,0)&&!c.drive.ignition&&c.drive.mode==VSL_BENCH);
    CHECK(c.mix.startup_gain==.5&&c.mix.catch_gain==(detail_study?.5:0)&&c.mix.residual_gain==0);
    CHECK(c.mix.width==1&&SendMessageW(source,CB_GETCURSEL,0,0)==2);
    CHECK(IsWindowEnabled(detail)==(detail_study!=0));
    if(detail_study) {
        CHECK(a->config.residual_bank==&m->residual&&m->residual.count==1&&m->residual.profile[0].bands==12);
        SendMessageW(detail,TBM_SETPOS,TRUE,50);SendMessageW(w,WM_HSCROLL,TB_THUMBPOSITION,(LPARAM)detail);
        CHECK(am_audio_get(a).mix.residual_gain==.5);
        SendMessageW(detail,TBM_SETPOS,TRUE,100);SendMessageW(w,WM_HSCROLL,TB_THUMBPOSITION,(LPARAM)detail);
        CHECK(am_audio_get(a).mix.residual_gain==1);
    }
    SendMessageW(source,CB_SETCURSEL,0,0);SendMessageW(w,WM_COMMAND,MAKEWPARAM(40,CBN_SELCHANGE),(LPARAM)source);
    CHECK(m->count==4&&m->residual.count==4&&a->config.residual_bank==&m->residual);
    CHECK(!a->config.startup_profile&&!a->config.catch_profile&&am_audio_get(a).mix.catch_gain==0);
    SendMessageW(source,CB_SETCURSEL,2,0);SendMessageW(w,WM_COMMAND,MAKEWPARAM(40,CBN_SELCHANGE),(LPARAM)source);
    CHECK(m->count==1&&a->config.startup_profile&&a->config.catch_profile);
    CHECK(IsWindowEnabled(detail)==(detail_study!=0));
    if(!detail_study)CHECK(!a->config.residual_bank&&am_audio_get(a).mix.residual_gain==0);
    SendMessageW(mode,CB_SETCURSEL,0,0);SendMessageW(w,WM_COMMAND,MAKEWPARAM(41,CBN_SELCHANGE),(LPARAM)mode);
    CHECK(am_audio_get(a).drive.mode==VSL_PEDALS&&IsWindowEnabled(GetDlgItem(w,20))&&!IsWindowEnabled(GetDlgItem(w,22)));
    SendMessageW(mode,CB_SETCURSEL,1,0);SendMessageW(w,WM_COMMAND,MAKEWPARAM(41,CBN_SELCHANGE),(LPARAM)mode);
    CHECK(am_audio_get(a).drive.mode==VSL_BENCH&&!IsWindowEnabled(GetDlgItem(w,20))&&IsWindowEnabled(GetDlgItem(w,22)));
    ok=1;
done:
    if(_wfopen_s(&f,path,L"wb")||!f)return 0;
    fprintf(f,"{\"schema\":\"vsl.startup-detail-ui-check/1\",\"passed\":%s,\"detail_study\":%s,\"checks\":%u,\"failed_line\":%d,"
        "\"programmatic_own_window_controls\":true,\"visual_QA\":false,\"audio_started\":false}\n",ok?"true":"false",detail_study?"true":"false",checks,line);
    if(fclose(f))ok=0;return ok;
}
