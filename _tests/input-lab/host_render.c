/* SPDX-License-Identifier: CC0-1.0 */
#include "lab.h"
#include <stdlib.h>
typedef struct { unsigned char *bytes; int width; } Image;
static void pixel(void *context,int x,int y,uint32_t rgb) {
    Image *image=context; unsigned char *p=image->bytes+((size_t)y*image->width+x)*3;
    p[0]=(unsigned char)(rgb>>16); p[1]=(unsigned char)(rgb>>8); p[2]=(unsigned char)rgb;
}
int main(int argc,char **argv) {
    if (argc!=4) return 1;
    int width=atoi(argv[2]),height=atoi(argv[3]);
    if (width<160 || width>1280 || height<144 || height>720) return 2;
    Image image={calloc((size_t)width*height,3),width};
    if (!image.bytes) return 3;
    LabCanvas canvas={width,height,&image,pixel};
    LabState state={0}; state.target=1; state.valid=31; state.port=3;
    state.buttons=2; lab_sample(&state);
    state.buttons=0; lab_sample(&state);
    state.buttons=UINT64_C(0x8000000000000009); lab_sample(&state);
    state.native_buttons=UINT64_C(0x1122334455667788);
    state.axes[0]=-32768; state.axes[1]=32767; state.axes[2]=-123; state.axes[3]=456;
    state.triggers[1]=32767; state.left_max=32767; state.right_max=32767;
    state.trigger_max=32767; state.touching=1; state.touch_x=319; state.touch_y=239;
    state.touch_width=320; state.touch_height=240; state.y_direction=1;
    lab_render(&canvas,&state,"HOST TEST");
    FILE *file=fopen(argv[1],"wb"); if (!file) return 4;
    fprintf(file,"P6\n%d %d\n255\n",width,height);
    size_t wrote=fwrite(image.bytes,3,(size_t)width*height,file);
    fclose(file); free(image.bytes); return wrote==(size_t)width*height?0:5;
}
