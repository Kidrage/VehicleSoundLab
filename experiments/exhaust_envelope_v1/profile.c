#include "profile.h"
static const VslEnvelopeBand bands[]={
#include "recipe.inc"
};
const VslEnvelopeBand *vsl_envelope_band(int index) { return index>=0&&index<3?&bands[index]:0; }
double vsl_envelope_strength(int mode) { return mode==1?.5:mode==2?1:0; }
const char *vsl_envelope_name(int mode) { return mode==0?"base":mode==1?"half":mode==2?"full":"invalid"; }
