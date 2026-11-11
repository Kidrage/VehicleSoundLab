#ifndef VSL_SCENE_MONITOR_RENDER_H
#define VSL_SCENE_MONITOR_RENDER_H
#include "dna_scene/scene.h"

typedef struct { DsSceneControl scene; int spatial; } SmoControl;
typedef struct {
    DsScene scene;
    double spatial_mix, follow;
    unsigned onset, release;
    int stopping;
    SmoControl target;
} SmoRender;
typedef struct { float *dna_raw, *low_raw, *dry, *spatial; } SmoCapture;

int smo_control_valid(const SmoControl *control);
int smo_render_init(SmoRender *render, VslEngine *storage, const DsSceneConfig *config, const SmoControl *control);
int smo_render_set(SmoRender *render, const SmoControl *control);
/* Stereo device adapter; linear18ms dry/spatial fade,5ms onset,10ms stop.
   Captures are before endpoint fades; no allocation, I/O or output limiter. */
int smo_render_process(SmoRender *render, float *stereo, unsigned frames, int stop, const SmoCapture *capture);
#endif
