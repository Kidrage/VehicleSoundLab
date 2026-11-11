#include "transmission.h"
static const VslTransmissionProfile sport={
    .040,.090,.140,.100,1.200,.450,
    .035,28000,36000,80,180,.35,.60
};
const VslTransmissionProfile *vsl_transmission_profile(int profile) { (void)profile;return &sport; }
