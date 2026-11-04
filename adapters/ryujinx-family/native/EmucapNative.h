// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
#include <stddef.h>
#ifdef _WIN32
#define EMUCAP_API __declspec(dllexport)
#define EMUCAP_CALL __cdecl
#else
#define EMUCAP_API __attribute__((visibility("default")))
#define EMUCAP_CALL
#endif
#ifdef __cplusplus
extern "C" {
#endif
#define EMUCAP_NATIVE_ABI_VERSION 1u
typedef struct EmucapNativeHandle EmucapNativeHandle;
typedef struct EmucapNativeOptions {
    uint32_t struct_size;
    uint32_t abi_version;
    const char *profile_json;
    const char *renderer;
    const char *content;
    const char *effective_user_root;
    const char *adapter_build;
    const char *native_system;
} EmucapNativeOptions;
// Strings are UTF-8, copied during create. Callbacks use Cdecl and must not throw.
// Effects return nonzero only on success. Observation callbacks read native atomics.
typedef struct EmucapNativeCallbacks {
    uint32_t struct_size;
    uint32_t abi_version;
    void *user;
    int32_t (EMUCAP_CALL *running)(void *user);
    uint64_t (EMUCAP_CALL *counter)(void *user);
    int32_t (EMUCAP_CALL *input)(void *user, uint32_t buttons, int32_t stick_x,
                               int32_t stick_y, int32_t cstick_x, int32_t cstick_y);
    int32_t (EMUCAP_CALL *touch)(void *user, int32_t active, uint32_t x, uint32_t y);
    int32_t (EMUCAP_CALL *request_capture)(void *user, uint64_t request_id);
    int32_t (EMUCAP_CALL *set_running)(void *user, int32_t running); // optional
} EmucapNativeCallbacks;
EMUCAP_API uint32_t EMUCAP_CALL emucap_native_abi_version(void);
EMUCAP_API EmucapNativeHandle *EMUCAP_CALL emucap_native_create(
    const EmucapNativeOptions *options, const EmucapNativeCallbacks *callbacks,
    char *error, size_t error_size);
// Pump and stop run on the frontend owner thread; do not run them concurrently.
EMUCAP_API int32_t EMUCAP_CALL emucap_native_pump(EmucapNativeHandle *, char *error, size_t error_size);
// Stop releases input and joins the transport. It does not destroy the handle.
EMUCAP_API int32_t EMUCAP_CALL emucap_native_stop(EmucapNativeHandle *, char *error, size_t error_size);
// Stop while owner/input is alive, finish renderer callbacks, then destroy.
// No calls, including late capture completion, may overlap or follow destroy.
EMUCAP_API void EMUCAP_CALL emucap_native_destroy(EmucapNativeHandle *);
// Completion copies caller-pinned bytes synchronously; it may race stop.
// Exactly width*height*4 tightly packed bytes, bounded to 8 MiB. Flags are 0/1.
EMUCAP_API int32_t EMUCAP_CALL emucap_native_complete_capture(EmucapNativeHandle *,
    uint64_t request_id, uint32_t width, uint32_t height, const uint8_t *data,
    size_t length, int32_t is_bgra, int32_t flip_x, int32_t flip_y,
    char *error, size_t error_size);
EMUCAP_API int32_t EMUCAP_CALL emucap_native_fail_capture(EmucapNativeHandle *,
    uint64_t request_id, char *error, size_t error_size);
#ifdef __cplusplus
}
#endif
