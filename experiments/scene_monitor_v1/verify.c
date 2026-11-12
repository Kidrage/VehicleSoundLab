#define _CRT_SECURE_NO_WARNINGS
#include "audio.h"
#include "recipe.h"
#include "io/wav.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static SdProfile dna, low;
static SaAudio audio;

static int save(const char *directory, const char *name, const float *samples, unsigned frames) {
    char path[4096]; VslWavWriter writer = {0}; int ok;
    if (snprintf(path, sizeof path, "%s/%s.wav", directory, name) >= (int)sizeof path ||
        !vsl_wav_begin_float(&writer, path, 48000, 2)) return 0;
    ok = vsl_wav_write(&writer, samples, frames);
    return vsl_wav_end(&writer) && ok;
}

static int replay(SaAudio *a, const SaStats *stats) {
    SmoRender *render = calloc(1, sizeof *render); VslEngine *storage = calloc(1, sizeof *storage);
    float block[1024]; uint64_t at = 0; unsigned event = 0; int ok = 0;
    if (!render || !storage || !a->trace_count || !smo_render_init(render, storage, &a->config, &a->trace[0].control)) goto done;
    while (at < stats->frames) {
        unsigned n = (unsigned)(stats->frames - at);
        if (n > 512) n = 512;
        while (event < a->trace_count && a->trace[event].frame == at) {
            if (!smo_render_set(render, &a->trace[event++].control)) goto done;
        }
        if (!smo_render_process(render, block, n, at >= a->stop_frame, NULL)) goto done;
        if (memcmp(block, a->capture + at * 2, n * 2 * sizeof(float))) goto done;
        at += n;
    }
    ok = event == a->trace_count;
done:
    free(render); free(storage); return ok;
}

static int healthy(const SaStats *s) {
    return s->opened && !s->error[0] && !s->queue_empty && !s->trace_overflow && s->frames && s->peak < .95 &&
        fabs(s->device_seconds - s->frames / 48000.) < .06;
}

static int save_trace(const char *directory, const char *name, const SaAudio *a) {
    char path[4096]; FILE *file; unsigned i; int ok;
    snprintf(path, sizeof path, "%s/%s_controls.json", directory, name);
    file = vsl_fopen(path, "wb"); if (!file) return 0;
    fprintf(file, "{\"schema\":\"vsl.monitor-control-evidence/1\",\"sample_rate\":48000,\"dna_seed\":48271,\"low_seed\":48271,\"stop_frame\":");
    if (a->stop_frame == UINT64_MAX) fprintf(file, "null"); else fprintf(file, "%llu", (unsigned long long)a->stop_frame);
    fprintf(file, ",\"events\":[");
    for (i = 0; i < a->trace_count; ++i) {
        const SmoControl *c = &a->trace[i].control;
        fprintf(file, "%s{\"frame\":%llu,\"pitch\":%.17g,\"dna_detail\":%.17g,\"low_detail\":%.17g,\"dna_gain\":%.17g,\"low_gain\":%.17g,\"output_gain\":%.17g,\"width\":%.17g,\"space\":%.17g,\"perspective\":%.17g,\"propagation\":%d,\"spatial\":%d,\"phase_texture\":%.17g}",
            i ? "," : "", (unsigned long long)a->trace[i].frame, c->scene.source.pitch,
            c->scene.source.dna_detail, c->scene.source.low_detail, c->scene.source.dna_gain,
            c->scene.source.low_gain, c->scene.output_gain, c->scene.width, c->scene.space,
            c->scene.perspective, c->scene.propagation, c->spatial, c->scene.source.phase_texture);
    }
    fprintf(file, "]}\n"); ok = !ferror(file); if (fclose(file)) ok = 0; return ok;
}

static void stats_json(FILE *file, const char *key, const SaStats *s, int equal) {
    fprintf(file, "\"%s\":{\"frames\":%llu,\"blocks\":%u,\"queue_empty\":%u,\"device_seconds\":%.9g,\"wall_seconds\":%.9g,\"render_ms_mean\":%.9g,\"render_ms_max\":%.9g,\"peak\":%.9g,\"applied_controls\":%u,\"trace_overflow\":%u,\"offline_float_equal\":%s}",
        key, (unsigned long long)s->frames, s->blocks, s->queue_empty, s->device_seconds, s->wall_seconds,
        s->render_ms_total / fmax(1, s->blocks), s->render_ms_max, s->peak, s->changes, s->trace_overflow, equal ? "true" : "false");
}

static int run(int argc, char **argv) {
    DsSceneConfig config; SmoControl control = smo_recipe_control();
    SaStats baseline, live, stopped, restarted; int equal[4] = {0}, ok = 1, stage = 0;
    FILE *file; char path[4096]; ULONGLONG deadline; int phase_study = 0;
    if (argc == 5 && !strcmp(argv[4], "--phase-texture")) phase_study = 1;
    if ((argc != 4 && !phase_study) || !sd_profile_load(argv[1], &dna) || !sd_profile_load(argv[2], &low)) return 2;
    control.scene.source.phase_texture = phase_study ? 1 : 0;
    config = smo_recipe_config(&dna, &low); sa_audio_init(&audio, &config, &control, 1);
    audio.capture_frames = 8 * 48000;
    audio.capture = calloc(audio.capture_frames * 2, sizeof(float));
    if (!audio.capture) { sa_audio_destroy(&audio); return 2; }
    audio.frame_limit = 6 * 48000;
    if (!sa_audio_start(&audio)) goto failed;
    deadline = GetTickCount64() + 15000;
    while (InterlockedCompareExchange(&audio.running, 0, 0) && GetTickCount64() < deadline) Sleep(10);
    sa_audio_stop(&audio); baseline = sa_audio_stats(&audio);
    equal[0] = replay(&audio, &baseline);
    ok &= healthy(&baseline) && equal[0] && baseline.frames == 6 * 48000 && save(argv[3], "baseline", audio.capture, (unsigned)baseline.frames) && save_trace(argv[3], "baseline", &audio);
    audio.frame_limit = 8 * 48000;
    if (!sa_audio_start(&audio)) goto failed;
    deadline = GetTickCount64() + 18000;
    while (InterlockedCompareExchange(&audio.running, 0, 0) && GetTickCount64() < deadline) {
        SaStats s = sa_audio_stats(&audio);
        if (stage == 0 && s.frames >= 24000) { control.scene.source.pitch = .9; stage = 1; sa_audio_controls(&audio, &control); }
        else if (stage == 1 && s.frames >= 60000) { control.scene.source.low_gain = 0; stage = 2; sa_audio_controls(&audio, &control); }
        else if (stage == 2 && s.frames >= 96000) { control.spatial = 1; control.scene.space = .65; control.scene.source.phase_texture = 0; stage = 3; sa_audio_controls(&audio, &control); }
        else if (stage == 3 && s.frames >= 132000) { control.scene.width = 0; control.scene.propagation = 1; stage = 4; sa_audio_controls(&audio, &control); }
        else if (stage == 4 && s.frames >= 168000) { control.scene.output_gain = .5 * pow(10, -6./20); stage = 5; sa_audio_controls(&audio, &control); }
        else if (stage == 5 && s.frames >= 204000) { control.scene.source.low_gain = 1; control.scene.source.pitch = 1.1; control.scene.source.phase_texture = phase_study ? 1 : 0; stage = 6; sa_audio_controls(&audio, &control); }
        else if (stage == 6 && s.frames >= 240000) { control.spatial = 0; stage = 7; sa_audio_controls(&audio, &control); }
        else if (stage == 7 && s.frames >= 288000) { control.scene.width = .6; control.spatial = 1; stage = 8; sa_audio_controls(&audio, &control); }
        else if (stage == 8 && s.frames >= 336000) { control = smo_recipe_control(); control.scene.source.phase_texture = phase_study ? 1 : 0; stage = 9; sa_audio_controls(&audio, &control); }
        Sleep(10);
    }
    sa_audio_stop(&audio); live = sa_audio_stats(&audio); equal[1] = replay(&audio, &live);
    ok &= healthy(&live) && equal[1] && stage == 9 && live.frames == 8 * 48000 && save(argv[3], "live_controls", audio.capture, (unsigned)live.frames) && save_trace(argv[3], "live", &audio);
    control = smo_recipe_control(); control.scene.source.phase_texture = phase_study ? 1 : 0; sa_audio_controls(&audio, &control); audio.frame_limit = 0;
    if (!sa_audio_start(&audio)) goto failed;
    deadline = GetTickCount64() + 5000;
    while (sa_audio_stats(&audio).frames < 24000 && InterlockedCompareExchange(&audio.running, 0, 0) && GetTickCount64() < deadline) Sleep(10);
    sa_audio_stop(&audio); stopped = sa_audio_stats(&audio); equal[2] = replay(&audio, &stopped);
    ok &= healthy(&stopped) && equal[2] && audio.render.release == 480 && !audio.thread && save(argv[3], "stopped", audio.capture, (unsigned)stopped.frames) && save_trace(argv[3], "stopped", &audio);
    audio.frame_limit = 48000;
    if (!sa_audio_start(&audio)) goto failed;
    deadline = GetTickCount64() + 5000;
    while (InterlockedCompareExchange(&audio.running, 0, 0) && GetTickCount64() < deadline) Sleep(10);
    sa_audio_stop(&audio); restarted = sa_audio_stats(&audio); equal[3] = replay(&audio, &restarted);
    ok &= healthy(&restarted) && equal[3] && restarted.frames == 48000 && save(argv[3], "restarted", audio.capture, (unsigned)restarted.frames) && save_trace(argv[3], "restarted", &audio);
    snprintf(path, sizeof path, "%s/device.json", argv[3]); file = vsl_fopen(path, "wb");
    if (!file) goto failed;
    fprintf(file, "{\"result\":\"%s\",\"device_muted\":true,\"control_stage\":%d,\"block_budget_ms\":%.9g,", ok ? "pass" : "fail", stage, 512 * 1000. / 48000);
    stats_json(file, "baseline", &baseline, equal[0]); fprintf(file, ",");
    stats_json(file, "live", &live, equal[1]); fprintf(file, ",");
    stats_json(file, "stopped", &stopped, equal[2]); fprintf(file, ",");
    stats_json(file, "restarted", &restarted, equal[3]); fprintf(file, "}\n"); fclose(file);
    free(audio.capture); audio.capture = NULL; sa_audio_destroy(&audio);
    puts(ok ? "PASS: muted device submissions, adopted control replay, stop and restart" : "FAIL: see device.json");
    return ok ? 0 : 3;
failed:
    sa_audio_stop(&audio); free(audio.capture); audio.capture = NULL; sa_audio_destroy(&audio); return 2;
}

int wmain(int argc, wchar_t **wide) {
    char **args = calloc((size_t)argc, sizeof *args); int i, result = 2;
    if (!args) return 2;
    for (i = 0; i < argc; ++i) {
        int length = WideCharToMultiByte(CP_UTF8, 0, wide[i], -1, NULL, 0, NULL, NULL);
        if (!length || !(args[i] = malloc((size_t)length)) || !WideCharToMultiByte(CP_UTF8, 0, wide[i], -1, args[i], length, NULL, NULL)) goto done;
    }
    result = run(argc, args);
done:
    for (i = 0; i < argc; ++i) free(args[i]); free(args); return result;
}
