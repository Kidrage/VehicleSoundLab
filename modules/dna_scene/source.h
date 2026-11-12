#ifndef VSL_DNA_SCENE_SOURCE_H
#define VSL_DNA_SCENE_SOURCE_H
#include "voice.h"
#include "phase_texture/voice.h"

typedef struct {
    const SdProfile *dna, *low; /* Borrowed immutable models; low may be NULL. */
    uint64_t dna_seed, low_seed;
    double low_scale; /* Fixed offline calibration, not a loudness follower. */
    uint64_t phase_seed;
} DsSourceConfig;

typedef struct {
    double pitch, dna_detail, low_detail, dna_gain, low_gain;
    double phase_texture; /*0..1: bypass..light shared phase motion. */
} DsSourceControl;

typedef struct {
    double dna_raw[2], low_raw[2];
    double dna[2], low[2]; /* Pre-spatial, pre-master layers. */
} DsSourceFrame;

typedef struct {
    SdVoice dna, low;
    PtVoice phase;
    DsSourceControl target;
    uint64_t frame;
    double dna_gain, low_gain, low_scale, follow;
    int has_low;
} DsSource;

int ds_source_control_valid(const DsSourceControl *control);
int ds_source_init(DsSource *source, const DsSourceConfig *config, const DsSourceControl *control);
/* Invalid controls leave every target and clock unchanged. Audio-thread owner. */
int ds_source_set(DsSource *source, const DsSourceControl *control);
void ds_source_tick(DsSource *source, DsSourceFrame *frame);
#endif
