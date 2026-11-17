#include "mechanical.h"
#include "core/engine.h"
#include "core/modules.h"
#include "drive_aux/motion.h"
#include <string.h>
void dch_mechanical_tick(VslEngine *engine,double follow,double mono[1]){
    VslObjectFrame frame;memset(&frame,0,sizeof frame);
    da_motion_tick(engine,follow);
    vsl_mechanical_tick(engine,&frame);
    mono[0]=frame.sample[VSL_MECHANICAL];
}
