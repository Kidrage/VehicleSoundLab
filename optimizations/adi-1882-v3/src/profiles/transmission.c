#include "transmission.h"
static const VslTransmissionProfile sport={
    .040f,.090f,.140f,.100f,1.200f,.450f,
    .035f,28000,36000,80,180,.35f,.60f
};
const VslTransmissionProfile *vsl_transmission_profile(int profile) { (void)profile;return &sport; }
