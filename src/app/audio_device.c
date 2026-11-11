#include "audio_device.h"
#include "core/character.h"
#include <mmsystem.h>
#include <avrt.h>
#include <stdlib.h>
#include <math.h>
#define BLOCK VSL_DEVICE_BLOCK
#define QUEUE 4
static DWORD WINAPI audio_thread(LPVOID context) {
    VslAudio*a=(VslAudio*)context;
    HANDLE completed=CreateEventW(NULL,FALSE,FALSE,NULL),scheduling=NULL;DWORD task_index=0;
    HWAVEOUT device=NULL; WAVEHDR headers[QUEUE]={0}; short pcm[QUEUE][BLOCK*2];
    WAVEFORMATEX format={WAVE_FORMAT_PCM,2,48000,192000,4,16,0};
    MMRESULT result; unsigned i,prepared=0,fade_frames=0; float buffer[BLOCK*2];
    LARGE_INTEGER frequency,worker_start;QueryPerformanceFrequency(&frequency);QueryPerformanceCounter(&worker_start);
    if(!completed) { lstrcpyW(a->error,L"Audio completion event unavailable");InterlockedExchange(&a->running,0);return 1; }
    result=waveOutOpen(&device,WAVE_MAPPER,&format,(DWORD_PTR)completed,0,CALLBACK_EVENT);
    if(result!=MMSYSERR_NOERROR) {
        waveOutGetErrorTextW(result,a->error,256);CloseHandle(completed);InterlockedExchange(&a->running,0);return 1;
    }
    scheduling=AvSetMmThreadCharacteristicsW(L"Audio",&task_index);
    if(scheduling)AvSetMmThreadPriority(scheduling,AVRT_PRIORITY_HIGH);
    for(i=0;i<QUEUE;++i) {
        headers[i].lpData=(LPSTR)pcm[i]; headers[i].dwBufferLength=sizeof pcm[i];
        result=waveOutPrepareHeader(device,&headers[i],sizeof(WAVEHDR));
        if(result)goto failed; ++prepared;
    }
    while(!InterlockedCompareExchange(&a->stop,0,0)) {
        if(a->rendered_blocks>=QUEUE) {
            int empty=1;for(i=0;i<QUEUE;++i)if(headers[i].dwFlags&WHDR_INQUEUE)empty=0;
            if(empty)++a->queue_empty_observations;
        }
        for(i=0;i<QUEUE;++i) {
            if(!(headers[i].dwFlags&WHDR_INQUEUE)) {
                VslParams p;unsigned j,n=BLOCK;LARGE_INTEGER before,after;double elapsed;
                EnterCriticalSection(&a->lock); p=a->params;LeaveCriticalSection(&a->lock);
                QueryPerformanceCounter(&before);
                if(a->take_mode==2) {
                    n=vsl_take_process(&a->player,a->engine,buffer,BLOCK,2,NULL);
                    if(!n)goto cleanup;
                } else {
                    vsl_set_params(a->engine,&p);
                    if(a->take_mode==1) {
                        if(a->take->frames>=VSL_TAKE_MAX_FRAMES) { a->take_limit=1;goto cleanup; }
                        if(VSL_TAKE_MAX_FRAMES-a->take->frames<n)n=(unsigned)(VSL_TAKE_MAX_FRAMES-a->take->frames);
                        if(!vsl_take_record(a->take,a->engine->frame,&a->engine->target)) { a->take_limit=2;goto cleanup; }
                    }
                    vsl_process(a->engine,buffer,n);
                }
                QueryPerformanceCounter(&after);elapsed=(after.QuadPart-before.QuadPart)*1000.0/frequency.QuadPart;
                for(j=0;j<n;++j) {
                    double gain=1;
                    if(a->take_mode==2&&InterlockedCompareExchange(&a->replay_fade,0,0)) {
                        if(fade_frames<2400)++fade_frames;gain=1-fade_frames/2400.;
                    }
                    pcm[i][2*j]=a->diagnostic_mute?0:(short)(buffer[2*j]*gain*32767);
                    pcm[i][2*j+1]=a->diagnostic_mute?0:(short)(buffer[2*j+1]*gain*32767);
                }
                headers[i].dwBufferLength=n*4;
                EnterCriticalSection(&a->lock);
                a->peak=a->engine->peak; a->rpm=a->engine->control.rpm; a->load=a->engine->control.load;
                a->state=a->engine->drive;
                a->actual_target=a->engine->target;
                a->voice=a->engine->voice;
                a->character_pressure_mix=a->engine->character.amount_pressure;
                a->character_structure_mix=a->engine->character.amount_structure;
                a->character_events=vsl_character_events(&a->engine->character);
                a->response_shape_mix=a->engine->response.amount;
                a->response_pressure_events=a->engine->response.pressure_events;
                a->event_color_mix=a->engine->color.amount;a->event_color_max_mod=a->engine->color.max_mod;
                a->event_color_events=a->engine->color.events[0]+a->engine->color.events[1];
                a->pulse_mix=a->engine->firing_source.mix;
                a->pulse_events=a->engine->firing_source.accepted[0]+a->engine->firing_source.accepted[1];
                a->pulse_overflow=a->engine->firing_source.kernel.overflow;
                a->propagation_mix=a->engine->spatial.propagation.mix;
                a->propagation_clamped_paths=a->engine->spatial.propagation.clamped_paths;
                a->render_ms_max=fmax(a->render_ms_max,elapsed);a->render_ms_total+=elapsed;++a->rendered_blocks;
                for(j=0;j<256;++j)a->scope[j]=buffer[2*(j*n/256)];
                LeaveCriticalSection(&a->lock);
                result=waveOutWrite(device,&headers[i],sizeof(WAVEHDR));
                if(result)goto failed;
                if(a->take_mode==1)vsl_take_commit(a->take,buffer,n);
                EnterCriticalSection(&a->lock);
                a->seconds+=n/48000.0;
                a->take_frames=a->take_mode==1?a->take->frames:a->engine->frame;
                a->take_events=a->take_mode==1?a->take->count:a->player.next;
                LeaveCriticalSection(&a->lock);
                if(a->take_mode==2&&a->engine->frame==a->take->frames) {
                    a->take_hash_match=a->player.audio_hash==a->take->audio_hash;
                    goto cleanup;
                }
            }
        }
        /* Buffer completion wakes immediately; no dependency on the desktop's
           timer resolution or occluded-window Sleep throttling. */
        WaitForSingleObject(completed,20);
    }
    goto cleanup;
failed:
    waveOutGetErrorTextW(result,a->error,256);
cleanup:
    /* Let queued blocks finish rather than truncating the waveform on Stop. */
    if(!result) {
        unsigned j;
        for(j=0;j<60;++j) {
            int pending=0;
            for(i=0;i<prepared;++i)pending|=(headers[i].dwFlags&WHDR_INQUEUE)!=0;
            if(!pending)break;WaitForSingleObject(completed,10);
        }
    }
    {
        MMTIME position={0};LARGE_INTEGER now;position.wType=TIME_SAMPLES;
        if(waveOutGetPosition(device,&position,sizeof position)==MMSYSERR_NOERROR) {
            if(position.wType==TIME_SAMPLES)a->device_seconds=position.u.sample/48000.;
            else if(position.wType==TIME_BYTES)a->device_seconds=position.u.cb/192000.;
            else if(position.wType==TIME_MS)a->device_seconds=position.u.ms/1000.;
        }
        QueryPerformanceCounter(&now);a->worker_wall_seconds=(now.QuadPart-worker_start.QuadPart)/(double)frequency.QuadPart;
    }
    waveOutReset(device);
    for(i=0;i<prepared;++i)waveOutUnprepareHeader(device,&headers[i],sizeof(WAVEHDR));
    waveOutClose(device);if(scheduling)AvRevertMmThreadCharacteristics(scheduling);CloseHandle(completed);
    InterlockedExchange(&a->running,0);return 0;
}
void vsl_audio_init(VslAudio*a) {
    ZeroMemory(a,sizeof *a); InitializeCriticalSection(&a->lock);
    a->engine=(VslEngine*)malloc(sizeof(VslEngine)); a->params=vsl_default_params(0);
    if(a->engine)vsl_init(a->engine,48000,48271);
}
int vsl_audio_start(VslAudio*a) {
    if(!a->engine)return 0;
    vsl_audio_stop(a);a->seconds=0;a->stop=0;a->running=1;a->error[0]=0;
    a->render_ms_max=a->render_ms_total=0;a->rendered_blocks=0;
    a->replay_fade=0;a->take_frames=0;a->take_events=0;a->take_limit=0;a->take_hash_match=0;
    a->worker_wall_seconds=a->device_seconds=0;a->queue_empty_observations=0;
    a->thread=CreateThread(NULL,0,audio_thread,a,0,NULL);
    if(!a->thread) { a->running=0; return 0; } return 1;
}
void vsl_audio_stop(VslAudio*a) {
    if(a->thread) {
        /* 18 ms release while the worker continues to consume blocks. */
        if(a->running) {
            EnterCriticalSection(&a->lock); a->params.master=0; LeaveCriticalSection(&a->lock);
            InterlockedExchange(&a->replay_fade,1);
            Sleep(65);
        }
        InterlockedExchange(&a->stop,1);
        WaitForSingleObject(a->thread,INFINITE); CloseHandle(a->thread); a->thread=NULL;
        if(a->take_mode==1)vsl_take_finish(a->take);
    }
}
void vsl_audio_destroy(VslAudio*a) { vsl_audio_stop(a); free(a->engine); DeleteCriticalSection(&a->lock); }
void vsl_audio_params(VslAudio*a,const VslParams*p,int drive) {
    EnterCriticalSection(&a->lock); a->params=*p; a->drive=drive; LeaveCriticalSection(&a->lock);
}
