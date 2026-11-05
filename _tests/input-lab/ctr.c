/* SPDX-License-Identifier: CC0-1.0 */
#include <3ds.h>
#include "lab.h"
static void pixel(void *context,int x,int y,uint32_t rgb) {
    u8 *p=(u8 *)context+((x*240)+(239-y))*3;
    p[0]=(u8)rgb; p[1]=(u8)(rgb>>8); p[2]=(u8)(rgb>>16);
}
int main(void) {
    gfxInitDefault(); gfxSetDoubleBuffering(GFX_TOP,false); gfxSetDoubleBuffering(GFX_BOTTOM,false);
    int has_ir=R_SUCCEEDED(irrstInit());
    LabState state={0}; state.target=3; state.valid=LAB_CONNECTED|LAB_LEFT_STICK|LAB_TOUCH;
    if (has_ir) state.valid|=LAB_RIGHT_STICK;
    state.left_max=156; state.right_max=156; state.y_direction=1;
    state.touch_width=320; state.touch_height=240;
    const u32 mapping[]={KEY_A,KEY_B,KEY_X,KEY_Y,KEY_L,KEY_R,KEY_ZL,KEY_ZR,
        KEY_SELECT,KEY_START,0,0,KEY_DUP,KEY_DDOWN,KEY_DLEFT,KEY_DRIGHT};
    while (aptMainLoop()) {
        hidScanInput(); if (has_ir) irrstScanInput();
        u32 keys=hidKeysHeld()|(has_ir?irrstKeysHeld():0);
        state.native_buttons=keys; state.buttons=0;
        for (unsigned i=0;i<16;++i) if (keys&mapping[i]) state.buttons|=LAB_BIT(i);
        circlePosition stick={0},right={0}; hidCircleRead(&stick);
        if (has_ir) irrstCstickRead(&right);
        state.axes[0]=stick.dx; state.axes[1]=stick.dy; state.axes[2]=right.dx; state.axes[3]=right.dy;
        touchPosition touch={0}; hidTouchRead(&touch); state.touching=(keys&KEY_TOUCH)!=0;
        if (state.touching) { state.touch_x=touch.px; state.touch_y=touch.py; }
        lab_sample(&state);
        LabCanvas top={400,240,gfxGetFramebuffer(GFX_TOP,GFX_LEFT,NULL,NULL),pixel};
        LabCanvas bottom={320,240,gfxGetFramebuffer(GFX_BOTTOM,GFX_LEFT,NULL,NULL),pixel};
        lab_render(&top,&state,"3DS"); lab_touch_render(&bottom,&state);
        gfxFlushBuffers(); gfxSwapBuffers(); gspWaitForVBlank();
    }
    if (has_ir) irrstExit();
    gfxExit(); return 0;
}
