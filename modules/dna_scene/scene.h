#ifndef VSL_DNA_SCENE_SCENE_H
#define VSL_DNA_SCENE_SCENE_H
#include "routing.h"
#include "core/types.h"

typedef struct {
    DsSourceConfig source;
    DsProjection projection;
    DsRoute route;
    int channels; /* 2 or 12; immutable until stop/reinitialize. */
} DsSceneConfig;

typedef struct {
    DsSourceControl source;
    double output_gain, width, space, perspective;
    int propagation;
} DsSceneControl;

typedef struct {
    float *dna_raw, *low_raw; /* Each interleaved observation stereo, before gains. */
    float *dna, *low;         /* Each interleaved stereo, calibrated layer gains. */
    float *dry;              /* Stereo sum, output_gain, no spatial processing. */
    float *objects;          /* 10 mono objects interleaved, pre-master/spatial. */
} DsCapture;

typedef struct {
    DsSource source;
    VslEngine *spatial_owner;
    DsSceneControl target;
    DsProjection projection;
    DsRoute route;
    double output_gain, follow;
    uint64_t frame;
    int channels;
} DsScene;

int ds_scene_control_valid(const DsSceneControl *control);
/* Non-realtime. Borrow exclusive storage for the existing spatial renderer;
   never share it with vsl_process_layout. Models must outlive this instance. */
int ds_scene_init(DsScene *scene, VslEngine *spatial_storage, const DsSceneConfig *config, const DsSceneControl *control);
int ds_scene_set(DsScene *scene, const DsSceneControl *control);
/* All buffers are distinct, caller-owned and sized for frames; capture members
   may be NULL. No allocations, file/device/UI I/O or legacy driving/DNA calls.
   Floating output is not clipped/limited. Host owns headroom and endpoint fades. */
int ds_scene_process(DsScene *scene, float *output, unsigned frames, const DsCapture *capture);
#endif
