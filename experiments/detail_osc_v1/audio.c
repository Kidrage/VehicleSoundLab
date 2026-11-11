/* waveOut event/queue lifecycle follows the separately frozen reference preview.
   DSP callback and control state are specific to this detail-preserving model. */
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
    DeAudio *a=context;HWAVEOUT device=NULL;HANDLE event=NULL,scheduling=NULL;DWORD index=0;
    WAVEHDR headers[QUEUE]={0};float pcm[QUEUE][BLOCK*2];double x[BLOCK];
    WAVEFORMATEX format={WAVE_FORMAT_IEEE_FLOAT,2,48000,384000,8,32,0};
    LARGE_INTEGER frequency,start,now,first_submit={0};MMRESULT result=0;unsigned prepared=0,i,fade=0;int finished=0;
    DeStats stats={0};stats.raw_hash=UINT64_C(14695981039346656037);stats.min_gain=1;
    QueryPerformanceFrequency(&frequency);QueryPerformanceCounter(&start);
    format.nSamplesPerSec=a->model->rate;format.nAvgBytesPerSec=a->model->rate*8;
    event=CreateEventW(NULL,FALSE,FALSE,NULL);if(!event){lstrcpyW(stats.error,L"Audio event unavailable");goto cleanup;}
    result=waveOutOpen(&device,WAVE_MAPPER,&format,(DWORD_PTR)event,0,CALLBACK_EVENT);
    if(result)goto failed;stats.opened=1;
    scheduling=AvSetMmThreadCharacteristicsW(L"Audio",&index);if(scheduling)AvSetMmThreadPriority(scheduling,AVRT_PRIORITY_HIGH);
    for(i=0;i<QUEUE;++i){headers[i].lpData=(LPSTR)pcm[i];headers[i].dwBufferLength=sizeof pcm[i];
        result=waveOutPrepareHeader(device,&headers[i],sizeof headers[i]);if(result)goto failed;++prepared;}
    while(1) {
        int pending=0;
        if(!finished&&stats.blocks>=QUEUE){int empty=1;for(i=0;i<QUEUE;++i)if(headers[i].dwFlags&WHDR_INQUEUE)empty=0;if(empty)++stats.queue_empty;}
        for(i=0;i<QUEUE&&!finished;++i)if(!(headers[i].dwFlags&WHDR_INQUEUE)) {
            unsigned j,c,n;LARGE_INTEGER before,after;double elapsed;
            de_set(&a->player,InterlockedCompareExchange(&a->pitch_milli,0,0)/1000.,
                   pow(10,InterlockedCompareExchange(&a->level_db,0,0)/20.),InterlockedCompareExchange(&a->loop,0,0));
            QueryPerformanceCounter(&before);n=de_process(&a->player,x,BLOCK);QueryPerformanceCounter(&after);
            elapsed=(after.QuadPart-before.QuadPart)*1000./frequency.QuadPart;
            if(!n){finished=1;break;}
            for(j=0;j<n;++j) {
                double stop_gain=1;float raw=(float)x[j];
                if(InterlockedCompareExchange(&a->stop,0,0)){if(fade<480)++fade;stop_gain=1-fade/480.;}
                for(c=0;c<2;++c){stats.raw_hash=hash_float(stats.raw_hash,raw);pcm[i][j*2+c]=a->muted?0:(float)(raw*stop_gain);}
            }
            headers[i].dwBufferLength=n*8;result=waveOutWrite(device,&headers[i],sizeof headers[i]);if(result)goto failed;
            if(!stats.blocks)QueryPerformanceCounter(&first_submit);
            stats.frames+=n;++stats.blocks;stats.render_ms_total+=elapsed;stats.render_ms_max=fmax(stats.render_ms_max,elapsed);
            stats.max_pitch=fmax(stats.max_pitch,a->player.pitch);stats.min_gain=fmin(stats.min_gain,a->player.gain);
            stats.loops=a->player.loops;stats.position=a->player.position;
            EnterCriticalSection(&a->lock);a->stats=stats;LeaveCriticalSection(&a->lock);
            if((!a->player.loop&&a->player.position>=a->model->frames)||fade>=480)finished=1;
        }
        for(i=0;i<prepared;++i)pending|=(headers[i].dwFlags&WHDR_INQUEUE)!=0;
        if(finished&&!pending)break;
        WaitForSingleObject(event,20);
    }
    goto cleanup;
failed:waveOutGetErrorTextW(result,stats.error,256);
cleanup:
    if(device){MMTIME time={0};time.wType=TIME_SAMPLES;
        if(waveOutGetPosition(device,&time,sizeof time)==MMSYSERR_NOERROR){
            if(time.wType==TIME_SAMPLES)stats.device_seconds=time.u.sample/(double)a->model->rate;
            else if(time.wType==TIME_BYTES)stats.device_seconds=time.u.cb/(double)(a->model->rate*8);
            else if(time.wType==TIME_MS)stats.device_seconds=time.u.ms/1000.;}
        waveOutReset(device);for(i=0;i<prepared;++i)waveOutUnprepareHeader(device,&headers[i],sizeof headers[i]);waveOutClose(device);}
    QueryPerformanceCounter(&now);stats.wall_seconds=(now.QuadPart-start.QuadPart)/(double)frequency.QuadPart;
    if(first_submit.QuadPart){stats.startup_seconds=(first_submit.QuadPart-start.QuadPart)/(double)frequency.QuadPart;
        stats.playback_wall_seconds=(now.QuadPart-first_submit.QuadPart)/(double)frequency.QuadPart;}
    if(scheduling)AvRevertMmThreadCharacteristics(scheduling);if(event)CloseHandle(event);
    EnterCriticalSection(&a->lock);a->stats=stats;LeaveCriticalSection(&a->lock);InterlockedExchange(&a->running,0);return 0;
}
void de_audio_init(DeAudio *a,const DoModel *m,int muted) {
    ZeroMemory(a,sizeof *a);InitializeCriticalSection(&a->lock);a->model=m;a->muted=muted;a->pitch_milli=1000;
}
void de_audio_controls(DeAudio *a,int pitch,int level,int loop) {
    if(pitch>=900&&pitch<=1100)InterlockedExchange(&a->pitch_milli,pitch);
    if(level>=-12&&level<=0)InterlockedExchange(&a->level_db,level);
    if(loop==0||loop==1)InterlockedExchange(&a->loop,loop);
}
int de_audio_start(DeAudio *a) {
    de_audio_stop(a);
    if(!de_init(&a->player,a->model,a->pitch_milli/1000.,pow(10,a->level_db/20.),a->loop))return 0;
    EnterCriticalSection(&a->lock);ZeroMemory(&a->stats,sizeof a->stats);LeaveCriticalSection(&a->lock);
    a->stop=0;a->running=1;a->thread=CreateThread(NULL,0,worker,a,0,NULL);if(!a->thread){a->running=0;return 0;}return 1;
}
void de_audio_stop(DeAudio *a) {
    if(a->thread){InterlockedExchange(&a->stop,1);WaitForSingleObject(a->thread,INFINITE);CloseHandle(a->thread);a->thread=NULL;}
}
void de_audio_destroy(DeAudio *a){de_audio_stop(a);DeleteCriticalSection(&a->lock);}
DeStats de_audio_stats(DeAudio *a){DeStats s;EnterCriticalSection(&a->lock);s=a->stats;LeaveCriticalSection(&a->lock);return s;}
