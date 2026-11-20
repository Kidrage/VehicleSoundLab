#ifndef VSL_HARMONIC_BODY_BAND_H
#define VSL_HARMONIC_BODY_BAND_H
typedef struct { float stop_low, pass_low, pass_high, stop_high; } HbBand;
/* Frequency mask only; acoustic LF partition, not an isolated physical source. */
HbBand hb_band_default(void);
int hb_band_valid(const HbBand *band);
float hb_band_weight(const HbBand *band,float hz);
static inline float hb_band_ease_inline(float x){return x*x*(3-2*x);}
static inline float hb_band_weight_inline(const HbBand *b,float hz){
    if(hz<=b->stop_low||hz>=b->stop_high)return 0;
    if(hz<b->pass_low)return hb_band_ease_inline((hz-b->stop_low)/(b->pass_low-b->stop_low));
    if(hz>b->pass_high)return 1-hb_band_ease_inline((hz-b->pass_high)/(b->stop_high-b->pass_high));
    return 1;
}
#endif
