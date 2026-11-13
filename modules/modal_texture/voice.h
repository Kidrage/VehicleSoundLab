#ifndef VSL_MODAL_TEXTURE_VOICE_H
#define VSL_MODAL_TEXTURE_VOICE_H
#include "envelope.h"
#include "modal_source/voice.h"
typedef struct {MsVoice source;MtEnvelope envelope;} MtVoice;
/* Non-RT. Both immutable profiles must outlive the voice. No room/filter,
   driving-state/RPM mapping, file IO or PCM trajectory lives in this adapter. */
int mt_voice_init(MtVoice *voice,const MsProfile *source,const MtProfile *texture,
                  uint64_t seed,double ratio,double gain,double amount);
int mt_voice_set(MtVoice *voice,double ratio,double gain,double amount);
int mt_voice_tick(MtVoice *voice,double stereo[2]);
int mt_voice_process(MtVoice *voice,double *interleaved,unsigned frames);
#endif
