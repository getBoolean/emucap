// SPDX-License-Identifier: GPL-3.0-or-later
#include "EmucapBridge.h"
#include <cassert>
#include <iostream>

using namespace EmucapEden;
int main() {
    auto state = DecodeInput(Json{{"port",0},{"buttons",{"a","plus"}},
                                 {"axes",{{"stick_x",-32767},{"cstick_y",32767}}}});
    assert(state.buttons[0] && state.buttons[10]);
    assert(state.axes[0] == -32767 && state.axes[3] == 32767);
    for (const auto& bad : {Json{{"port",1}}, Json{{"buttons",{"unknown"}}},
                           Json{{"axes",{{"stick_x",32768}}}}, Json{{"buttons","a"}}}) {
        bool failed = false;
        try { (void)DecodeInput(bad); } catch (const std::exception&) { failed = true; }
        assert(failed);
    }
    auto touch = DecodeTouch(Json{{"port",0},{"x",1264},{"y",704},{"release",false}});
    assert(touch && touch->x == 1264 && touch->y == 704);
    touch = DecodeTouch(Json{{"port",0},{"x",15},{"y",15}});
    assert(touch && touch->x == 15 && touch->y == 15);
    assert(!DecodeTouch(Json{{"release",true}}));
    for (const auto& bad : {Json{{"x",0},{"y",0},{"frames",1}},Json{{"release","true"}},
                           Json{{"x",0},{"y",0}},Json{{"x",1279},{"y",719}},
                           Json{{"x",14},{"y",15}},Json{{"x",1265},{"y",704}}}) {
        bool failed=false;
        try { (void)DecodeTouch(bad); } catch(const std::exception&) { failed=true; }
        assert(failed);
    }
    bool timed_input_rejected=false;
    try { DecodeInput(Json{{"frames",1}}); } catch(...) { timed_input_rejected=true; }
    assert(timed_input_rejected);
    bool rejected = false;
    try { DecodeTouch(Json{{"x",1280},{"y",0}}); } catch (...) { rejected = true; }
    assert(rejected);
    WaitState wait(10, 50, 1000);
    auto progress = wait.Terminal(62, "completed");
    assert(progress["domain"] == "native_render_present");
    assert(progress["observed"] == 12 && progress["overshoot"] == 2);
    assert(!wait.Complete(59) && wait.Complete(60));
    auto pixels = std::vector<uint8_t>{0,0,255,0, 255,0,0,0};
    auto png = EncodePng(1,2,pixels,false);
    assert(png.size() > 40 && png[0] == 137 && png[1] == 80);
    assert(EncodePng(1,2,pixels,true) != png);
    rejected = false;
    try { EncodePng(4096,4096,pixels,false); } catch (...) { rejected = true; }
    assert(rejected);
    std::cout << "native input, touch, observed-progress and PNG tests passed\n";
}
