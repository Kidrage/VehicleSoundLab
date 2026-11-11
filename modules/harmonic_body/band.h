#ifndef VSL_HARMONIC_BODY_BAND_H
#define VSL_HARMONIC_BODY_BAND_H
typedef struct { double stop_low, pass_low, pass_high, stop_high; } HbBand;
/* Frequency mask only; acoustic LF partition, not an isolated physical source. */
HbBand hb_band_default(void);
int hb_band_valid(const HbBand *band);
double hb_band_weight(const HbBand *band,double hz);
#endif
