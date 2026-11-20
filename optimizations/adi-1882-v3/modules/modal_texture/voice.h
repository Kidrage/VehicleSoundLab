#ifndef VSL_MODAL_TEXTURE_VOICE_H
#define VSL_MODAL_TEXTURE_VOICE_H
#include "envelope.h"
#include "modal_source/voice.h"
typedef struct {MsVoice source;MtEnvelope envelope;} MtVoice;
/* Non-RT. Both immutable profiles must outlive the voice. No room/filter,
   driving-state/RPM mapping, file IO or PCM trajectory lives in this adapter. */
int mt_voice_init(MtVoice *voice,const MsProfile *source,const MtProfile *texture,
                  uint64_t seed,float ratio,float gain,float amount);
int mt_voice_set(MtVoice *voice,float ratio,float gain,float amount);
int mt_voice_tick(MtVoice *voice,float stereo[2]);
int mt_voice_process(MtVoice *voice,float *interleaved,unsigned frames);
#endif
