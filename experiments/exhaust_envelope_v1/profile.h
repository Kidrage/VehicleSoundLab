#ifndef VSL_ENVELOPE_PROFILE_H
#define VSL_ENVELOPE_PROFILE_H
typedef struct { double hz,q,gain_db; } VslEnvelopeBand;
const VslEnvelopeBand *vsl_envelope_band(int index);
double vsl_envelope_strength(int mode);
const char *vsl_envelope_name(int mode);
#endif
