// Copyright 2026 emucap
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <array>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>

namespace EmucapEden {
using Json = nlohmann::json;
inline constexpr size_t MaxFrameBytes = 8 * 1024 * 1024;
inline constexpr uint32_t TouchWidth = 1280, TouchHeight = 720;
inline constexpr uint32_t TouchBorder = 15;
inline constexpr uint32_t TouchXMin = TouchBorder, TouchXMax = TouchWidth - TouchBorder - 1;
inline constexpr uint32_t TouchYMin = TouchBorder, TouchYMax = TouchHeight - TouchBorder - 1;
inline constexpr std::array<const char*,20> Buttons{
    "a","b","x","y","lstick","rstick","l","r","zl","zr",
    "plus","minus","left","up","right","down","sl","sr","home","capture"};
inline constexpr std::array<const char*,4> Axes{"stick_x","stick_y","cstick_x","cstick_y"};
struct InputState {
    std::array<bool,20> buttons{};
    std::array<int,4> axes{};
};
struct Touch { uint32_t x{}, y{}; };
InputState DecodeInput(const Json& params);
std::optional<Touch> DecodeTouch(const Json& params);
std::vector<uint8_t> EncodePng(uint32_t width, uint32_t height,
                               const std::vector<uint8_t>& bgra, bool invert_y);
std::string Base64(const std::vector<uint8_t>& bytes);

struct WaitState {
    uint64_t requested, start, timeout_ms;
    WaitState(uint64_t count, uint64_t initial, uint64_t timeout);
    bool Complete(uint64_t current) const;
    Json Terminal(uint64_t current, const char* status) const;
};

struct CaptureBuffer {
    uint32_t width = TouchWidth, height = TouchHeight;
    std::vector<uint8_t> pixels = std::vector<uint8_t>(size_t(width) * height * 4);
};
struct Hooks {
    // These observation callbacks must read native atomics and remain valid until Stop returns.
    std::function<bool()> running;
    std::function<uint64_t()> counter;
    // Effects are called only from Pump/Stop on the SDL owner thread.
    std::function<void(const InputState&)> input;
    std::function<void(std::optional<Touch>)> touch;
    // The renderer retains the supplied buffer and callback until completion/teardown.
    std::function<void(std::shared_ptr<CaptureBuffer>, std::function<void(bool)>)> capture;
};
struct Config {
    uint16_t port{};
    std::string front_key, launch_id, system, renderer, content, user_root, adapter_build;
    Json build_profile;
    static bool Enabled();
    static Config FromEnvironment(Json profile, std::string renderer,
                                  std::string content, std::string effective_root,
                                  std::string adapter_build, std::string native_system);
};

class Bridge {
public:
    Bridge(Config config, Hooks hooks);
    ~Bridge();
    Bridge(const Bridge&) = delete;
    Bridge& operator=(const Bridge&) = delete;
    void Pump();
    void Stop();
private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
} // namespace EmucapEden
