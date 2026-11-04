/* SPDX-License-Identifier: CC0-1.0
 * Original emucap witness: pixels encode guest-observed state, not host metadata. */
#include <3ds.h>
#include <string.h>

static void row(u8 *fb, unsigned y, u32 value) {
    for (unsigned bit = 0; bit < 32; ++bit)
        for (unsigned dy = 0; dy < 8; ++dy)
            for (unsigned dx = 0; dx < 8; ++dx) {
                unsigned p = ((16 + bit * 8 + dx) * 240 + 239 - y - dy) * 3;
                memset(fb + p, (value & (1u << bit)) ? 255 : 0, 3);
            }
}

int main(void) {
    gfxInitDefault();
    gfxSetDoubleBuffering(GFX_TOP, false);
    gfxSetDoubleBuffering(GFX_BOTTOM, false);
    u32 frame = 0;
    while (aptMainLoop()) {
        hidScanInput();
        circlePosition stick = {0};
        touchPosition touch = {0};
        hidCircleRead(&stick);
        hidTouchRead(&touch);
        u32 keys = hidKeysHeld();
        if (keys & KEY_START) break;
        u8 *top = gfxGetFramebuffer(GFX_TOP, GFX_LEFT, NULL, NULL);
        u8 *bottom = gfxGetFramebuffer(GFX_BOTTOM, GFX_LEFT, NULL, NULL);
        memset(top, 48, 400 * 240 * 3);
        memset(bottom, (keys & KEY_TOUCH) ? 192 : 48, 320 * 240 * 3);
        row(top, 16, 0x454d5543); /* EMUC, least significant bit first. */
        row(top, 40, ++frame);
        row(top, 64, keys & KEY_A ? 1 : 0);
        row(top, 88, (u16)stick.dx | ((u32)(u16)stick.dy << 16));
        row(top, 112, (keys & KEY_TOUCH) ? touch.px | ((u32)touch.py << 16) : 0xffffffff);
        row(top, 136, 3); /* Fixture system identity: CTR. */
        gfxFlushBuffers();
        gfxSwapBuffers();
        gspWaitForVBlank();
    }
    gfxExit();
    return 0;
}
