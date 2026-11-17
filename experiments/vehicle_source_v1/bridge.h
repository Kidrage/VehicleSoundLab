#ifndef VSL_SOURCE_BRIDGE_H
#define VSL_SOURCE_BRIDGE_H
#include "vehicle_source/api.h"
#include "vehicle_source/state_assets.h"
#if defined(_WIN32)
#define VSB_API __declspec(dllexport)
#else
#define VSB_API
#endif
typedef struct VsbHandle VsbHandle;
enum {VSB_RESIDUAL=1,VSB_LOW=2,VSB_RESONANT=4,VSB_STARTUP=8,VSB_CATCH=16,VSB_IDLE=32,VSB_FINE_IDLE=64,VSB_START_FLARE=128,VSB_TUNING_HEADROOM=256,VSB_MECHANICAL_DNA=512};
VSB_API unsigned vsl_source_abi(void);
VSB_API unsigned vsl_source_event_policy_size(void);
VSB_API unsigned vsl_source_event_policy_stats_size(void);
VSB_API int vsl_source_event_policy_set(VsbHandle *handle,const VsEventPolicy *policy);
VSB_API int vsl_source_event_policy_get(VsbHandle *handle,VsEventPolicy *policy);
VSB_API int vsl_source_event_policy_stats(VsbHandle *handle,VsEventPolicyStats *stats);
VSB_API unsigned vsl_source_startup_size(void);
VSB_API int vsl_source_startup_set(VsbHandle *handle,const VsStartupResponse *response);
VSB_API int vsl_source_startup_get(VsbHandle *handle,VsStartupResponse *response);
VSB_API unsigned vsl_source_control_size(void);
VSB_API unsigned vsl_source_telemetry_size(void);
VSB_API unsigned vsl_source_event_notice_size(void);
VSB_API unsigned vsl_source_event_profile_size(void);
VSB_API int vsl_source_event_profile(VsbHandle *handle,unsigned type,const EsProfile *profile);
VSB_API unsigned vsl_source_event_mask(void);
VSB_API const char *vsl_source_event_bank_identity(void);
VSB_API unsigned vsl_source_events(VsbHandle *handle,EsNotice *notices,unsigned capacity);
VSB_API unsigned vsl_source_catalog_count(void);
VSB_API const char *vsl_source_catalog_name(int selection);
VSB_API const char *vsl_source_catalog_key(int selection);
/* Non-RT catalog/owned-assets adapter for local hosts, separate from DSP.
   Host serializes calls for each handle; no hidden audio/device thread. */
VSB_API VsbHandle *vsl_source_open(int catalog_selection);
/* Non-RT file adapter; validates/copies DNA before constructing an engine.
   Catalog selection supplies vehicle control defaults, never its sound layers. */
VSB_API VsbHandle *vsl_source_open_dna(int catalog_selection,const char *const *paths,unsigned count,
    double root_per_rpm,uint64_t seed,unsigned align_orders);
/* Flattened base/idle/power/overrun paths, counts[4]; non-RT owned load. */
VSB_API VsbHandle *vsl_source_open_state_dna(int catalog_selection,const char *const *paths,const unsigned *counts,
    double root_per_rpm,uint64_t seed,unsigned align_orders,double transition_seconds);
VSB_API unsigned vsl_source_dna_state_size(void);
VSB_API int vsl_source_dna_state(VsbHandle *handle,SxTelemetry *telemetry);
VSB_API void vsl_source_close(VsbHandle *handle);
VSB_API int vsl_source_controls(VsbHandle *handle,VsControl *control);
VSB_API int vsl_source_set(VsbHandle *handle,const VsControl *control);
VSB_API int vsl_source_state(VsbHandle *handle,VsTelemetry *telemetry);
VSB_API unsigned vsl_source_channels(void);
VSB_API unsigned vsl_source_capabilities(VsbHandle *handle);
VSB_API unsigned vsl_source_stem_channels(unsigned stem);
VSB_API const char *vsl_source_stem_name(unsigned stem);
/* Packed stems are frame-major concatenation of native channels in VS order.
   The monitor is an electrical reference mix, never a spatial render. */
VSB_API int vsl_source_process(VsbHandle *handle,float *monitor,float *packed_stems,unsigned frames);
#endif
