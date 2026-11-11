#ifndef VSL_TAKE_H
#define VSL_TAKE_H
#include "core/engine.h"
#define VSL_TAKE_EVENTS 65536
#define VSL_TAKE_MAX_FRAMES (UINT64_C(48000)*600)
#define VSL_TAKE_HASH_INITIAL UINT64_C(14695981039346656037)
typedef struct { uint64_t frame;VslParams params; } VslTakeEvent;
typedef struct {
    double dna_root,dna_amp[VSL_PARTIALS],dna_phase[VSL_PARTIALS];
    float ir[VSL_MAX_IR];unsigned dna_count,ir_length;
} VslTakeAssets;
typedef struct {
    VslTakeEvent *events;unsigned count,capacity,sample_rate;uint32_t seed;
    uint64_t frames,audio_hash;VslTakeAssets assets;
    char dsp[32];int overflow;
} VslTake;
typedef struct { const VslTake *take;unsigned next;uint64_t audio_hash; } VslTakePlayer;
int vsl_take_allocate(VslTake *take,unsigned capacity);
void vsl_take_free(VslTake *take);
int vsl_take_begin(VslTake *take,const VslEngine *fresh_engine);
int vsl_take_record(VslTake *take,uint64_t frame,const VslParams *actual_target);
void vsl_take_commit(VslTake *take,const float *stereo,unsigned frames);
void vsl_take_finish(VslTake *take);
int vsl_take_validate(const VslTake *take);
int vsl_take_player_init(VslTakePlayer *player,VslEngine *engine,const VslTake *take);
unsigned vsl_take_process(VslTakePlayer *player,VslEngine *engine,float *output,unsigned frames,int channels,float *stems);
uint64_t vsl_take_hash(uint64_t hash,const float *audio,unsigned samples);
#endif
