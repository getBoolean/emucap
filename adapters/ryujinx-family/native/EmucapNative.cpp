// SPDX-License-Identifier: GPL-3.0-or-later
#include "EmucapNative.h"
#include "../../eden-family/native/EmucapBridge.h"
#include <algorithm>
#include <cstring>
#include <mutex>
#include <stdexcept>

using namespace EmucapEden;
struct EmucapNativeHandle {
    EmucapNativeCallbacks callbacks{};
    std::unique_ptr<Bridge> bridge;
    std::mutex mutex;
    bool stopped=false;
    uint64_t next_id=0, pending_id=0;
    std::shared_ptr<CaptureBuffer> pixels;
    std::function<void(bool)> complete;
};
namespace {
void Error(char* target,size_t size,const char* message) noexcept {
    if(target&&size) {const auto count=std::min(size-1,std::strlen(message));
        std::memcpy(target,message,count);target[count]=0;}
}
template<class F> int32_t Guard(char* error,size_t size,F action) noexcept {
    Error(error,size,"");
    try {action();return 1;}
    catch(const std::exception& exception) {Error(error,size,exception.what());}
    catch(...) {Error(error,size,"unknown native bridge failure");}
    return 0;
}
const char* Required(const char* value) {
    if(!value||!*value) throw std::invalid_argument("missing native bridge option");
    return value;
}
void Handle(EmucapNativeHandle* handle) {
    if(!handle) throw std::invalid_argument("null native bridge handle");
}
void Effect(int32_t success) {
    if(!success) throw std::runtime_error("frontend rejected native effect");
}
void Pending(EmucapNativeHandle* handle,uint64_t id) {
    if(handle->stopped||!id||id!=handle->pending_id)
        throw std::invalid_argument("capture request is no longer pending");
}
}
extern "C" {
uint32_t EMUCAP_CALL emucap_native_abi_version(void) {return EMUCAP_NATIVE_ABI_VERSION;}
EmucapNativeHandle* EMUCAP_CALL emucap_native_create(const EmucapNativeOptions* options,
    const EmucapNativeCallbacks* callbacks,char* error,size_t size) {
    EmucapNativeHandle* result=nullptr;
    Guard(error,size,[&] {
        if(!options||!callbacks||options->struct_size!=sizeof(*options)||
            callbacks->struct_size!=sizeof(*callbacks)||options->abi_version!=EMUCAP_NATIVE_ABI_VERSION||
            callbacks->abi_version!=EMUCAP_NATIVE_ABI_VERSION)
            throw std::invalid_argument("native ABI version or structure size mismatch");
        if(!callbacks->running||!callbacks->counter||!callbacks->input||!callbacks->touch||!callbacks->request_capture)
            throw std::invalid_argument("missing required native callback");
        auto config=Config::FromEnvironment(Json::parse(Required(options->profile_json)),
            Required(options->renderer),Required(options->content),Required(options->effective_user_root),
            Required(options->adapter_build),Required(options->native_system),"ryujinx-family");
        auto owned=std::make_unique<EmucapNativeHandle>();auto* handle=owned.get();
        handle->callbacks=*callbacks;
        Hooks hooks;
        hooks.running=[handle] {return handle->callbacks.running(handle->callbacks.user)!=0;};
        hooks.counter=[handle] {return handle->callbacks.counter(handle->callbacks.user);};
        hooks.input=[handle](const InputState& value) {
            uint32_t mask=0;for(size_t i=0;i<value.buttons.size();++i) if(value.buttons[i]) mask|=1u << i;
            Effect(handle->callbacks.input(handle->callbacks.user,mask,value.axes[0],value.axes[1],value.axes[2],value.axes[3]));
        };
        hooks.touch=[handle](std::optional<Touch> value) {
            Effect(handle->callbacks.touch(handle->callbacks.user,value.has_value(),value?value->x:0,value?value->y:0));
        };
        if(callbacks->set_running) hooks.set_running=[handle](bool running) {
            return handle->callbacks.set_running(handle->callbacks.user,running)!=0;
        };
        hooks.capture=[handle](std::shared_ptr<CaptureBuffer> pixels,std::function<void(bool)> done) {
            uint64_t id;
            {std::lock_guard lock(handle->mutex);
                if(handle->stopped||handle->pending_id) throw std::runtime_error("capture unavailable");
                id=++handle->next_id;handle->pending_id=id;
                handle->pixels=std::move(pixels);handle->complete=std::move(done);}
            if(!handle->callbacks.request_capture(handle->callbacks.user,id)) {
                std::lock_guard lock(handle->mutex);
                if(handle->pending_id==id) {
                    handle->pending_id=0;handle->pixels.reset();handle->complete={};
                }
                throw std::runtime_error("frontend rejected renderer capture");
            }
        };
        handle->bridge=std::make_unique<Bridge>(std::move(config),std::move(hooks));
        result=owned.release();
    });
    return result;
}
int32_t EMUCAP_CALL emucap_native_pump(EmucapNativeHandle* handle,char* error,size_t size) {
    return Guard(error,size,[&] {Handle(handle);
        {std::lock_guard lock(handle->mutex);if(handle->stopped) throw std::runtime_error("native bridge stopped");}
        handle->bridge->Pump();});
}
int32_t EMUCAP_CALL emucap_native_stop(EmucapNativeHandle* handle,char* error,size_t size) {
    return Guard(error,size,[&] {Handle(handle);
        {std::lock_guard lock(handle->mutex);handle->stopped=true;
            handle->pending_id=0;handle->pixels.reset();handle->complete={};}
        handle->bridge->Stop();});
}
void EMUCAP_CALL emucap_native_destroy(EmucapNativeHandle* handle) {
    if(!handle) return;
    // Frontend must already have joined renderer callbacks before destroying.
    emucap_native_stop(handle,nullptr,0);delete handle;
}
int32_t EMUCAP_CALL emucap_native_complete_capture(EmucapNativeHandle* handle,uint64_t id,
    uint32_t width,uint32_t height,const uint8_t* data,size_t length,int32_t bgra,
    int32_t flip_x,int32_t flip_y,char* error,size_t size) {
    return Guard(error,size,[&] {Handle(handle);std::lock_guard lock(handle->mutex);Pending(handle,id);
        if(!width||!height||width>1920||height>1080||
            uint64_t(width)*height*4>MaxFrameBytes||length!=uint64_t(width)*height*4||!data||
            (bgra!=0&&bgra!=1)||(flip_x!=0&&flip_x!=1)||(flip_y!=0&&flip_y!=1))
            throw std::invalid_argument("invalid capture dimensions, bytes or layout flags");
        auto& pixels=*handle->pixels;pixels.width=width;pixels.height=height;pixels.pixels.resize(length);
        for(uint32_t y=0;y<height;++y) for(uint32_t x=0;x<width;++x) {
            const size_t source=(size_t(flip_y?height-1-y:y)*width+(flip_x?width-1-x:x))*4;
            const size_t dest=(size_t(y)*width+x)*4;
            pixels.pixels[dest]=data[source+(bgra?0:2)];pixels.pixels[dest+1]=data[source+1];
            pixels.pixels[dest+2]=data[source+(bgra?2:0)];pixels.pixels[dest+3]=data[source+3];
        }
        auto done=std::move(handle->complete);handle->pending_id=0;handle->pixels.reset();done(false);
    });
}
int32_t EMUCAP_CALL emucap_native_fail_capture(EmucapNativeHandle* handle,uint64_t id,char* error,size_t size) {
    return Guard(error,size,[&] {Handle(handle);std::lock_guard lock(handle->mutex);Pending(handle,id);
        handle->pixels->pixels.clear();auto done=std::move(handle->complete);
        handle->pending_id=0;handle->pixels.reset();done(false);
    });
}
}
