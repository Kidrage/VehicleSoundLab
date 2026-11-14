#ifndef VSL_CATALOG_SESSION_H
#define VSL_CATALOG_SESSION_H
#include "models.h"
#include "../atlas_monitor_v1/audio.h"
typedef struct {DcPreset *preset;AdControl live;} CdSession;
/* Main thread only. Caller preserves unsaved take FIRST. Success takes
   candidate ownership, stops audio, commits pointers and stays ignition off.
   A failed candidate does not alter current host/preset. */
int cd_session_commit(CdSession *session,AmAudio *audio,DcPreset *candidate);
void cd_session_before_replay(CdSession *session,AmAudio *audio);
int cd_session_restore(CdSession *session,AmAudio *audio);
/* After audio destroyed/stopped. */
void cd_session_dispose(CdSession *session);
#endif
