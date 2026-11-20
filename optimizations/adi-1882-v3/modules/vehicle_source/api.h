#ifndef VSL_VEHICLE_SOURCE_API_H
#define VSL_VEHICLE_SOURCE_API_H
#include <stdint.h>
#include "vehicle_input/types.h"
#include "event_control/api.h"
#include "profiles/lifecycle.h"
#include "dna_character/control.h"
#define VS_RATE 48000
#define VS_BLOCK_MAX 1024
typedef struct VsAssets VsAssets;
typedef struct VsEngine VsEngine;
typedef VslLifecycleProfile VsStartupResponse;
typedef EcPolicy VsEventPolicy;
typedef EcPolicyStats VsEventPolicyStats;
enum {VS_BENCH,VS_PEDALS,VS_AUTODRIVE};
enum {VS_DNA,VS_LOW,VS_DETAIL,VS_INTAKE,VS_MECHANICAL,VS_EXHAUST_AIR,
      VS_ROAD,VS_WIND,VS_STARTUP,VS_CATCH,VS_ADDED,VS_LEGACY_EVENT,
      VS_EVENT_0,VS_EVENT_1,VS_EVENT_2,VS_EVENT_3,VS_STEMS};
typedef struct {
    int mode,ignition,start_id,gear,automatic,backfire;
    float rpm,load,throttle,brake;
    float gain,detail,legacy_event_gain,low_mix,coherent_low_gain,resonant_gain,residual_gain;
    float intake_gain,mechanical_gain,air_gain,road_gain,wind_gain;
    float startup_gain,catch_gain,idle_mix,idle_motion,idle_detail;
    ViInput input;
    EcControl events;
    int dna_unified; /* Fixed at engine creation; legacy adapters keep zero. */
    DchControl dna;
} VsControl;
typedef struct {
    const char *id,*name,*role;
    unsigned channels;
    /* Electrical monitor only; no vehicle position or speaker routing.
       These weights reconstruct the supplied reference monitor from stems. */
    float monitor_left,monitor_right;
} VsStemInfo;
typedef struct {
    uint64_t frame;
    float rpm,speed_mps,acceleration_mps2,load,root_hz,gain,idle_weight;
    int gear,lifecycle,operating,coverage;
    unsigned shifts,overruns,legacy_hits;
    int input_source,input_stale;
    float tire_slip;
    uint64_t signal_sequence;
    unsigned event_active,event_started,event_rejected,event_replaced;
    unsigned event_queue,event_overflow,event_log_lost,event_peak;
} VsTelemetry;
typedef struct {
    float *monitor; /* Optional interleaved stereo, frames*2. */
    float *stem[VS_STEMS]; /* Optional native-channel arrays, all non-overlapping. */
} VsOutput;
const VsStemInfo *vs_stem_info(unsigned stem);
/* Assets and engines are created/destroyed outside audio processing.
   Assets immutable and borrowed: keep alive until engine destroyed.
   No file/device I/O, allocation or spatial processing in set/process. */
void vs_assets_destroy(VsAssets *assets);
VsEngine *vs_engine_create(const VsAssets *assets,const VsControl *control);
void vs_engine_destroy(VsEngine *engine);
int vs_engine_set(VsEngine *engine,const VsControl *control);
int vs_engine_process(VsEngine *engine,VsOutput *output,unsigned frames);
int vs_engine_telemetry(const VsEngine *engine,VsTelemetry *telemetry);
unsigned vs_event_mask(void);
const char *vs_event_bank_identity(void);
/* Non-RT setup only, before the first frame/control event. Copies parameters.
   Blank valid profiles explicitly disable a type. Never changes the global bank. */
int vs_engine_event_profile(VsEngine *engine,unsigned type,const EsProfile *profile);
/* Non-RT, before frame 0 and before any queued control event. Copied per engine.
   Governs the unique driver and startup/catch texture progress, not event modes. */
int vs_engine_startup_set(VsEngine *engine,const VsStartupResponse *response);
int vs_engine_startup_get(const VsEngine *engine,VsStartupResponse *response);
/* Non-RT catalog opt-in, before frame zero. Enables the selected catch-only
   model; startup_gain controls it, old starter/catch sources are replaced.
   Other catalogs/authored DNA never inherit these V10 parameters implicitly. */
int vs_engine_enable_start_flare(VsEngine *engine);
/* Non-RT, before frame 0 and before queued/manual events; copied per engine. */
int vs_engine_event_policy_set(VsEngine *engine,const VsEventPolicy *policy);
int vs_engine_event_policy_get(const VsEngine *engine,VsEventPolicy *policy);
int vs_engine_event_policy_stats(const VsEngine *engine,VsEventPolicyStats *stats);
unsigned vs_engine_events(VsEngine *engine,EsNotice *notices,unsigned capacity);
#endif
