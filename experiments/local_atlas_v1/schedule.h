#ifndef VSL_LOCAL_ATLAS_SCHEDULE_H
#define VSL_LOCAL_ATLAS_SCHEDULE_H
#define LA_MAX_EVENTS 12001
typedef struct {unsigned frame;double root_hz,detail,gain;} LaEvent;
typedef struct {unsigned frames,count;LaEvent event[LA_MAX_EVENTS];} LaSchedule;
/* Non-RT transactional read. Frame0 required; strictly increasing events;
   48kHz, <=60 seconds, root0..1000Hz/detail&gain0..1. No runtime file reads. */
int la_schedule_load(LaSchedule *schedule,const char *path);
#endif
