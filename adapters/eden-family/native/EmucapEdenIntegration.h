// Copyright 2026 emucap
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "EmucapBridge.h"
#include "EmucapBuildProfile.h"
#include "common/fs/path_util.h"
#include "common/settings.h"
#include "core/frontend/framebuffer_layout.h"
#include "core/hle/kernel/k_process.h"
#include "hid_core/hid_core.h"
#include "input_common/drivers/virtual_gamepad.h"
#include "input_common/drivers/touch_screen.h"
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string_view>

static_assert(EmucapEden::TouchWidth==Layout::ScreenUndocked::Width &&
              EmucapEden::TouchHeight==Layout::ScreenUndocked::Height);

inline bool EmucapPrintBuildProfile(int argc, char** argv) {
    if(argc!=2 || std::string_view{argv[1]}!="--emucap-build-profile") return false;
    std::fputs(EmucapBuildProfileJson,stdout);
    std::fputc('\n',stdout);
    std::fflush(stdout);
    return true;
}

inline void ConfigureEmucap() {
    if(!EmucapEden::Config::Enabled()) return;
    const char* requested=std::getenv("EMUCAP_RENDERER");
    if(!requested) throw std::runtime_error("managed renderer selection is missing");
    Settings::values.renderer_backend.SetGlobal(true);
    if(std::string_view{requested}=="vulkan")
        Settings::values.renderer_backend.SetValue(Settings::RendererBackend::Vulkan);
    else if(std::string_view{requested}=="opengl")
        Settings::values.renderer_backend.SetValue(Settings::RendererBackend::OpenGL_GLSL);
    else throw std::runtime_error("managed renderer must be vulkan or opengl");
    Settings::values.players.SetGlobal(true);
    auto& players=Settings::values.players.GetValue();
    for(auto& player:players) player.connected=false;
    auto& controlled=players.at(0);
    controlled.connected=true;
    controlled.controller_type=Settings::ControllerType::ProController;
    // HID adds virtual_gamepad callbacks independently in ReloadInput. Remove config keyboard/SDL sources.
    controlled.buttons.fill("engine:null");
    controlled.analogs.fill("engine:null");
    controlled.motions.fill("engine:null");
    Settings::values.use_docked_mode.SetGlobal(true);
    Settings::values.use_docked_mode.SetValue(Settings::ConsoleMode::Handheld);
    Settings::values.touchscreen.enabled=true;
    Settings::values.touchscreen.finger=0;
    Settings::values.touchscreen.diameter_x=15;
    Settings::values.touchscreen.diameter_y=15;
    Settings::values.touchscreen.rotation_angle=0;
}

inline void InitializeEmucapInput(Core::System& system,InputCommon::InputSubsystem& input) {
    if(!EmucapEden::Config::Enabled()) return;
    input.GetVirtualGamepad()->ResetControllers();
    input.GetTouchScreen()->TouchReleased(0);
    // The SDL window has registered input engines, and Load has created HID resources.
    system.HIDCore().ReloadInputDevices();
}

template<typename Process>
inline std::string NativeEmucapSystem(const Process* process) {
    if(!process) throw std::runtime_error("no loaded application process for emucap");
    if constexpr(requires {process->IsSwitch2();})
        return process->IsSwitch2()?"switch2":"switch";
    return "switch";
}

inline std::unique_ptr<EmucapEden::Bridge> MakeEmucapBridge(
        Core::System& system, InputCommon::InputSubsystem& input, const std::string& content) {
    if(!EmucapEden::Config::Enabled()) return {};
    std::string renderer;
    switch(Settings::values.renderer_backend.GetValue()) {
    case Settings::RendererBackend::Vulkan: renderer="vulkan";break;
    case Settings::RendererBackend::OpenGL_GLSL:
    case Settings::RendererBackend::OpenGL_GLASM:
    case Settings::RendererBackend::OpenGL_SPIRV: renderer="opengl";break;
    default: throw std::runtime_error("null rendering cannot supply emucap capture");
    }
    auto config=EmucapEden::Config::FromEnvironment(
        EmucapEden::Json::parse(EmucapBuildProfileJson),renderer,content,
        Common::FS::GetEdenPathString(Common::FS::EdenPath::EdenDir),EmucapAdapterBuild,
        NativeEmucapSystem(system.ApplicationProcess()));
    EmucapEden::Hooks hooks;
    hooks.running=[&system]{return !system.IsPaused();};
    hooks.counter=[&system]{return system.Renderer().EmucapPresentCount();};
    hooks.input=[&input](const EmucapEden::InputState& state) {
        using Button=InputCommon::VirtualGamepad::VirtualButton;
        using Stick=InputCommon::VirtualGamepad::VirtualStick;
        static constexpr std::array native_buttons{
            Button::ButtonA,Button::ButtonB,Button::ButtonX,Button::ButtonY,
            Button::StickL,Button::StickR,Button::TriggerL,Button::TriggerR,
            Button::TriggerZL,Button::TriggerZR,Button::ButtonPlus,Button::ButtonMinus,
            Button::ButtonLeft,Button::ButtonUp,Button::ButtonRight,Button::ButtonDown,
            Button::ButtonSL,Button::ButtonSR,Button::ButtonHome,Button::ButtonCapture};
        static_assert(native_buttons.size()==EmucapEden::Buttons.size());
        auto* gamepad=input.GetVirtualGamepad();
        for(size_t index=0;index<state.buttons.size();++index)
            gamepad->SetButtonState(0,native_buttons[index],state.buttons[index]);
        gamepad->SetStickPosition(0,Stick::Left,float(state.axes[0])/32767.0f,float(state.axes[1])/32767.0f);
        gamepad->SetStickPosition(0,Stick::Right,float(state.axes[2])/32767.0f,float(state.axes[3])/32767.0f);
    };
    hooks.touch=[&input](std::optional<EmucapEden::Touch> touch) {
        if(touch) input.GetTouchScreen()->TouchPressed(
            (float(touch->x)+0.5f)/EmucapEden::TouchWidth,
            (float(touch->y)+0.5f)/EmucapEden::TouchHeight,0);
        else input.GetTouchScreen()->TouchReleased(0);
    };
    hooks.capture=[&system](std::shared_ptr<EmucapEden::CaptureBuffer> buffer,
                           std::function<void(bool)> callback) {
        auto& native=system.Renderer();
        if(native.IsScreenshotPending()) throw std::runtime_error("renderer already owns a screenshot");
        native.RequestScreenshot(buffer->pixels.data(),
            [buffer,callback=std::move(callback)](bool invert_y){callback(invert_y);},
            Layout::DefaultFrameLayout(buffer->width,buffer->height));
    };
    return std::make_unique<EmucapEden::Bridge>(std::move(config),std::move(hooks));
}
