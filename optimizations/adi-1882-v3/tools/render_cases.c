/* Identical 200 Hz input timeline for A/B. Outer timing includes control set
   and all synthesis calls, excludes creation, file writes and result checks.
   Windows times/cycles are host measurements, never ADSP MCPS. */
#define _CRT_SECURE_NO_WARNINGS
#include "experiments/vehicle_source_v1/bridge.h"
#include "presets/events/reference_afterfire_G_v3.h"
#include <windows.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

typedef struct {
    VsbHandle *(*open)(int);
    void (*close)(VsbHandle *);
    int (*controls)(VsbHandle *,VsControl *);
    int (*set)(VsbHandle *,const VsControl *);
    int (*process)(VsbHandle *,float *,float *,unsigned);
    int (*profile)(VsbHandle *,unsigned,const EsProfile *);
    int (*policy)(VsbHandle *,const VsEventPolicy *);
    int (*state)(VsbHandle *,VsTelemetry *);
    unsigned (*control_size)(void);
    void (*modules)(float *,unsigned);
    void (*perf_reset)(void);void (*perf_write)(const char *);
} Api;

static void put16(FILE *f,unsigned v) {
    unsigned char b[2]={(unsigned char)v,(unsigned char)(v>>8)};
    fwrite(b,1,2,f);
}
static void put32(FILE *f,unsigned v) {put16(f,v&65535);put16(f,v>>16);}
static FILE *wave(const wchar_t *path,unsigned frames) {
    FILE *f=_wfopen(path,L"wb");if(!f)return NULL;
    fwrite("RIFF",1,4,f);put32(f,36+frames*8);fwrite("WAVEfmt ",1,8,f);
    put32(f,16);put16(f,3);put16(f,2);put32(f,48000);put32(f,384000);
    put16(f,8);put16(f,32);fwrite("data",1,4,f);put32(f,frames*8);return f;
}
static float ramp(double t,double begin,double end,float a,float b) {
    double u=(t-begin)/(end-begin);if(u<0)u=0;if(u>1)u=1;
    u=u*u*(3-2*u);return a+(b-a)*(float)u;
}
static int driving(const wchar_t *scene) {
    return !wcscmp(scene,L"startup")||!wcscmp(scene,L"brake")||
           !wcscmp(scene,L"shift")||!wcscmp(scene,L"stop")||!wcscmp(scene,L"full")||!wcscmp(scene,L"restart");
}
static void inputs(VsControl *c,const wchar_t *scene,double t) {
    c->ignition=1;c->throttle=0;c->brake=0;c->load=0;
    if(!wcscmp(scene,L"startup")){c->brake=.65f;return;}
    if(!wcscmp(scene,L"restart")){
        c->brake=.65f;c->ignition=t<.7||(t>=2&&t<5)||(t>=6.5&&t<10)||t>=11.5;
        c->start_id=t<2?1:t<6.5?2:t<11.5?3:4;return;
    }
    if(!wcscmp(scene,L"idle")){c->rpm=850;return;}
    if(!wcscmp(scene,L"acceleration")){
        c->rpm=ramp(t,1,8,850,8000);c->load=.9f;c->throttle=.85f;return;
    }
    if(!wcscmp(scene,L"cruise")){c->rpm=3200;c->load=.35f;c->throttle=.3f;return;}
    if(!wcscmp(scene,L"high")){c->rpm=8500;c->load=.95f;c->throttle=.95f;return;}
    if(!wcscmp(scene,L"lift")){
        c->rpm=ramp(t,2,8,6000,1800);c->throttle=t<2?.85f:0;
        c->load=t<2?.85f:0;return;
    }
    if(!wcscmp(scene,L"brake")){c->throttle=t<1?.8f:0;c->brake=t<1?0:.8f;return;}
    if(!wcscmp(scene,L"shift")){
        c->throttle=.8f;c->gear=t<2?1:t<5?2:t<8?3:2;return;
    }
    if(!wcscmp(scene,L"events")){
        c->rpm=5625;c->load=.65f;c->throttle=.7f;return;
    }
    if(!wcscmp(scene,L"stop")){c->ignition=t<2;c->brake=.65f;return;}
    if(!wcscmp(scene,L"full")){
        c->ignition=t<31;c->automatic=1;c->gear=1;
        c->throttle=t<4?0:t<17?.85f:t<19?.5f:t<23?0:t<27?.65f:0;
        c->brake=t<4?.65f:t<20?0:t<23?.5f:t<27?0:.7f;return;
    }
}
int wmain(int argc,wchar_t **argv) {
    HMODULE module;Api a={0};VsbHandle *engine;VsControl c;VsTelemetry state={0};
    float audio[2048],stems[1024*23],modules[1024*20];unsigned total,block,frame=0,n,k,warm=0;
    FILE *wav=NULL,*raw=NULL,*csv=NULL,*mod=NULL;wchar_t path[4096];
    LARGE_INTEGER frequency,begin,end;ULONG64 cy0,cy1,cycles=0;
    double seconds=0,maximum=0,peak=0,squares=0;int silent_output;
    if(argc!=7){fwprintf(stderr,L"render_cases DLL SCENE SECONDS BLOCK OUT.wav|none STEMS(0|1)\n");return 2;}
    total=(unsigned)(_wtof(argv[3])*48000);block=(unsigned)_wtoi(argv[4]);
    if(!total||total>48000*120||!block||block>1024)return 2;
    module=LoadLibraryW(argv[1]);if(!module)return 3;
#define LOAD(field,name) do {FARPROC p=GetProcAddress(module,"vsl_source_" name); \
    if(!p)return 4;memcpy(&a.field,&p,sizeof p);}while(0)
    LOAD(open,"open");LOAD(close,"close");LOAD(controls,"controls");LOAD(set,"set");
    LOAD(process,"process");LOAD(profile,"event_profile");LOAD(policy,"event_policy_set");
    LOAD(state,"state");LOAD(control_size,"control_size");
    LOAD(modules,"modules");LOAD(perf_reset,"perf_reset");LOAD(perf_write,"perf_write");
#undef LOAD
    if(a.control_size()!=sizeof c){fprintf(stderr,"control ABI mismatch\n");return 4;}
    engine=a.open(0);if(!engine||!a.controls(engine,&c))return 5;
    if(!a.profile(engine,ES_AFTERFIRE,&vsl_reference_afterfire_G_v3))return 6;
    {
        VsEventPolicy p={6,10,.018f,.04f,.11f,.97f,1,.35f,.025f,0};
        if(!a.policy(engine,&p))return 6;
    }
    c.mode=driving(argv[2])?VS_PEDALS:VS_BENCH;c.start_id=1;
    c.gear=0;c.automatic=0;c.backfire=1;
    c.events.enabled=1;c.events.gain=.7f;c.events.levels[ES_AFTERFIRE]=.8f;
    c.startup_gain=.5f;c.mechanical_gain=1;
    if(getenv("VSL_AIR"))c.dna.air=(float)atof(getenv("VSL_AIR"));
    if(getenv("VSL_LINE"))c.dna.line=(float)atof(getenv("VSL_LINE"));
    if(getenv("VSL_MECHANICAL"))c.mechanical_gain=(float)atof(getenv("VSL_MECHANICAL"));
    inputs(&c,argv[2],0);
    if(!a.set(engine,&c))return 7;
    if(wcscmp(argv[2],L"startup")&&wcscmp(argv[2],L"full")&&wcscmp(argv[2],L"restart")){
        unsigned warm_frames=(!wcscmp(argv[2],L"brake")||!wcscmp(argv[2],L"shift"))?48000*8:48000*3;
        if(driving(argv[2])){c.gear=1;c.throttle=.8f;c.brake=0;if(!a.set(engine,&c))return 7;}
        for(warm=0;warm<warm_frames;warm+=240)if(!a.process(engine,audio,NULL,240))return 8;
        inputs(&c,argv[2],0);if(!a.set(engine,&c))return 7;
    }
    silent_output=!wcscmp(argv[5],L"none");
    if(!silent_output){
        wav=wave(argv[5],total);if(!wav)return 9;
        if(_wtoi(argv[6])){swprintf(path,4096,L"%s.stems.f32",argv[5]);raw=_wfopen(path,L"wb");if(!raw)return 9;}
        if(_wtoi(argv[6])){swprintf(path,4096,L"%s.modules.f32",argv[5]);mod=_wfopen(path,L"wb");}
        swprintf(path,4096,L"%s.blocks.csv",argv[5]);csv=_wfopen(path,L"wb");if(!csv)return 9;
        fprintf(csv,"frame,frames,seconds,thread_cycles,rpm,speed_mps,lifecycle,operating,gear,event_started,event_active\n");
    }
    a.perf_reset();
    QueryPerformanceFrequency(&frequency);
    while(frame<total){
        unsigned outer=total-frame<block?total-frame:block,offset=0;
        QueryThreadCycleTime(GetCurrentThread(),&cy0);QueryPerformanceCounter(&begin);
        while(offset<outer){
            unsigned at=frame+offset,boundary=240-at%240;
            if(at%240==0){
                inputs(&c,argv[2],at/48000.);
                if(getenv("VSL_AIR_SWEEP"))c.dna.air=at<48000*5?1:at<48000*10?0:at<48000*15?.3f:1;
                if(!a.set(engine,&c))return 10;
                if(!wcscmp(argv[2],L"events")&&at%12000==0){
                    for(k=0;k<4;++k){c.events.manual_type=ES_AFTERFIRE;++c.events.manual_sequence;if(!a.set(engine,&c))return 10;}
                }
            }
            n=outer-offset;if(n>boundary)n=boundary;
            if(!a.process(engine,audio+2*offset,_wtoi(argv[6])?stems+23*offset:NULL,n))return 11;
            if(mod)a.modules(modules+20*offset,n);
            offset+=n;
        }
        QueryPerformanceCounter(&end);QueryThreadCycleTime(GetCurrentThread(),&cy1);
        {
            double dt=(double)(end.QuadPart-begin.QuadPart)/frequency.QuadPart;
            seconds+=dt;cycles+=cy1-cy0;if(dt>maximum)maximum=dt;
            if(!a.state(engine,&state))return 13;
            if(csv)fprintf(csv,"%u,%u,%.12g,%llu,%.9g,%.9g,%d,%d,%d,%u,%u\n",frame,outer,dt,
                (unsigned long long)(cy1-cy0),state.rpm,state.speed_mps,state.lifecycle,state.operating,state.gear,state.event_started,state.event_active);
        }
        for(k=0;k<2*outer;++k){double x=audio[k];if(!isfinite(x))return 12;if(fabs(x)>peak)peak=fabs(x);squares+=x*x;}
        if(wav)fwrite(audio,sizeof(float),outer*2,wav);
        if(raw)fwrite(stems,sizeof(float),outer*23,raw);
        if(mod)fwrite(modules,sizeof(float),outer*20,mod);
        frame+=outer;
    }
    if(mod)fclose(mod);if(wav)fclose(wav);if(raw)fclose(raw);if(csv)fclose(csv);
    wprintf(L"{\"scene\":\"%s\",\"frames\":%u,\"block\":%u,\"warmup_frames\":%u,\"process_seconds\":%.12g,\"thread_cycles\":%llu,\"maximum_block_ms\":%.12g,\"peak_FS\":%.12g,\"rms_FS\":%.12g,\"rpm\":%.9g,\"shifts\":%u,\"event_started\":%u,\"event_peak\":%u}\n",
        argv[2],total,block,warm,seconds,(unsigned long long)cycles,maximum*1000,peak,sqrt(squares/(2*total)),state.rpm,state.shifts,state.event_started,state.event_peak);
    a.perf_write(getenv("VSL_PERF_FILE"));a.close(engine);FreeLibrary(module);return 0;
}

