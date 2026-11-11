/* Shared Windows stereo transport; no knowledge of engines, models or controls. */
#include "device.h"
#include <mmsystem.h>
#include <mmreg.h>
#include <avrt.h>
#include <math.h>
#include <string.h>
#define BLOCK 512
#define QUEUE 4
static DWORD WINAPI worker(LPVOID context) {
    WoDevice *d=context;
    WAVEFORMATEX format={WAVE_FORMAT_IEEE_FLOAT,2,48000,384000,8,32,0};
    WAVEHDR headers[QUEUE]={{0}};float pcm[QUEUE][BLOCK*2];
    HWAVEOUT device=NULL;HANDLE event=NULL,priority=NULL;DWORD task=0;
    LARGE_INTEGER hz,start,first,now;
    WoStats s={0};MMRESULT error=0;unsigned prepared=0,i;int finished=0,submitted=0;
    ULONGLONG progress=GetTickCount64();
    s.output_hash=UINT64_C(14695981039346656037);
    QueryPerformanceFrequency(&hz);QueryPerformanceCounter(&start);first=start;
    event=CreateEventW(NULL,FALSE,FALSE,NULL);
    if(!event){lstrcpyW(s.error,L"无法建立音频事件");goto done;}
    error=waveOutOpen(&device,WAVE_MAPPER,&format,(DWORD_PTR)event,0,CALLBACK_EVENT);
    if(error)goto failed;
    s.opened=1;
    priority=AvSetMmThreadCharacteristicsW(L"Audio",&task);
    if(priority)AvSetMmThreadPriority(priority,AVRT_PRIORITY_HIGH);
    for(i=0;i<QUEUE;++i) {
        headers[i].lpData=(LPSTR)pcm[i];headers[i].dwBufferLength=sizeof pcm[i];
        error=waveOutPrepareHeader(device,&headers[i],sizeof headers[i]);if(error)goto failed;++prepared;
    }
    for(;;) {
        int pending=0;
        if(!finished&&s.blocks>=QUEUE) {
            int empty=1;
            for(i=0;i<QUEUE;++i)if(headers[i].dwFlags&WHDR_INQUEUE)empty=0;
            if(empty)++s.queue_empty;
        }
        for(i=0;i<QUEUE&&!finished;++i)if(!(headers[i].dwFlags&WHDR_INQUEUE)) {
            unsigned n=BLOCK,j;LARGE_INTEGER before,after;double elapsed;int result;
            if(d->frame_limit&&d->frame_limit-s.frames<n)n=(unsigned)(d->frame_limit-s.frames);
            if(!n){finished=1;break;}
            QueryPerformanceCounter(&before);
            result=d->process(d->context,pcm[i],n,InterlockedCompareExchange(&d->stop,0,0)!=0);
            QueryPerformanceCounter(&after);
            if(result<0){lstrcpyW(s.error,L"音频生成失败");goto done;}
            elapsed=(after.QuadPart-before.QuadPart)*1000./hz.QuadPart;
            for(j=0;j<n*2;++j) {
                uint32_t bits;unsigned b;
                if(!isfinite(pcm[i][j])||fabs(pcm[i][j])>=1) {
                    lstrcpyW(s.error,L"输出超出余量，请降低电平");goto done;
                }
                s.peak=fmax(s.peak,fabs(pcm[i][j]));memcpy(&bits,&pcm[i][j],4);
                for(b=0;b<4;++b){s.output_hash^=(bits>>(8*b))&255u;s.output_hash*=UINT64_C(1099511628211);}
            }
            if(d->muted)memset(pcm[i],0,n*2*sizeof(float));
            headers[i].dwBufferLength=n*8;
            error=waveOutWrite(device,&headers[i],sizeof headers[i]);if(error)goto failed;
            if(!submitted) {
                QueryPerformanceCounter(&first);submitted=1;
                s.startup_seconds=(first.QuadPart-start.QuadPart)/(double)hz.QuadPart;
            }
            progress=GetTickCount64();s.frames+=n;++s.blocks;
            s.render_ms_total+=elapsed;s.render_ms_max=fmax(s.render_ms_max,elapsed);
            if(elapsed>n*1000./48000)++s.budget_exceeded;
            EnterCriticalSection(&d->lock);d->stats=s;LeaveCriticalSection(&d->lock);
            if(result>0||(d->frame_limit&&s.frames==d->frame_limit))finished=1;
        }
        for(i=0;i<prepared;++i)pending|=(headers[i].dwFlags&WHDR_INQUEUE)!=0;
        if(finished&&!pending)break;
        if(pending&&GetTickCount64()-progress>2000){lstrcpyW(s.error,L"音频设备超时");goto done;}
        WaitForSingleObject(event,20);
    }
    goto done;
failed:
    waveOutGetErrorTextW(error,s.error,256);
done:
    QueryPerformanceCounter(&now);
    if(submitted)s.playback_wall_seconds=(now.QuadPart-first.QuadPart)/(double)hz.QuadPart;
    if(device) {
        MMTIME position={0};position.wType=TIME_SAMPLES;
        if(waveOutGetPosition(device,&position,sizeof position)==MMSYSERR_NOERROR) {
            if(position.wType==TIME_SAMPLES)s.device_seconds=position.u.sample/48000.;
            else if(position.wType==TIME_BYTES)s.device_seconds=position.u.cb/384000.;
            else if(position.wType==TIME_MS)s.device_seconds=position.u.ms/1000.;
        }
        waveOutReset(device);
        for(i=0;i<prepared;++i)waveOutUnprepareHeader(device,&headers[i],sizeof headers[i]);
        waveOutClose(device);
    }
    if(priority)AvRevertMmThreadCharacteristics(priority);
    if(event)CloseHandle(event);
    EnterCriticalSection(&d->lock);d->stats=s;LeaveCriticalSection(&d->lock);
    InterlockedExchange(&d->running,0);return 0;
}
void wo_init(WoDevice *d,WoProcess process,void *context) {
    memset(d,0,sizeof *d);InitializeCriticalSection(&d->lock);d->process=process;d->context=context;
}
int wo_start(WoDevice *d,int muted,uint64_t limit) {
    if(!d||!d->process||(muted!=0&&muted!=1))return 0;
    wo_stop(d);d->muted=muted;d->frame_limit=limit;
    EnterCriticalSection(&d->lock);memset(&d->stats,0,sizeof d->stats);LeaveCriticalSection(&d->lock);
    InterlockedExchange(&d->stop,0);InterlockedExchange(&d->running,1);
    d->thread=CreateThread(NULL,0,worker,d,0,NULL);
    if(!d->thread){InterlockedExchange(&d->running,0);return 0;}return 1;
}
void wo_stop(WoDevice *d) {
    if(d->thread){InterlockedExchange(&d->stop,1);WaitForSingleObject(d->thread,INFINITE);CloseHandle(d->thread);d->thread=NULL;}
}
void wo_destroy(WoDevice *d) { wo_stop(d);DeleteCriticalSection(&d->lock); }
WoStats wo_stats(WoDevice *d) {
    WoStats s;EnterCriticalSection(&d->lock);s=d->stats;LeaveCriticalSection(&d->lock);return s;
}
