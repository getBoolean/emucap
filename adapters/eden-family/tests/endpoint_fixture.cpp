// SPDX-License-Identifier: GPL-3.0-or-later
#include "EmucapBridge.h"
#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <thread>

int Exercise() {
    using namespace EmucapEden;
    using namespace std::chrono_literals;
    const Json profile={{"schema","emucap-emulator-build/v1"},{"family","eden-family"},
        {"bridge_api",1},{"fork","fixture"},{"revision",std::string(40,'a')},
        {"systems",{"switch"}},{"renderers",{"vulkan"}}};
    auto root_utf8=std::filesystem::current_path().u8string();
    auto config=Config::FromEnvironment(profile,"vulkan","homebrew.nro",
        std::string(reinterpret_cast<const char*>(root_utf8.data()),root_utf8.size()),"fixture-build","switch");
    const auto root=std::filesystem::u8path(config.user_root);
    std::atomic<uint64_t> counter{0};std::atomic<bool> running{true};
    Hooks hooks;
    hooks.running=[&]{return running.load();};hooks.counter=[&]{return counter.load();};
    hooks.input=[&](const InputState& value){
        Json data={{"a",value.buttons[0]},{"stick_x",value.axes[0]}};
        std::ofstream(root/"input.json")<<data.dump();
    };
    hooks.touch=[&](std::optional<Touch> value){
        std::ofstream(root/"touch.json")<<(value?Json{{"x",value->x},{"y",value->y}}:Json{}).dump();
    };
    hooks.capture=[&root](std::shared_ptr<CaptureBuffer> buffer,std::function<void(bool)> done){
        int delay=80;
        if(std::ifstream setting(root/"capture_delay_ms");setting) setting>>delay;
        std::thread([buffer,delay,done=std::move(done)]{
            std::this_thread::sleep_for(std::chrono::milliseconds(delay));
            for(size_t i=0;i<buffer->pixels.size();i+=4) {
                buffer->pixels[i+2]=255;
            }
            done(false);
        }).detach();
    };
    Bridge bridge(config,std::move(hooks));
    const auto end=std::chrono::steady_clock::now()+60s;
    while(std::chrono::steady_clock::now()<end&&!std::filesystem::exists(root/"quit")) {
        running=!std::filesystem::exists(root/"paused");
        if(running&&!std::filesystem::exists(root/"stalled")) ++counter;
        bridge.Pump();std::this_thread::sleep_for(5ms);
    }
    bridge.Stop();
    return 0;
}
int main() {
    try {return Exercise();} catch(const std::exception&) {return 64;}
}
