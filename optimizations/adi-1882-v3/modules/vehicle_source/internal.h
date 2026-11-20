#ifndef VSL_VEHICLE_SOURCE_INTERNAL_H
#define VSL_VEHICLE_SOURCE_INTERNAL_H
#include "atlas_adapter.h"
#include "atlas_take/assets.h"
#include "state_dna/api.h"
#include "dna_character/voice.h"
#include "startup_flare/voice.h"
struct VsStateAssets;
struct VsAssets {AtAssets owned;struct VsStateAssets *states;};
struct VsEngine {
    const VsAssets *assets;
    AdRender generator;
    VslEngine owner;
    AdControl adopted;
    float idle_weight;
    int dna_unified;
    DchVoice *character;
    SflVoice *flare;
    float flare_gain;
    float flare_audio[VS_BLOCK_MAX*2];
    float flare_background[VS_BLOCK_MAX];
    ViState input;
    ViAdopted input_adopted;
    float monitor[VS_BLOCK_MAX*2];
    float dna[VS_BLOCK_MAX*2],body[VS_BLOCK_MAX*2],low[VS_BLOCK_MAX*2];
    float residual[VS_BLOCK_MAX*2],resonant[VS_BLOCK_MAX*2];
    float aux[VS_BLOCK_MAX*VSL_OBJECTS];
    float startup[VS_BLOCK_MAX*2],catching[VS_BLOCK_MAX*2],added[VS_BLOCK_MAX*2];
    float events[VS_BLOCK_MAX];
    AdTelemetry telemetry[VS_BLOCK_MAX];
    EcState event_control;
    SxVoice state_dna;
    EsPool event_pool;
    EsPool *event_runtime;
    uint64_t event_block_frame;
    float event_levels[ES_TYPES];
    float event_voices[ES_VOICES][VS_BLOCK_MAX];
};
VsAssets *vs_assets_acquire(void);
void vs_assets_release(VsAssets *assets);
void vs_state_assets_release(VsAssets *assets);
void vs_control_to_atlas(const VsControl *control,AdControl *old);
int vs_output_valid(const VsOutput *output,unsigned frames);
void vs_stems_write(VsEngine *engine,VsOutput *output,unsigned frames,float start_gain);
void vs_drive_step(void *state,VslDrive *driver,const VslParams *params,uint64_t frame);
int vs_events_init(VsEngine *engine,const EcControl *control);
int vs_events_sample(void *state,uint64_t frame);
void vs_events_observe(VsEngine *engine,const VslDrive *driver,const VslParams *params,uint64_t frame);
int vs_state_init(VsEngine *engine);
void vs_state_observe(VsEngine *engine,const VslDrive *driver);
int vs_state_sample(void *state,SaVoice *main,const HbBand *band,float stereo[2],float body[2]);
int vs_character_sample(void *state,const AdSourceContext *context,AdSourceFrame *frame);
void vs_character_envelopes(void *state,const VslEngine *owner,float *line,float *air);
int vs_flare_sample(VsEngine *engine,uint64_t frame);
void vs_flare_apply(VsEngine *engine,unsigned frames,float start_gain);
void vs_mechanical_sample(void *state,VslEngine *owner,DaVoice *voice,VslObjectFrame *raw,VslObjectFrame *mixed);
#endif
