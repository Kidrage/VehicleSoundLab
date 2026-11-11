#ifndef VSL_WIN_OUTPUT_DEVICE_H
#define VSL_WIN_OUTPUT_DEVICE_H
#include <windows.h>
#include <stdint.h>
/* Return -1 for error,0 to continue,1 when this rendered block finishes transport.
   Worker calls exactly once per submitted block before optional device mute. */
typedef int (*WoProcess)(void *context,float *stereo,unsigned frames,int stopping);
/* Called only after successful waveOutWrite, with cumulative pre-mute hash.
   Optional; bounded/nonblocking, same worker as process. */
typedef void (*WoSubmitted)(void *context,unsigned frames,uint64_t hash);
typedef struct {
    uint64_t frames,output_hash;
    unsigned blocks,queue_empty,budget_exceeded;
    double render_ms_total,render_ms_max,peak,device_seconds,playback_wall_seconds,startup_seconds;
    int opened;
    wchar_t error[256];
} WoStats;
typedef struct {
    WoProcess process;WoSubmitted submitted;void *context;
    CRITICAL_SECTION lock;
    HANDLE thread;
    volatile LONG running,stop;
    int muted;uint64_t frame_limit;
    WoStats stats;
} WoDevice;
void wo_init(WoDevice *device,WoProcess process,void *context);
int wo_start(WoDevice *device,int muted,uint64_t frame_limit);
void wo_stop(WoDevice *device);
void wo_destroy(WoDevice *device);
WoStats wo_stats(WoDevice *device);
#endif
