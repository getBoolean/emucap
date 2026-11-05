/* SPDX-License-Identifier: CC0-1.0 */
#include <switch.h>
#include "lab.h"
#ifdef __SWITCH2__
size_t __nx_heap_size=64*1024*1024;
#endif
typedef struct { u32 *pixels; u32 stride; } Surface;
static void pixel(void *context,int x,int y,uint32_t rgb) {
    Surface *s=context;
    s->pixels[y*s->stride+x]=0xff000000u|((rgb&255)<<16)|(rgb&0xff00)|(rgb>>16);
}
int main(void) {
    padConfigureInput(1,HidNpadStyleSet_NpadStandard);
    PadState pad; padInitializeDefault(&pad); hidInitializeTouchScreen();
    Framebuffer fb;
    if (R_FAILED(framebufferCreate(&fb,nwindowGetDefault(),1280,720,PIXEL_FORMAT_RGBA_8888,2))) return 1;
    framebufferMakeLinear(&fb);
    LabState state={0};
#ifdef __SWITCH2__
    state.target=2;
#else
    state.target=1;
#endif
    state.left_max=32767; state.right_max=32767; state.y_direction=1;
    state.touch_width=1280; state.touch_height=720;
    const u64 mapping[]={HidNpadButton_A,HidNpadButton_B,HidNpadButton_X,HidNpadButton_Y,
        HidNpadButton_L,HidNpadButton_R,HidNpadButton_ZL,HidNpadButton_ZR,
        HidNpadButton_Minus,HidNpadButton_Plus,HidNpadButton_StickL,HidNpadButton_StickR,
        HidNpadButton_Up,HidNpadButton_Down,HidNpadButton_Left,HidNpadButton_Right,
        HidNpadButton_LeftSL|HidNpadButton_RightSL,HidNpadButton_LeftSR|HidNpadButton_RightSR};
    while (appletMainLoop()) {
        padUpdate(&pad);
        state.valid=LAB_TOUCH|(padIsConnected(&pad)?LAB_CONNECTED|LAB_LEFT_STICK|LAB_RIGHT_STICK:0);
        state.native_buttons=padGetButtons(&pad); state.buttons=0;
        for (unsigned i=0;i<sizeof(mapping)/sizeof(mapping[0]);++i)
            if (state.native_buttons&mapping[i]) state.buttons|=LAB_BIT(i);
        for (unsigned i=0;i<2;++i) { HidAnalogStickState stick=padGetStickPos(&pad,i);
            state.axes[i*2]=(int16_t)stick.x; state.axes[i*2+1]=(int16_t)stick.y; }
        HidTouchScreenState touch={0};
        state.touching=hidGetTouchScreenStates(&touch,1)>0 && touch.count>0;
        if (state.touching) { state.touch_x=(uint16_t)touch.touches[0].x; state.touch_y=(uint16_t)touch.touches[0].y; }
        lab_sample(&state);
        Surface surface; u32 stride;
        surface.pixels=framebufferBegin(&fb,&stride); surface.stride=stride/4;
        LabCanvas canvas={1280,720,&surface,pixel};
        lab_render(&canvas,&state,state.target==2?"SWITCH 2":"SWITCH");
        if (state.touching) {
            lab_number(&canvas,850,380,3,"TOUCH X",state.touch_x);
            lab_number(&canvas,850,410,3,"TOUCH Y",state.touch_y);
            lab_disc(&canvas,state.touch_x,state.touch_y,8,0xc4b5fd);
            lab_draw_record(&canvas,&state);
        }
        framebufferEnd(&fb);
    }
    framebufferClose(&fb); return 0;
}
