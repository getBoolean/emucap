/* SPDX-License-Identifier: CC0-1.0; native PAD/WPAD sampling, no motion. */
#include <gccore.h>
#ifdef HW_RVL
#include <wiiuse/wpad.h>
#endif
#include <malloc.h>
#include "lab.h"
typedef struct { uint32_t *rgb; int x,y; } Surface;
static void pixel(void *context,int x,int y,uint32_t rgb) {
    Surface *s=context; s->rgb[(y+s->y)*640+x+s->x]=rgb;
}
static unsigned clamp(int n) { return (unsigned)(n<0?0:n>255?255:n); }
static uint32_t yuv_pair(uint32_t a,uint32_t b) {
    int r=(a>>16)&255,g=(a>>8)&255,blue=a&255;
    unsigned y0=clamp(((66*r+129*g+25*blue+128)>>8)+16);
    int r1=(b>>16)&255,g1=(b>>8)&255,b1=b&255;
    unsigned y1=clamp(((66*r1+129*g1+25*b1+128)>>8)+16);
    r=(r+r1)/2; g=(g+g1)/2; blue=(blue+b1)/2;
    unsigned u=clamp(((-38*r-74*g+112*blue+128)>>8)+128);
    unsigned v=clamp(((112*r-94*g-18*blue+128)>>8)+128);
    return (y0<<24)|(u<<16)|(y1<<8)|v;
}
int main(void) {
    VIDEO_Init(); PAD_Init();
#ifdef HW_RVL
    if (WPAD_Init()<0) return 1;
    for (int port=0;port<4;++port) WPAD_SetDataFormat(port,WPAD_FMT_BTNS);
#endif
    GXRModeObj mode=TVNtsc480IntDf;
    mode.fbWidth=640; mode.efbHeight=480; mode.xfbHeight=480;
    void *xfb[2]={MEM_K0_TO_K1(SYS_AllocateFramebuffer(&mode)),MEM_K0_TO_K1(SYS_AllocateFramebuffer(&mode))};
    uint32_t *rgb=memalign(32,640*480*4);
    if (!xfb[0] || !xfb[1] || !rgb) return 2;
    VIDEO_Configure(&mode); VIDEO_SetNextFramebuffer(xfb[0]); VIDEO_SetBlack(false); VIDEO_Flush();
    VIDEO_WaitVSync(); VIDEO_WaitVSync();
    LabState states[4]={0}; int buffer=1;
    for (;;) {
        PADStatus pads[4]; PAD_Read(pads);
#ifdef HW_RVL
        WPAD_ScanPads();
#endif
        for (unsigned port=0;port<4;++port) {
            LabState *s=&states[port]; s->port=port; s->buttons=0; s->native_buttons=0;
            s->valid=0; memset(s->axes,0,sizeof(s->axes)); memset(s->triggers,0,sizeof(s->triggers));
            s->y_direction=1;
#ifdef HW_RVL
            s->target=7;
            WPADData *data=WPAD_Data((int)port);
            if (data && data->err==WPAD_ERR_NONE) {
                s->valid=LAB_CONNECTED; s->native_buttons=data->btns_h;
                const uint32_t remote[]={WPAD_BUTTON_A,WPAD_BUTTON_B,WPAD_BUTTON_1,WPAD_BUTTON_2,
                    0,0,0,0,WPAD_BUTTON_MINUS,WPAD_BUTTON_PLUS,0,0,
                    WPAD_BUTTON_UP,WPAD_BUTTON_DOWN,WPAD_BUTTON_LEFT,WPAD_BUTTON_RIGHT};
                for (unsigned i=0;i<16;++i) if (data->btns_h&remote[i]) s->buttons|=LAB_BIT(i);
                if (data->btns_h&WPAD_BUTTON_HOME) s->buttons|=LAB_BIT(LAB_HOME);
                if (data->exp.type==WPAD_EXP_NUNCHUK) {
                    s->valid|=LAB_LEFT_STICK;
                    s->axes[0]=(int16_t)((int)data->exp.nunchuk.js.pos.x-data->exp.nunchuk.js.center.x);
                    s->axes[1]=(int16_t)((int)data->exp.nunchuk.js.pos.y-data->exp.nunchuk.js.center.y);
                    s->left_max=128;
                    if (data->btns_h&WPAD_NUNCHUK_BUTTON_C) s->buttons|=LAB_BIT(LAB_L);
                    if (data->btns_h&WPAD_NUNCHUK_BUTTON_Z) s->buttons|=LAB_BIT(LAB_ZL);
                } else if (data->exp.type==WPAD_EXP_CLASSIC) {
                    const uint32_t classic[]={WPAD_CLASSIC_BUTTON_A,WPAD_CLASSIC_BUTTON_B,
                        WPAD_CLASSIC_BUTTON_X,WPAD_CLASSIC_BUTTON_Y,WPAD_CLASSIC_BUTTON_FULL_L,
                        WPAD_CLASSIC_BUTTON_FULL_R,WPAD_CLASSIC_BUTTON_ZL,WPAD_CLASSIC_BUTTON_ZR,
                        WPAD_CLASSIC_BUTTON_MINUS,WPAD_CLASSIC_BUTTON_PLUS,0,0,
                        WPAD_CLASSIC_BUTTON_UP,WPAD_CLASSIC_BUTTON_DOWN,WPAD_CLASSIC_BUTTON_LEFT,WPAD_CLASSIC_BUTTON_RIGHT};
                    for (unsigned i=0;i<16;++i) if (data->btns_h&classic[i]) s->buttons|=LAB_BIT(i);
                    s->valid|=LAB_LEFT_STICK|LAB_RIGHT_STICK|LAB_TRIGGERS;
                    classic_ctrl_t *cc=&data->exp.classic;
                    s->axes[0]=(int16_t)((int)cc->ljs.pos.x-cc->ljs.center.x);
                    s->axes[1]=(int16_t)((int)cc->ljs.pos.y-cc->ljs.center.y);
                    s->axes[2]=(int16_t)((int)cc->rjs.pos.x-cc->rjs.center.x);
                    s->axes[3]=(int16_t)((int)cc->rjs.pos.y-cc->rjs.center.y);
                    s->triggers[0]=cc->ls_raw; s->triggers[1]=cc->rs_raw;
                    s->left_max=32; s->right_max=16; s->trigger_max=31;
                }
            }
            const char *title="WII REMOTE";
#else
            s->target=6;
            if (pads[port].err==PAD_ERR_NONE) {
                PADStatus *p=&pads[port]; s->valid=LAB_CONNECTED|LAB_LEFT_STICK|LAB_RIGHT_STICK|LAB_TRIGGERS;
                s->native_buttons=p->button;
                const uint16_t map[]={PAD_BUTTON_A,PAD_BUTTON_B,PAD_BUTTON_X,PAD_BUTTON_Y,
                    PAD_TRIGGER_L,PAD_TRIGGER_R,0,PAD_TRIGGER_Z,0,PAD_BUTTON_START,0,0,
                    PAD_BUTTON_UP,PAD_BUTTON_DOWN,PAD_BUTTON_LEFT,PAD_BUTTON_RIGHT};
                for (unsigned i=0;i<16;++i) if (p->button&map[i]) s->buttons|=LAB_BIT(i);
                s->axes[0]=p->stickX; s->axes[1]=p->stickY; s->axes[2]=p->substickX; s->axes[3]=p->substickY;
                s->triggers[0]=p->triggerL; s->triggers[1]=p->triggerR;
                s->left_max=127; s->right_max=127; s->trigger_max=255;
            }
            const char *title="GAMECUBE";
#endif
            lab_sample(s);
            Surface surface={rgb,(int)(port%2)*320,(int)(port/2)*240};
            LabCanvas canvas={320,240,&surface,pixel}; lab_render(&canvas,s,title);
        }
        uint32_t *target=xfb[buffer];
        for (unsigned i=0;i<640*480;i+=2) target[i/2]=yuv_pair(rgb[i],rgb[i+1]);
        VIDEO_SetNextFramebuffer(xfb[buffer]); VIDEO_Flush(); VIDEO_WaitVSync(); buffer^=1;
    }
}
