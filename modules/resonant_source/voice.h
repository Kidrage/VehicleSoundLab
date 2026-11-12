#ifndef VSL_RESONANT_SOURCE_VOICE_H
#define VSL_RESONANT_SOURCE_VOICE_H
#include "dna_scene/source.h"
#include "resonant_detail/voice.h"
#include "recipe.h"
typedef struct {
    DsSourceConfig source; /* Borrowed prepared DNA and optional matched LF. */
    const RdtProfile *detail; /* Borrowed immutable; may be NULL. */
    uint64_t detail_seed;
} RssConfig;
typedef struct { DsSourceControl source;double detail_gain; } RssControl;
typedef struct {
    DsSourceFrame source;
    double detail_raw[2],detail[2],mix[2];
    double phase_cycles;
} RssFrame;
typedef struct {
    DsSource source;
    RdtVoice detail;
    RssControl target;
    double detail_gain,follow;
    int initialized,has_detail;
} RssVoice;
int rss_control_valid(const RssControl *control);
/* Non-RT, transactional; only detail is prewarmed before source sample0.
   All models must outlive the voice. No room or source PCM. */
int rss_voice_init(RssVoice *voice,const RssConfig *config,const RssControl *control);
/* RT owner only; invalid controls leave state unchanged. Phase texture is
   intentionally disabled in this held recipe; source.phase_texture must be0. */
int rss_voice_set(RssVoice *voice,const RssControl *control);
/* RT, preallocated state/output; no I/O/allocation. One DNA phase drives
   detail envelopes; muting never pauses RNG/filter/source clocks. */
int rss_voice_tick(RssVoice *voice,RssFrame *frame);
#endif
