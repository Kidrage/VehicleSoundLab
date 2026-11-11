#ifndef VSL_ENVELOPE_TRANSFER_H
#define VSL_ENVELOPE_TRANSFER_H
#include "biquad.h"
#include "core/engine.h"
#include "session/take.h"
typedef struct {
    VslEnvelopeBiquad bank[2][3];
    double sample_rate;int mode,eligible;
} VslEnvelopeTransfer;
int vsl_envelope_init(VslEnvelopeTransfer *s,double rate,int mode);
void vsl_envelope_prepare(VslEnvelopeTransfer *s,const VslEngine *e);
double vsl_envelope_side_tick(VslEnvelopeTransfer *s,int side,double input);
void vsl_envelope_excitation_tick(VslEngine *e,VslObjectFrame *objects,VslEnvelopeTransfer *s,float *taps);
int vsl_envelope_process_layout(VslEngine *e,VslEnvelopeTransfer *s,float *out,unsigned frames,int channels,float *stems,float *taps);
unsigned vsl_envelope_take_process(VslTakePlayer *p,VslEngine *e,VslEnvelopeTransfer *s,float *out,unsigned frames,int channels,float *stems,float *taps);
#endif
