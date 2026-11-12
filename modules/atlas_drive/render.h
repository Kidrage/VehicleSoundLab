#ifndef VSL_ATLAS_DRIVE_RENDER_H
#define VSL_ATLAS_DRIVE_RENDER_H
#include "control.h"
#include "dna_atlas/voice.h"
#include "dna_scene/routing.h"
#include "residual_atlas/voice.h"
#include "harmonic_body/mix.h"
#include "drive_aux/voice.h"
#include "stereo_bed/route.h"
#include "start_texture/voice.h"
#include "catch_bloom/voice.h"

typedef enum { AD_SCENE_OBJECTS, AD_SCENE_STEREO_BED } AdSceneMode;

typedef struct {
    const SaBank *bank;
    uint64_t seed;
    int profile, channels;
    double root_per_rpm; /* Explicit hypothesis, e.g1/120 for the E cabin bank. */
    DsProjection projection;
    DsRoute route;
    const RaBank *residual_bank; /* Optional, same acoustic anchors/context. */
    AdSceneMode scene_mode; /* Default0 retains former mono proxy routing. */
    const StProfile *startup_profile; /* Opt-in cabin observation, replaces legacy starter only. */
    const CbProfile *catch_profile; /* Optional observation colour, no physical-source claim. */
} AdConfig;

typedef struct {
    uint64_t frame;
    double rpm, speed, load, root_hz, blend, envelope;
    unsigned lower, upper, shifts, overruns, hits;
    int gear, lifecycle, operating, coverage;
    double residual_gain;
    double body_mix, body_envelope;
    double auxiliary_rpm, firing;
    int fuel_mode;
    unsigned rotating_strikes, fired_strikes;
} AdTelemetry;
typedef struct {
    float *dna_raw; /* Observation stereo, before driving envelope. */
    float *dna;     /* Observation stereo, after driving envelope. */
    float *events;  /* Mono, legacy procedural events, after optional gain. */
    float *dry;     /* Observation stereo + mono events, after master gain. */
    float *objects; /* 10 mono objects, before spatial/master; no measured banks. */
    AdTelemetry *telemetry; /* One per sample; caller may subsample200Hz. */
    float *residual_raw; /* Stereo, before amount and driving envelope. */
    float *residual; /* Stereo, after amount and driving envelope. */
    float *residual_objects; /* 10 source objects, before spatial/master. */
    float *body_raw; /* Stereo LF tap from the same DNA oscillator bank. */
    float *body; /* Stereo LF after amount and separate envelope; not new energy. */
    float *body_objects; /* 10 objects: selected observation projected to BODY. */
    float *aux_raw; /* 10 independently generated objects, before layer amounts. */
    float *aux_objects; /* Same10 objects, after individual amounts. */
    float *aux; /* Direct stereo auxiliary monitor, before master gain. */
    float *observation; /* DNA+body+residual L/R before width/master, both modes. */
    float *bed; /* Routed observation bed, config.channels, before master;0 in object mode. */
    float *startup; /* Independent observed L/R startup layer before width/master. */
    float *catch_bloom; /* Coherent CATCH delta L/R before width/master. */
} AdCapture;
typedef struct {
    SaVoice dna;
    RaVoice residual;
    HbBand body_band;
    HbMix body;
    DaVoice auxiliary;
    SbLayout bed_layout;
    StVoice startup;
    CbVoice catch_bloom;
    VslEngine *owner; /* Exclusive controller+spatial storage; no legacy render. */
    AdConfig config;
    AdControl target;
    double gain, event_gain, spatial_mix, envelope, follow;
    uint64_t frame;
} AdRender;

/* Init/load outside audio callback. No audio-time allocation or I/O. Atlas and
   all profiles must outlive this object. Never share owner with other renders.
   Optional residual atlas is separate from DNA and old procedural events.
   LF is a complementary harmonic partition, not a separated physical source;
   independent cabin sub-bass remains absent. Auxiliary intake/mechanical/air/
   road/wind are optional engineering templates, not fitted physical sources. */
int ad_render_init(AdRender *render,VslEngine *owner,const AdConfig *config,const AdControl *control);
int ad_render_set(AdRender *render,const AdControl *control);
int ad_render_process(AdRender *render,float *output,unsigned frames,const AdCapture *capture);
#endif
