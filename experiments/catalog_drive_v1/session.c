#include "session.h"
#include <string.h>
int cd_session_commit(CdSession *s,AmAudio *a,DcPreset *candidate) {
    const AdConfig *cfg=dc_preset_config(candidate);AdControl c=dc_preset_initial(candidate);DcPreset *old;
    if(!s||!a||!cfg||candidate==s->preset||cfg->channels!=2||c.drive.ignition||!ad_control_supported(cfg,&c))return 0;
    am_audio_stop(a);old=s->preset;a->config=*cfg;
    if(!am_audio_control(a,&c))return 0; /*Stopped and validated above. */
    a->transport=0;InterlockedExchange(&a->replay_result,0);
    EnterCriticalSection(&a->lock);memset(&a->latest,0,sizeof a->latest);LeaveCriticalSection(&a->lock);
    s->preset=candidate;s->live=c;dc_preset_destroy(old);return 1;
}
void cd_session_before_replay(CdSession *s,AmAudio *a){if(s&&a&&a->transport!=2)s->live=am_audio_get(a);}
int cd_session_restore(CdSession *s,AmAudio *a) {
    if(!s||!s->preset||!a)return 0;
    if(a->transport!=2)return 1;
    am_audio_stop(a);a->config=*dc_preset_config(s->preset);
    if(!am_audio_control(a,&s->live))return 0;
    a->transport=0;return 1;
}
void cd_session_dispose(CdSession *s){if(s){dc_preset_destroy(s->preset);memset(s,0,sizeof *s);}}
