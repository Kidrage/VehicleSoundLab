/* Device lifecycle and control snapshots; synthesis stays in the portable modules.
   The worker owns all render state. UI never holds the lock during I/O/waits. */
#include "audio.h"
#include <mmsystem.h>
#include <mmreg.h>
#include <avrt.h>
#include <math.h>
#include <string.h>
#define BLOCK 512
#define QUEUE 4

static uint64_t hash_float(uint64_t h, float x) {
    uint32_t bits; unsigned i;
    memcpy(&bits, &x, 4);
    for (i = 0; i < 4; ++i) { h ^= (bits >> (i * 8)) & 255u; h *= UINT64_C(1099511628211); }
    return h;
}

static DWORD WINAPI worker(LPVOID context) {
    SaAudio *a = context;
    HWAVEOUT device = NULL; HANDLE event = NULL, scheduling = NULL; DWORD index = 0;
    WAVEHDR headers[QUEUE] = {{0}};
    float pcm[QUEUE][BLOCK * 2], dna[BLOCK * 2], low[BLOCK * 2];
    SmoCapture capture = {dna, low, NULL, NULL};
    WAVEFORMATEX format = {WAVE_FORMAT_IEEE_FLOAT, 2, 48000, 384000, 8, 32, 0};
    LARGE_INTEGER frequency, start, now; MMRESULT result = 0;
    unsigned prepared = 0, i; int finished = 0; uint64_t adopted = UINT64_MAX;
    ULONGLONG last_progress = GetTickCount64();
    SaStats s = {0};
    s.dna_hash = s.low_hash = s.output_hash = UINT64_C(14695981039346656037);
    QueryPerformanceFrequency(&frequency); QueryPerformanceCounter(&start);
    event = CreateEventW(NULL, FALSE, FALSE, NULL);
    if (!event) { lstrcpyW(s.error, L"无法建立音频事件"); goto cleanup; }
    result = waveOutOpen(&device, WAVE_MAPPER, &format, (DWORD_PTR)event, 0, CALLBACK_EVENT);
    if (result) goto failed;
    s.opened = 1;
    scheduling = AvSetMmThreadCharacteristicsW(L"Audio", &index);
    if (scheduling) AvSetMmThreadPriority(scheduling, AVRT_PRIORITY_HIGH);
    for (i = 0; i < QUEUE; ++i) {
        headers[i].lpData = (LPSTR)pcm[i]; headers[i].dwBufferLength = sizeof pcm[i];
        result = waveOutPrepareHeader(device, &headers[i], sizeof headers[i]);
        if (result) goto failed;
        ++prepared;
    }
    for (;;) {
        int pending = 0;
        if (!finished && s.blocks >= QUEUE) {
            int empty = 1;
            for (i = 0; i < QUEUE; ++i) if (headers[i].dwFlags & WHDR_INQUEUE) empty = 0;
            if (empty) ++s.queue_empty;
        }
        for (i = 0; i < QUEUE && !finished; ++i) if (!(headers[i].dwFlags & WHDR_INQUEUE)) {
            unsigned n = BLOCK, j; uint64_t generation; SmoControl control;
            LARGE_INTEGER before, after; double elapsed; int stop;
            if (a->frame_limit && a->frame_limit - s.frames < n) n = (unsigned)(a->frame_limit - s.frames);
            if (!n) { finished = 1; break; }
            EnterCriticalSection(&a->lock);
            control = a->control; generation = a->generation;
            LeaveCriticalSection(&a->lock);
            if (generation != adopted) {
                if (!smo_render_set(&a->render, &control)) { lstrcpyW(s.error, L"监听参数无效"); goto cleanup; }
                if (a->trace_count < SA_TRACE_CAPACITY) {
                    a->trace[a->trace_count].frame = s.frames;
                    a->trace[a->trace_count++].control = control;
                } else ++s.trace_overflow;
                adopted = generation; ++s.changes;
            }
            stop = InterlockedCompareExchange(&a->stop, 0, 0) != 0;
            if (stop && a->stop_frame == UINT64_MAX) a->stop_frame = s.frames;
            QueryPerformanceCounter(&before);
            if (!smo_render_process(&a->render, pcm[i], n, stop, &capture)) { lstrcpyW(s.error, L"监听渲染失败"); goto cleanup; }
            QueryPerformanceCounter(&after);
            elapsed = (after.QuadPart - before.QuadPart) * 1000. / frequency.QuadPart;
            for (j = 0; j < n * 2; ++j) {
                if (!isfinite(pcm[i][j]) || fabs(pcm[i][j]) >= 1) { lstrcpyW(s.error, L"输出超出余量，请降低电平"); goto cleanup; }
                s.dna_hash = hash_float(s.dna_hash, dna[j]); s.low_hash = hash_float(s.low_hash, low[j]);
                s.output_hash = hash_float(s.output_hash, pcm[i][j]); s.peak = fmax(s.peak, fabs(pcm[i][j]));
            }
            if (a->capture && s.frames + n <= a->capture_frames) memcpy(a->capture + s.frames * 2, pcm[i], n * 2 * sizeof(float));
            if (a->muted) memset(pcm[i], 0, n * 2 * sizeof(float));
            headers[i].dwBufferLength = n * 8;
            result = waveOutWrite(device, &headers[i], sizeof headers[i]);
            if (result) goto failed;
            last_progress = GetTickCount64();
            s.frames += n; ++s.blocks;
            s.render_ms_total += elapsed; s.render_ms_max = fmax(s.render_ms_max, elapsed);
            EnterCriticalSection(&a->lock); a->stats = s; LeaveCriticalSection(&a->lock);
            if ((a->frame_limit && s.frames == a->frame_limit) || a->render.release == 480) finished = 1;
        }
        for (i = 0; i < prepared; ++i) pending |= (headers[i].dwFlags & WHDR_INQUEUE) != 0;
        if (finished && !pending) break;
        if (pending && GetTickCount64() - last_progress > 2000) {
            lstrcpyW(s.error, L"音频设备超时，已停止监听"); goto cleanup;
        }
        WaitForSingleObject(event, 20);
    }
    goto cleanup;
failed:
    waveOutGetErrorTextW(result, s.error, 256);
cleanup:
    if (device) {
        MMTIME position = {0}; position.wType = TIME_SAMPLES;
        if (waveOutGetPosition(device, &position, sizeof position) == MMSYSERR_NOERROR) {
            if (position.wType == TIME_SAMPLES) s.device_seconds = position.u.sample / 48000.;
            else if (position.wType == TIME_BYTES) s.device_seconds = position.u.cb / 384000.;
            else if (position.wType == TIME_MS) s.device_seconds = position.u.ms / 1000.;
        }
        waveOutReset(device);
        for (i = 0; i < prepared; ++i) waveOutUnprepareHeader(device, &headers[i], sizeof headers[i]);
        waveOutClose(device);
    }
    QueryPerformanceCounter(&now); s.wall_seconds = (now.QuadPart - start.QuadPart) / (double)frequency.QuadPart;
    if (scheduling) AvRevertMmThreadCharacteristics(scheduling);
    if (event) CloseHandle(event);
    EnterCriticalSection(&a->lock); a->stats = s; LeaveCriticalSection(&a->lock);
    InterlockedExchange(&a->running, 0);
    return 0;
}

void sa_audio_init(SaAudio *a, const DsSceneConfig *config, const SmoControl *control, int muted) {
    memset(a, 0, sizeof *a); InitializeCriticalSection(&a->lock);
    a->config = *config; a->control = *control; a->muted = muted;
}
int sa_audio_controls(SaAudio *a, const SmoControl *control) {
    if (!smo_control_valid(control)) return 0;
    EnterCriticalSection(&a->lock); a->control = *control; ++a->generation; LeaveCriticalSection(&a->lock);
    return 1;
}
SmoControl sa_audio_control(SaAudio *a) {
    SmoControl control; EnterCriticalSection(&a->lock); control = a->control; LeaveCriticalSection(&a->lock); return control;
}
int sa_audio_start(SaAudio *a) {
    SmoControl control;
    sa_audio_stop(a); control = sa_audio_control(a);
    if (!smo_render_init(&a->render, &a->spatial, &a->config, &control)) return 0;
    EnterCriticalSection(&a->lock); memset(&a->stats, 0, sizeof a->stats); LeaveCriticalSection(&a->lock);
    a->trace_count = 0; a->stop_frame = UINT64_MAX;
    InterlockedExchange(&a->stop, 0); InterlockedExchange(&a->running, 1);
    a->thread = CreateThread(NULL, 0, worker, a, 0, NULL);
    if (!a->thread) { InterlockedExchange(&a->running, 0); return 0; }
    return 1;
}
void sa_audio_stop(SaAudio *a) {
    if (a->thread) {
        InterlockedExchange(&a->stop, 1);
        WaitForSingleObject(a->thread, INFINITE);
        CloseHandle(a->thread); a->thread = NULL;
    }
}
void sa_audio_destroy(SaAudio *a) { sa_audio_stop(a); DeleteCriticalSection(&a->lock); }
SaStats sa_audio_stats(SaAudio *a) {
    SaStats s; EnterCriticalSection(&a->lock); s = a->stats; LeaveCriticalSection(&a->lock); return s;
}
