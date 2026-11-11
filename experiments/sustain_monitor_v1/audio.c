/* Event-driven waveOut lifecycle; frozen synthesis remains in sustain_osc_v1.
   No file I/O or allocation in this rendering worker. */
#include "audio.h"
#include <mmsystem.h>
#include <mmreg.h>
#include <avrt.h>
#include <math.h>
#include <string.h>
#define BLOCK 512
#define QUEUE 4
static uint64_t hash_float(uint64_t h,float value) {
    uint32_t bits;unsigned i;memcpy(&bits,&value,4);
    for(i=0;i<4;++i){h^=(bits>>(i*8))&255u;h*=UINT64_C(1099511628211);}return h;
}
static DWORD WINAPI worker(LPVOID context) {
    SmAudio *a=context;HWAVEOUT device=NULL;HANDLE event=NULL,scheduling=NULL;DWORD index=0;
    WAVEHDR headers[QUEUE]={0};float pcm[QUEUE][BLOCK*2],raw[BLOCK*2];
    WAVEFORMATEX format={WAVE_FORMAT_IEEE_FLOAT,2,48000,384000,8,32,0};
    LARGE_INTEGER frequency,start,now,first_submit={0};MMRESULT result=0;unsigned prepared=0,i;int finished=0;
    SmStats s={0};s.raw_hash=UINT64_C(14695981039346656037);s.min_pitch=2;s.min_detail=2;s.min_attenuation=2;
    QueryPerformanceFrequency(&frequency);QueryPerformanceCounter(&start);
    event=CreateEventW(NULL,FALSE,FALSE,NULL);if(!event){lstrcpyW(s.error,L"Audio event unavailable");goto cleanup;}
    result=waveOutOpen(&device,WAVE_MAPPER,&format,(DWORD_PTR)event,0,CALLBACK_EVENT);
    if(result)goto failed;s.opened=1;
    scheduling=AvSetMmThreadCharacteristicsW(L"Audio",&index);if(scheduling)AvSetMmThreadPriority(scheduling,AVRT_PRIORITY_HIGH);
    for(i=0;i<QUEUE;++i){headers[i].lpData=(LPSTR)pcm[i];headers[i].dwBufferLength=sizeof pcm[i];
        result=waveOutPrepareHeader(device,&headers[i],sizeof headers[i]);if(result)goto failed;++prepared;}
    while(1) {
        int pending=0;
        if(!finished&&s.blocks>=QUEUE){int empty=1;for(i=0;i<QUEUE;++i)if(headers[i].dwFlags&WHDR_INQUEUE)empty=0;if(empty)++s.queue_empty;}
        for(i=0;i<QUEUE&&!finished;++i)if(!(headers[i].dwFlags&WHDR_INQUEUE)) {
            unsigned n=BLOCK,j;LARGE_INTEGER before,after;double elapsed;
            if(a->frame_limit&&a->frame_limit-s.frames<n)n=(unsigned)(a->frame_limit-s.frames);
            if(!n){finished=1;break;}
            sm_render_set(&a->render,InterlockedCompareExchange(&a->pitch,0,0),
                InterlockedCompareExchange(&a->detail,0,0),InterlockedCompareExchange(&a->db,0,0));
            QueryPerformanceCounter(&before);
            sm_render_process(&a->render,raw,pcm[i],n,InterlockedCompareExchange(&a->stop,0,0)!=0);
            QueryPerformanceCounter(&after);elapsed=(after.QuadPart-before.QuadPart)*1000./frequency.QuadPart;
            for(j=0;j<n*2;++j){s.raw_hash=hash_float(s.raw_hash,raw[j]);s.peak=fmax(s.peak,fabs(pcm[i][j]));}
            if(a->capture&&s.frames+n<=a->capture_frames)memcpy(a->capture+s.frames*2,pcm[i],n*2*sizeof(float));
            if(a->muted)memset(pcm[i],0,n*2*sizeof(float));
            headers[i].dwBufferLength=n*8;result=waveOutWrite(device,&headers[i],sizeof headers[i]);if(result)goto failed;
            if(!s.blocks)QueryPerformanceCounter(&first_submit);
            s.frames+=n;++s.blocks;s.render_ms_total+=elapsed;s.render_ms_max=fmax(s.render_ms_max,elapsed);
            s.min_pitch=fmin(s.min_pitch,a->render.source.pitch);s.max_pitch=fmax(s.max_pitch,a->render.source.pitch);
            s.min_detail=fmin(s.min_detail,a->render.source.amount);s.max_detail=fmax(s.max_detail,a->render.source.amount);
            s.min_attenuation=fmin(s.min_attenuation,a->render.attenuation);
            EnterCriticalSection(&a->lock);a->stats=s;LeaveCriticalSection(&a->lock);
            if((a->frame_limit&&s.frames==a->frame_limit)||a->render.release>=480)finished=1;
        }
        for(i=0;i<prepared;++i)pending|=(headers[i].dwFlags&WHDR_INQUEUE)!=0;
        if(finished&&!pending)break;
        WaitForSingleObject(event,20);
    }
    goto cleanup;
failed:waveOutGetErrorTextW(result,s.error,256);
cleanup:
    if(device){MMTIME time={0};time.wType=TIME_SAMPLES;
        if(waveOutGetPosition(device,&time,sizeof time)==MMSYSERR_NOERROR){
            if(time.wType==TIME_SAMPLES)s.device_seconds=time.u.sample/48000.;
            else if(time.wType==TIME_BYTES)s.device_seconds=time.u.cb/384000.;
            else if(time.wType==TIME_MS)s.device_seconds=time.u.ms/1000.;}
        waveOutReset(device);for(i=0;i<prepared;++i)waveOutUnprepareHeader(device,&headers[i],sizeof headers[i]);waveOutClose(device);}
    QueryPerformanceCounter(&now);s.wall_seconds=(now.QuadPart-start.QuadPart)/(double)frequency.QuadPart;
    if(first_submit.QuadPart){s.startup_seconds=(first_submit.QuadPart-start.QuadPart)/(double)frequency.QuadPart;
        s.playback_wall_seconds=(now.QuadPart-first_submit.QuadPart)/(double)frequency.QuadPart;}
    if(scheduling)AvRevertMmThreadCharacteristics(scheduling);if(event)CloseHandle(event);
    EnterCriticalSection(&a->lock);a->stats=s;LeaveCriticalSection(&a->lock);InterlockedExchange(&a->running,0);return 0;
}
void sm_audio_init(SmAudio *a,const SuModel *m,int muted) {
    ZeroMemory(a,sizeof *a);InitializeCriticalSection(&a->lock);a->model=m;a->muted=muted;a->pitch=1000;a->detail=1000;
}
void sm_audio_controls(SmAudio *a,int pitch,int detail,int db) {
    if(pitch>=900&&pitch<=1100)InterlockedExchange(&a->pitch,pitch);
    if(detail>=0&&detail<=1000)InterlockedExchange(&a->detail,detail);
    if(db>=-18&&db<=0)InterlockedExchange(&a->db,db);
}
int sm_audio_start(SmAudio *a) {
    sm_audio_stop(a);
    if(!sm_render_init(&a->render,a->model,a->pitch,a->detail,a->db))return 0;
    EnterCriticalSection(&a->lock);ZeroMemory(&a->stats,sizeof a->stats);LeaveCriticalSection(&a->lock);
    a->stop=0;a->running=1;a->thread=CreateThread(NULL,0,worker,a,0,NULL);if(!a->thread){a->running=0;return 0;}return 1;
}
void sm_audio_stop(SmAudio *a) {
    if(a->thread){InterlockedExchange(&a->stop,1);WaitForSingleObject(a->thread,INFINITE);CloseHandle(a->thread);a->thread=NULL;}
}
void sm_audio_destroy(SmAudio *a){sm_audio_stop(a);DeleteCriticalSection(&a->lock);}
SmStats sm_audio_stats(SmAudio *a){SmStats s;EnterCriticalSection(&a->lock);s=a->stats;LeaveCriticalSection(&a->lock);return s;}
