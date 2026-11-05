/* SPDX-License-Identifier: CC0-1.0; DS and GBA share keypad bit positions. */
#ifdef ARM9
#include <nds.h>
#else
#include <gba.h>
static uint16_t framebuffer[240*160] EWRAM_BSS __attribute__((aligned(4)));
#endif
#include "lab.h"
static void pixel(void *context,int x,int y,uint32_t rgb) {
#ifdef ARM9
    ((volatile uint16_t *)context)[y*256+x]=(uint16_t)(0x8000|((rgb>>19)&31)|((rgb>>6)&0x3e0)|((rgb<<7)&0x7c00));
#else
    ((volatile uint16_t *)context)[y*240+x]=(uint16_t)(((rgb>>19)&31)|((rgb>>6)&0x3e0)|((rgb<<7)&0x7c00));
#endif
}
int main(void) {
    LabState state={0}; state.valid=LAB_CONNECTED;
#ifdef ARM9
    videoSetMode(MODE_5_2D); videoSetModeSub(MODE_5_2D);
    vramSetBankA(VRAM_A_MAIN_BG); vramSetBankC(VRAM_C_SUB_BG);
    int top_bg=bgInit(3,BgType_Bmp16,BgSize_B16_256x256,0,0);
    int bottom_bg=bgInitSub(3,BgType_Bmp16,BgSize_B16_256x256,0,0);
    LabCanvas top={256,192,bgGetGfxPtr(top_bg),pixel};
    LabCanvas bottom={256,192,bgGetGfxPtr(bottom_bg),pixel};
    state.target=4; state.valid|=LAB_TOUCH; state.touch_width=256; state.touch_height=192;
#else
    irqInit(); irqEnable(IRQ_VBLANK); SetMode(MODE_3|BG2_ENABLE);
    LabCanvas top={240,160,framebuffer,pixel}; state.target=5;
#endif
    /* A B Select Start Right Left Up Down R L are identical native positions. */
    const unsigned native_bits[]={0,1,16,16,9,8,16,16,2,3,16,16,6,7,5,4};
    for (;;) {
#ifdef ARM9
        swiWaitForVBlank(); scanKeys(); uint32_t keys=keysHeld();
        touchPosition touch={0}; touchRead(&touch); state.touching=(keys&KEY_TOUCH)!=0;
        if (state.touching) { state.touch_x=touch.px; state.touch_y=touch.py; }
#else
        scanKeys(); uint32_t keys=keysHeld();
#endif
        state.native_buttons=keys; state.buttons=0;
        for (unsigned i=0;i<16;++i) if (keys&(1u<<native_bits[i])) state.buttons|=LAB_BIT(i);
#ifdef ARM9
        if (keys&KEY_X) state.buttons|=LAB_BIT(LAB_X);
        if (keys&KEY_Y) state.buttons|=LAB_BIT(LAB_Y);
#endif
        lab_sample(&state); lab_render(&top,&state,state.target==4?"DS":"GBA");
#ifdef ARM9
        lab_touch_render(&bottom,&state);
#else
        /* Render off-screen; publish complete pixels from EWRAM at VBlank. */
        VBlankIntrWait();
        DMA3COPY(framebuffer, (void *)0x06000000, DMA32 | (sizeof(framebuffer)/4));
#endif
    }
}
