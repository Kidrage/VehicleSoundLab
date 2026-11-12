#ifndef VSL_ATLAS_TAKE_PLAYER_H
#define VSL_ATLAS_TAKE_PLAYER_H
#include "take.h"
#include "atlas_monitor/render.h"
typedef struct {
    const AtTake *take;
    AmRender render;
    AdConfig config;
    AdControl current;
    unsigned next;
    uint64_t audio_hash,source_hash;
    float raw[1024],dna[1024],residual[1024],body[1024],events[512];
    float auxiliary[512*VSL_OBJECTS];
    float startup[1024];
} AtPlayer;
/* Override layout2/12 for export; source controls are identical,12forces only
   spatial routing. Recorded presentation hash applies to its original layout. */
int at_player_init(AtPlayer *player,VslEngine *owner,const AtTake *take,int channels);
unsigned at_player_process(AtPlayer *player,float *output,unsigned frames,AdTelemetry *telemetry);
int at_player_complete(const AtPlayer *player);
int at_player_verified(const AtPlayer *player);
#endif
