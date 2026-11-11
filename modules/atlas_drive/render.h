#ifndef VSL_ATLAS_DRIVE_RENDER_H
#define VSL_ATLAS_DRIVE_RENDER_H
#include "control.h"
#include "dna_atlas/voice.h"
#include "dna_scene/routing.h"

typedef struct {
    const SaBank *bank;
    uint64_t seed;
    int profile, channels;
    double root_per_rpm; /* Explicit hypothesis, e.g1/120 for the E cabin bank. */
    DsProjection projection;
    DsRoute route;
} AdConfig;

typedef struct {
    uint64_t frame;
    double rpm, speed, load, root_hz, blend, envelope;
    unsigned lower, upper, shifts, overruns, hits;
    int gear, lifecycle, operating, coverage;
} AdTelemetry;
typedef struct {
    float *dna_raw; /* Observation stereo, before driving envelope. */
    float *dna;     /* Observation stereo, after driving envelope. */
    float *events;  /* Mono, legacy procedural events, after optional gain. */
    float *dry;     /* Observation stereo + mono events, after master gain. */
    float *objects; /* 10 mono objects, before spatial/master; no measured banks. */
    AdTelemetry *telemetry; /* One per sample; caller may subsample200Hz. */
} AdCapture;
typedef struct {
    SaVoice dna;
    VslEngine *owner; /* Exclusive controller+spatial storage; no legacy render. */
    AdConfig config;
    AdControl target;
    double gain, event_gain, spatial_mix, envelope, follow;
    uint64_t frame;
} AdRender;

/* Init/load outside audio callback. No audio-time allocation or I/O. Atlas and
   all profiles must outlive this object. Never share owner with other renders.
   Only DNA and optional old procedural events are connected in this revision;
   cabin LF/intake/mechanics/air models remain absent rather than fabricated. */
int ad_render_init(AdRender *render,VslEngine *owner,const AdConfig *config,const AdControl *control);
int ad_render_set(AdRender *render,const AdControl *control);
int ad_render_process(AdRender *render,float *output,unsigned frames,const AdCapture *capture);
#endif
