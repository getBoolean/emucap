/* SPDX-License-Identifier: CC0-1.0
 * Original Input Lab raster UI and guest observation encoder. */
#ifndef INPUT_LAB_H
#define INPUT_LAB_H
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#ifndef LAB_BUILD_ID0
#define LAB_BUILD_ID0 0
#define LAB_BUILD_ID1 0
#define LAB_BUILD_ID2 0
#define LAB_BUILD_ID3 0
#endif

enum { LAB_A, LAB_B, LAB_X, LAB_Y, LAB_L, LAB_R, LAB_ZL, LAB_ZR,
       LAB_MINUS, LAB_PLUS, LAB_LS, LAB_RS, LAB_UP, LAB_DOWN, LAB_LEFT, LAB_RIGHT,
       LAB_SL, LAB_SR, LAB_HOME, LAB_CAPTURE };
#define LAB_BIT(bit) (UINT64_C(1) << (bit))
enum { LAB_CONNECTED=1, LAB_LEFT_STICK=2, LAB_RIGHT_STICK=4,
       LAB_TRIGGERS=8, LAB_TOUCH=16 };
typedef struct {
    uint32_t target, sequence, valid, port;
    uint64_t buttons, native_buttons, pressed_seen, released_seen, previous;
    int16_t axes[4];
    uint16_t triggers[2], touch_x, touch_y, touch_width, touch_height;
    uint32_t left_max, right_max, trigger_max, y_direction, transitions;
    int touching;
} LabState;
typedef void (*LabPixel)(void *, int, int, uint32_t);
typedef struct { int width, height; void *context; LabPixel pixel; } LabCanvas;

static inline void lab_sample(LabState *s) {
    s->pressed_seen |= s->buttons & ~s->previous;
    s->released_seen |= s->previous & ~s->buttons;
    if (s->buttons != s->previous) ++s->transitions;
    s->previous=s->buttons;
    ++s->sequence;
}
static inline uint32_t lab_pair(uint16_t x, uint16_t y) {
    return (uint32_t)x | ((uint32_t)y << 16);
}
static inline void lab_record(const LabState *s, int width, int height, uint32_t out[32]) {
    memset(out, 0, 32*sizeof(uint32_t));
    out[0]=0x494c4142; out[1]=1; out[2]=s->target; out[3]=s->sequence;
    out[4]=(uint32_t)s->buttons; out[5]=(uint32_t)(s->buttons>>32);
    out[6]=(uint32_t)s->native_buttons; out[7]=(uint32_t)(s->native_buttons>>32);
    out[8]=lab_pair((uint16_t)s->axes[0], (uint16_t)s->axes[1]);
    out[9]=lab_pair((uint16_t)s->axes[2], (uint16_t)s->axes[3]);
    out[10]=lab_pair(s->triggers[0],s->triggers[1]);
    out[11]=s->touching ? lab_pair(s->touch_x,s->touch_y) : UINT32_MAX;
    out[12]=s->valid; out[13]=s->port;
    out[14]=(uint32_t)s->pressed_seen; out[15]=(uint32_t)(s->pressed_seen>>32);
    out[16]=(uint32_t)s->released_seen; out[17]=(uint32_t)(s->released_seen>>32);
    out[18]=s->transitions; out[19]=lab_pair((uint16_t)width,(uint16_t)height);
    out[20]=lab_pair(s->touch_width,s->touch_height);
    out[21]=s->left_max; out[22]=s->right_max; out[23]=s->trigger_max;
    out[24]=s->y_direction;
    out[25]=LAB_BUILD_ID0; out[26]=LAB_BUILD_ID1; out[27]=LAB_BUILD_ID2; out[28]=LAB_BUILD_ID3;
    uint32_t crc=UINT32_MAX;
    for (unsigned w=0; w<31; ++w) for (unsigned b=0; b<4; ++b) {
        crc ^= (out[w]>>(b*8)) & 255;
        for (unsigned bit=0; bit<8; ++bit) crc=(crc>>1) ^ (0xedb88320u & (0u-(crc&1)));
    }
    out[31]=~crc;
}
static inline void lab_rect(LabCanvas *c, int x, int y, int w, int h, uint32_t color) {
    for (int j=y; j<y+h && j<c->height; ++j) for (int i=x; i<x+w && i<c->width; ++i)
        if (i>=0 && j>=0) c->pixel(c->context,i,j,color);
}
/* Original 3x5 bitmap glyphs, row-major. No external font dependency. */
static inline unsigned lab_glyph(char ch) {
    static const unsigned letters[]={
        0x5f7a,0x3beb,0x724e,0x3b6b,0x73cf,0x13cf,0x7b4e,0x5bed,0x7497,
        0x2b24,0x5aeb,0x7249,0x5bfd,0x5ffd,0x7b6f,0x12eb,0x6f6f,0x5aeb,
        0x388e,0x2497,0x7b6d,0x256d,0x5fed,0x5aad,0x24ad,0x72a7};
    static const char *digits[]={"111101101101111","010110010010111","111001111100111",
        "111001111001111","101101111001001","111100111001111","111100111101111",
        "111001001001001","111101111101111","111101111001111"};
    if (ch>='a' && ch<='z') ch=(char)(ch-'a'+'A');
    if (ch>='A' && ch<='Z') return letters[ch-'A'];
    if (ch>='0' && ch<='9') {
        unsigned g=0; for (unsigned i=0;i<15;++i) g|=(unsigned)(digits[ch-'0'][i]=='1')<<i;
        return g;
    }
    if (ch=='-') return 7u<<6;
    if (ch=='+') return (7u<<6)|(2u<<3)|(2u<<9);
    if (ch==':') return (2u<<3)|(2u<<9);
    if (ch=='/') return 0x12a4;
    if (ch=='.') return 2u<<12;
    return 0;
}
static inline void lab_text(LabCanvas *c,int x,int y,int scale,const char *text,uint32_t color) {
    for (; *text; ++text,x+=4*scale) {
        unsigned glyph=lab_glyph(*text);
        for (unsigned i=0;i<15;++i) if (glyph&(1u<<i))
            lab_rect(c,x+(int)(i%3)*scale,y+(int)(i/3)*scale,scale,scale,color);
    }
}
static inline void lab_number(LabCanvas *c,int x,int y,int scale,const char *label,long value) {
    char text[48]; snprintf(text,sizeof(text),"%s %ld",label,value);
    lab_text(c,x,y,scale,text,0xe6edf6);
}
static inline void lab_disc(LabCanvas *c,int x,int y,int r,uint32_t color) {
    for (int j=-r;j<=r;++j) for (int i=-r;i<=r;++i)
        if (i*i+j*j<=r*r) lab_rect(c,x+i,y+j,1,1,color);
}
#ifdef LAB_ARTWORK
#include "controller_art.h"
static inline void lab_art(LabCanvas *c,int x,int y,int width) {
    int height=width*LAB_ART_HEIGHT/LAB_ART_WIDTH;
    for (int j=0;j<height;++j) for (int i=0;i<width;++i) {
        uint16_t p=lab_controller_art[(j*LAB_ART_HEIGHT/height)*LAB_ART_WIDTH+i*LAB_ART_WIDTH/width];
        uint32_t rgb=((((p>>11)&31)*255/31)<<16)|((((p>>5)&63)*255/63)<<8)|((p&31)*255/31);
        lab_rect(c,x+i,y+j,1,1,rgb);
    }
}
#endif
static inline void lab_plot(LabCanvas *c,int x,int y,int size,const LabState *s,int axis,uint32_t maximum) {
    lab_rect(c,x,y,size,size,0x15263c);
    lab_rect(c,x+size/2,y,1,size,0x52708f);
    lab_rect(c,x,y+size/2,size,1,0x52708f);
    if (!maximum) return;
    int px=x+size/2+(int)((int32_t)s->axes[axis]*(size/2-3)/(int32_t)maximum);
    int py=y+size/2+(int)((int32_t)s->axes[axis+1]*(size/2-3)/(int32_t)maximum);
    if (s->y_direction==1) py=2*(y+size/2)-py;
    lab_disc(c,px,py,2,0x67e8f9);
}
static inline void lab_draw_record(LabCanvas *c,const LabState *s) {
    uint32_t record[32]; lab_record(s,c->width,c->height,record);
    for (unsigned bit=0;bit<1024;++bit) {
        uint32_t color=(record[bit/32]&(1u<<(bit%32)))?0xffffff:0;
        lab_rect(c,8+(int)(bit%64)*2,c->height-40+(int)(bit/64)*2,2,2,color);
    }
}
static inline void lab_render(LabCanvas *c,const LabState *s,const char *platform) {
    const uint32_t text=0xe6edf6, cyan=0x67e8f9, muted=0xa2b2c9;
    int scale=c->width>=640 ? 3 : 1;
    lab_rect(c,0,0,c->width,c->height,0x101d30);
    lab_text(c,8,7,scale,"INPUT LAB",cyan);
    lab_text(c,c->width/2,7,scale,platform,muted);
    lab_number(c,8,16*scale,scale,"SAMPLE",s->sequence);
    lab_number(c,c->width/2,16*scale,scale,"PORT",s->port);
    if (!(s->valid&LAB_CONNECTED)) lab_text(c,8,23*scale,scale,"DISCONNECTED",0xfcd34d);
    int top=26*scale;
    if (c->width>=320) {
        int art_width=c->width>=640 ? c->width*3/8 : 160;
#ifdef LAB_ARTWORK
        lab_art(c,8,top,art_width);
#endif
        /* Markers follow the original Pro Controller geometry; labels retain
         * platform-neutral control IDs, and this is labeled as a reference. */
        const int positions[16][2]={{462,135},{419,171},{419,97},{377,134},
            {100,46},{449,46},{221,12},{321,12},{207,95},{342,95},
            {124,133},{345,208},{191,183},{191,237},{163,211},{216,211}};
        for (int i=0;i<16;++i) if (s->buttons&LAB_BIT(i))
            lab_disc(c,8+positions[i][0]*art_width/550,top+positions[i][1]*art_width/550,
                     art_width/45,cyan);
        int right=art_width+28, plot=c->width>=640 ? 110 : 50;
        if (s->valid&LAB_LEFT_STICK) lab_plot(c,right,top,plot,s,0,s->left_max);
        if (s->valid&LAB_RIGHT_STICK) lab_plot(c,right+plot+12,top,plot,s,2,s->right_max);
        lab_number(c,right,top+plot+10,scale,"LX",s->axes[0]);
        lab_number(c,right,top+plot+20*scale,scale,"LY",s->axes[1]);
        lab_number(c,right,top+plot+30*scale,scale,"RX",s->axes[2]);
        lab_number(c,right,top+plot+40*scale,scale,"RY",s->axes[3]);
        if (s->valid&LAB_TRIGGERS) {
            lab_number(c,right,top+plot+50*scale,scale,"LT",s->triggers[0]);
            lab_number(c,right,top+plot+60*scale,scale,"RT",s->triggers[1]);
            if (s->trigger_max && c->width>=640) {
                for (int i=0;i<2;++i) {
                    int y=top+plot+(55+i*10)*scale;
                    lab_rect(c,right+180,y,160,5,0x31435f);
                    lab_rect(c,right+180,y,(int)((uint32_t)s->triggers[i]*160/s->trigger_max),5,cyan);
                }
            }
        }
        lab_text(c,8,top+art_width*420/550+8,scale,"PRO CONTROLLER REFERENCE",muted);
    }
    static const char *labels[]={"A","B","X","Y","L","R","ZL","ZR","SEL","START",
                                 "LS","RS","UP","DOWN","LEFT","RIGHT"};
    int cell=c->width/8, row_height=10*scale;
    int grid_y=c->height-42-2*row_height-12*scale;
    if (c->width<320) grid_y=32;
    for (int i=0;i<16;++i) {
        int x=(i%8)*cell+2,y=grid_y+(i/8)*row_height;
        int held=(s->buttons&LAB_BIT(i))!=0;
        lab_rect(c,x,y,cell-3,row_height-2,held?0x67e8f9:0x253b52);
        lab_text(c,x+2,y+2,scale,labels[i],held?0x101d30:text);
    }
    if (c->width<320) {
        lab_number(c,8,56,1,"LX",s->axes[0]); lab_number(c,80,56,1,"LY",s->axes[1]);
        lab_number(c,8,65,1,"RX",s->axes[2]); lab_number(c,80,65,1,"RY",s->axes[3]);
        lab_number(c,8,74,1,"TOUCH",s->touching); lab_number(c,80,74,1,"EDGES",s->transitions);
    }
    char extras[48]; snprintf(extras,sizeof(extras),"SL %u SR %u HOME %u",
        (unsigned)((s->buttons>>LAB_SL)&1),(unsigned)((s->buttons>>LAB_SR)&1),
        (unsigned)((s->buttons>>LAB_HOME)&1));
    lab_text(c,c->width>=320?160:8,c->height-58,1,extras,muted);
    lab_text(c,8,c->height-49,1,"GUEST OBSERVED / NO SELF PASS",muted);
    lab_draw_record(c,s);
}
static inline void lab_touch_render(LabCanvas *c,const LabState *s) {
    lab_rect(c,0,0,c->width,c->height,0x101d30);
    for (int x=0;x<c->width;x+=20) lab_rect(c,x,0,1,c->height,0x31435f);
    for (int y=0;y<c->height;y+=20) lab_rect(c,0,y,c->width,1,0x31435f);
    lab_number(c,8,8,1,"SAMPLE",s->sequence);
    lab_number(c,8,18,1,"TOUCH",s->touching);
    lab_number(c,8,28,1,"X",s->touch_x); lab_number(c,80,28,1,"Y",s->touch_y);
    if (s->touching && s->touch_width && s->touch_height) {
        int x=(int)s->touch_x*c->width/s->touch_width,y=(int)s->touch_y*c->height/s->touch_height;
        lab_rect(c,x-8,y,17,1,0x67e8f9); lab_rect(c,x,y-8,1,17,0x67e8f9);
        lab_disc(c,x,y,3,0x67e8f9);
    }
}
#endif
