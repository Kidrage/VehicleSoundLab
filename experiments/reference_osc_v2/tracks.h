#ifndef VSL_REFERENCE_TRACKS_H
#define VSL_REFERENCE_TRACKS_H
#include "model.h"
#define RT_MAX_TRACKS 262144u
typedef struct { unsigned tracks,rows,segments;unsigned *offsets,*ids; } RtTracks;
/* Borrowed acoustic model. IDs may persist only across contiguous intervals
   with matching endpoints. Loading and ownership changes are not realtime. */
int rt_tracks_load(const char *path,const RoModel *model,RtTracks *tracks);
void rt_tracks_free(RtTracks *tracks);
#endif
