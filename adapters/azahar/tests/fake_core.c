#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#define EXPORT __declspec(dllexport)
#else
#include <unistd.h>
#define EXPORT __attribute__((visibility("default")))
#endif

typedef bool (*environment_fn)(unsigned, void *);
typedef void (*video_fn)(const void *, unsigned, unsigned, size_t);
typedef int16_t (*input_fn)(unsigned, unsigned, unsigned, unsigned);
static environment_fn environment;
static video_fn video;
static input_fn input;
static void (*poll_input)(void);
struct system_info { const char *name, *version, *extensions; bool fullpath, extract; };
struct geometry { unsigned width, height, max_width, max_height; float aspect; };
struct av_info { struct geometry geometry; double fps, sample_rate; };
struct game { const char *path; const void *data; size_t size; const char *meta; };
struct variable { const char *key, *value; };
static const char *renderer_option, *fallback_option;

static int mode(const char *value) {
    const char *actual = getenv("EMUCAP_FAKE_MODE");
    return actual && strcmp(actual, value) == 0;
}
static void event(const char *name) {
    const char *path = getenv("EMUCAP_FAKE_LOG");
    if (path) { FILE *file = fopen(path, "a"); if (file) { fprintf(file, "%s\n", name); fclose(file); } }
}
EXPORT unsigned retro_api_version(void) { return mode("bad_version") ? 2 : 1; }
EXPORT void retro_set_environment(environment_fn callback) { environment = callback; }
EXPORT void retro_set_video_refresh(video_fn callback) { video = callback; }
EXPORT void retro_set_input_state(input_fn callback) { input = callback; }
EXPORT void retro_set_input_poll(void (*callback)(void)) { poll_input = callback; }
EXPORT void retro_set_audio_sample(void (*callback)(int16_t, int16_t)) { (void)callback; }
EXPORT void retro_set_audio_sample_batch(size_t (*callback)(const int16_t *, size_t)) { (void)callback; }
EXPORT void retro_get_system_info(struct system_info *info) {
    *info = (struct system_info){"fake-azahar", "1", "3dsx", !mode("bad_fullpath"), false};
}
EXPORT void retro_get_system_av_info(struct av_info *info) {
    *info = (struct av_info){{400, 480, 400, 480, 400.0f / 480}, 60.0, 48000.0};
}
EXPORT void retro_init(void) {
    event("init");
    puts("native diagnostic, not JSON"); fflush(stdout);
    unsigned format = 1; environment(10, &format);
    struct variable definitions[] = {{"citra_graphics_api", "Renderer; OpenGL|Software"},
                                    {"fake_option", "Fixture; first|second"}, {NULL, NULL}};
    if (!environment(16, definitions)) event("bad-options");
    struct variable renderer = {"citra_graphics_api", NULL}, fallback = {"fake_option", NULL};
    if (!environment(15, &renderer) || !environment(15, &fallback)) event("bad-options");
    renderer_option = renderer.value;
    fallback_option = fallback.value;
    if (mode("init_shutdown")) environment(7, NULL);
}
EXPORT bool retro_load_game(const struct game *game) {
    event("load");
    return game && game->path && !mode("reject_load");
}
EXPORT void retro_run(void) {
    event("run");
    if (!renderer_option || strcmp(renderer_option, "Software") != 0 ||
        !fallback_option || strcmp(fallback_option, "first") != 0) event("bad-options");
    if (mode("hang")) {
        for (;;) {
#ifdef _WIN32
            Sleep(100);
#else
            usleep(100000);
#endif
        }
    }
    if (mode("shutdown")) { environment(7, NULL); return; }
    if (mode("callback_failure")) {
        struct geometry invalid = {0, 480, 400, 480, 1.0f};
        environment(37, &invalid);
        return;
    }
    poll_input();
    const uint32_t pixels[] = {0x00ff0000, 0x000000ff};
    video(pixels, 2, 1, sizeof pixels);
    (void)input(0, 1, 0, 8);
}
EXPORT void retro_unload_game(void) { event("unload"); }
EXPORT void retro_deinit(void) { event("deinit"); }
