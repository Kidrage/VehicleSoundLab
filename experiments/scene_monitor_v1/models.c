#include "models.h"
#include <windows.h>
#include <stdlib.h>

static int load(const wchar_t *path, SdProfile *profile) {
    char utf8[8192];
    return WideCharToMultiByte(CP_UTF8, 0, path, -1, utf8, sizeof utf8, NULL, NULL) && sd_profile_load(utf8, profile);
}
int smo_models_read(SmoModels *destination, const wchar_t *dna, const wchar_t *low) {
    SmoModels *candidate = calloc(1, sizeof *candidate);
    DsSource *trial = calloc(1, sizeof *trial); int ok = 0;
    if (candidate && trial && load(dna, &candidate->dna) && (!low || load(low, &candidate->low))) {
        DsSceneConfig config; SmoControl control = smo_recipe_control();
        candidate->has_low = low != NULL;
        config = smo_recipe_config(&candidate->dna, low ? &candidate->low : NULL);
        if (ds_source_init(trial, &config.source, &control.scene.source)) { *destination = *candidate; ok = 1; }
    }
    free(candidate); free(trial); return ok;
}
