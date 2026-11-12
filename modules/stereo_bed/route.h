#ifndef VSL_STEREO_BED_ROUTE_H
#define VSL_STEREO_BED_ROUTE_H

typedef struct { unsigned channels; } SbLayout;
/* Observation channels with baked recording transfer, not physical cylinders.
   Native order FL FR FC LFE BL BR SL SR TFL TFR TBL TBR; no invented upmix.
   Init is transactional. Route takes validated finite stereo and width0..1,
   applies width once, overwrites every channel; no gain/EQ/room/allocation. */
int sb_layout_init(SbLayout *layout,unsigned channels);
void sb_route(const SbLayout *layout,const double stereo[2],double width,double *output);
#endif
