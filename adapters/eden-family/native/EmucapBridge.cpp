// Copyright 2026 emucap
// SPDX-License-Identifier: GPL-3.0-or-later
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
#endif
#include "EmucapBridge.h"
#include "emucap_front_auth.h"
#include "emucap_native_failure.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cerrno>
#include <condition_variable>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace EmucapEden {
namespace {
using Clock = std::chrono::steady_clock;
using namespace std::chrono_literals;
#ifdef _WIN32
using Socket = SOCKET;
constexpr Socket InvalidSocket = INVALID_SOCKET;
void Close(Socket socket) { closesocket(socket); }
#else
using Socket = int;
constexpr Socket InvalidSocket = -1;
void Close(Socket socket) { close(socket); }
#endif
Json Error(uint64_t id, const std::string& kind, const std::string& message) {
    return {{"id",id},{"ok",false},{"error",{{"kind",kind},{"message",message}}}};
}
Json Success(uint64_t id, Json result) {
    return {{"id",id},{"ok",true},{"result",std::move(result)}};
}
uint64_t Number(const Json& object, const char* key, uint64_t fallback) {
    if (!object.contains(key)) return fallback;
    if (!object[key].is_number_unsigned() &&
        !(object[key].is_number_integer() && object[key].get<int64_t>()>=0))
        throw std::invalid_argument(std::string(key)+" must be unsigned");
    return object[key].get<uint64_t>();
}
void Port(const Json& params) {
    if (!params.is_object() || Number(params,"port",0) != 0)
        throw std::invalid_argument("only controller port zero is supported");
}
void U32(std::vector<uint8_t>& bytes, uint32_t value) {
    for (int shift=24; shift>=0; shift-=8) bytes.push_back(uint8_t(value>>shift));
}
uint32_t Crc(const uint8_t* data, size_t size) {
    uint32_t crc=0xffffffff;
    for (size_t i=0;i<size;++i) {
        crc ^= data[i];
        for(int bit=0;bit<8;++bit) crc=(crc>>1)^((crc&1)?0xedb88320:0);
    }
    return ~crc;
}
void Chunk(std::vector<uint8_t>& output, const char* type, const std::vector<uint8_t>& data) {
    U32(output,uint32_t(data.size()));
    const auto start=output.size();
    output.insert(output.end(),type,type+4);
    output.insert(output.end(),data.begin(),data.end());
    U32(output,Crc(output.data()+start,output.size()-start));
}
std::string Env(const char* name) {
#ifdef _WIN32
    const std::wstring wide_name(name,name+std::char_traits<char>::length(name));
    const wchar_t* wide_value=_wgetenv(wide_name.c_str());
    if(!wide_value) return {};
    const int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide_value,-1,nullptr,0,nullptr,nullptr);
    if(size<=0) throw std::runtime_error("invalid Unicode environment value");
    std::string value(size_t(size),'\0');
    WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide_value,-1,value.data(),size,nullptr,nullptr);
    value.pop_back();return value;
#else
    const char* value=std::getenv(name);
    return value?value:"";
#endif
}
bool Has(const Json& values, const std::string& value) {
    return values.is_array() && std::find(values.begin(),values.end(),Json(value))!=values.end();
}
bool Readable(Socket socket,int timeout_ms) {
    fd_set set; FD_ZERO(&set); FD_SET(socket,&set);
    timeval timeout{timeout_ms/1000,(timeout_ms%1000)*1000};
    return select(int(socket)+1,&set,nullptr,nullptr,&timeout)>0;
}
bool Connect(Socket socket,const sockaddr_in& address,const std::atomic<bool>& stop) {
#ifdef _WIN32
    u_long nonblocking=1;
    if(ioctlsocket(socket,FIONBIO,&nonblocking)!=0) return false;
#else
    const int original=fcntl(socket,F_GETFL,0);
    if(original<0||fcntl(socket,F_SETFL,original|O_NONBLOCK)!=0) return false;
#endif
    bool connected=connect(socket,reinterpret_cast<const sockaddr*>(&address),sizeof(address))==0;
    if(!connected) {
#ifdef _WIN32
        if(WSAGetLastError()!=WSAEWOULDBLOCK) return false;
#else
        if(errno!=EINPROGRESS) return false;
#endif
        const auto deadline=Clock::now()+2s;
        while(!stop&&Clock::now()<deadline) {
            fd_set writable;FD_ZERO(&writable);FD_SET(socket,&writable);
            fd_set failed=writable;timeval timeout{0,25000};
            const int ready=select(int(socket)+1,nullptr,&writable,&failed,&timeout);
            if(ready<0) return false;
            if(ready==0) continue;
            int error=0;
#ifdef _WIN32
            int size=sizeof(error);
            if(getsockopt(socket,SOL_SOCKET,SO_ERROR,reinterpret_cast<char*>(&error),&size)!=0) return false;
#else
            socklen_t size=sizeof(error);
            if(getsockopt(socket,SOL_SOCKET,SO_ERROR,&error,&size)!=0) return false;
#endif
            connected=error==0;break;
        }
    }
#ifdef _WIN32
    nonblocking=0;
    if(ioctlsocket(socket,FIONBIO,&nonblocking)!=0) return false;
#else
    if(fcntl(socket,F_SETFL,original)!=0) return false;
#endif
    return connected&&!stop;
}
bool WriteBytes(Socket socket,const uint8_t* data,size_t size) {
    const auto deadline=Clock::now()+5s;
    while(size) {
        if(Clock::now()>=deadline) return false;
        fd_set set; FD_ZERO(&set); FD_SET(socket,&set); timeval timeout{0,25000};
        if(select(int(socket)+1,nullptr,&set,nullptr,&timeout)<=0) continue;
#ifdef MSG_NOSIGNAL
        constexpr int flags=MSG_NOSIGNAL;
#else
        constexpr int flags=0;
#endif
        const int count=send(socket,reinterpret_cast<const char*>(data),int(std::min(size,size_t(65536))),flags);
        if(count<=0) return false;
        data+=count; size-=size_t(count);
    }
    return true;
}
bool WriteJson(Socket socket,const Json& value) {
    std::string bytes=value.dump();
    if(bytes.size()>MaxFrameBytes) return false;
    bytes+='\n';
    return WriteBytes(socket,reinterpret_cast<const uint8_t*>(bytes.data()),bytes.size());
}
bool ValidKey(const Json& key,const std::string& runtime) {
    if(!key.is_object() || key.size()!=3 || !key.contains("runtime") || key["runtime"]!=runtime) return false;
    for(const auto* name:{"runtime","owner_id","operation_id"}) {
        if(!key.contains(name)||!key[name].is_string()) return false;
        auto value=key[name].get<std::string>();
        if(value.empty()||value.size()>256) return false;
    }
    return true;
}
bool ValidAttachment(const Json& value) {
    return value.is_object() && value.size()==3 && value.contains("broker_instance") &&
        value["broker_instance"].is_string() && !value["broker_instance"].get<std::string>().empty() &&
        value["broker_instance"].get<std::string>().size()<=256 &&
        Number(value,"registration",0)>0 && Number(value,"session",0)>0;
}
} // namespace

InputState DecodeInput(const Json& params) {
    Port(params); InputState result;
    if(params.contains("frames")&&!params["frames"].is_null())
        throw std::invalid_argument("timed controller input is unsupported; replace persistent state explicitly");
    auto buttons=params.value("buttons",Json::array());
    if(!buttons.is_array()) throw std::invalid_argument("buttons must be an array");
    for(const auto& button:buttons) {
        if(!button.is_string()) throw std::invalid_argument("button must be a string");
        auto name=button.get<std::string>();
        auto found=std::find(Buttons.begin(),Buttons.end(),name);
        if(found==Buttons.end()) throw std::invalid_argument("unadvertised button");
        result.buttons[size_t(found-Buttons.begin())]=true;
    }
    auto axes=params.value("axes",Json::object());
    if(!axes.is_object()) throw std::invalid_argument("axes must be an object");
    for(auto it=axes.begin();it!=axes.end();++it) {
        auto found=std::find(Axes.begin(),Axes.end(),it.key());
        if(found==Axes.end()||!it.value().is_number_integer()||it.value() < -32767||it.value() > 32767)
            throw std::invalid_argument("unadvertised axis or out-of-range axis value");
        result.axes[size_t(found-Axes.begin())]=it.value().get<int>();
    }
    return result;
}
std::optional<Touch> DecodeTouch(const Json& params) {
    Port(params);
    if(params.contains("frames")&&!params["frames"].is_null())
        throw std::invalid_argument("timed touch is unsupported; hold and release explicitly");
    if(params.contains("release")&&!params["release"].is_boolean()) throw std::invalid_argument("release must be boolean");
    if(params.value("release",false)) return {};
    const auto x=Number(params,"x",TouchWidth), y=Number(params,"y",TouchHeight);
    if(x<TouchXMin||x>TouchXMax||y<TouchYMin||y>TouchYMax)
        throw std::invalid_argument("touch exceeds advertised native HID bounds");
    return Touch{uint32_t(x),uint32_t(y)};
}
std::vector<uint8_t> EncodePng(uint32_t width,uint32_t height,const std::vector<uint8_t>& bgra,bool invert_y) {
    if(width==0||height==0||width>1920||height>1080||bgra.size()!=size_t(width)*height*4)
        throw std::invalid_argument("invalid screenshot dimensions/buffer");
    std::vector<uint8_t> raw; raw.reserve((size_t(width)*3+1)*height);
    for(uint32_t y=0;y<height;++y) {
        raw.push_back(0);
        auto offset=size_t(invert_y?height-1-y:y)*width*4;
        for(uint32_t x=0;x<width;++x,offset+=4) {
            raw.push_back(bgra[offset+2]); raw.push_back(bgra[offset+1]); raw.push_back(bgra[offset]);
        }
    }
    std::vector<uint8_t> compressed{0x78,0x01};
    for(size_t offset=0;offset<raw.size();) {
        const auto size=uint16_t(std::min(raw.size()-offset,size_t(65535)));
        compressed.push_back(offset+size==raw.size()?1:0);
        compressed.push_back(uint8_t(size)); compressed.push_back(uint8_t(size>>8));
        compressed.push_back(uint8_t(~size)); compressed.push_back(uint8_t((~size)>>8));
        compressed.insert(compressed.end(),raw.begin()+offset,raw.begin()+offset+size); offset+=size;
    }
    uint32_t a=1,b=0;
    for(auto byte:raw) {a=(a+byte)%65521;b=(b+a)%65521;}
    U32(compressed,(b<<16)|a);
    std::vector<uint8_t> output{137,80,78,71,13,10,26,10},header;
    U32(header,width);U32(header,height);header.insert(header.end(),{8,2,0,0,0});
    Chunk(output,"IHDR",header);Chunk(output,"IDAT",compressed);Chunk(output,"IEND",{});
    if(output.size()>((MaxFrameBytes-65536)*3/4)) throw std::runtime_error("screenshot exceeds inline limit");
    return output;
}
std::string Base64(const std::vector<uint8_t>& data) {
    constexpr char digits[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string result;result.reserve((data.size()+2)/3*4);
    for(size_t i=0;i<data.size();i+=3) {
        const uint32_t v=uint32_t(data[i])<<16 | (i+1<data.size()?uint32_t(data[i+1])<<8:0) | (i+2<data.size()?data[i+2]:0);
        result+=digits[(v>>18)&63];result+=digits[(v>>12)&63];
        result+=i+1<data.size()?digits[(v>>6)&63]:'=';result+=i+2<data.size()?digits[v&63]:'=';
    }
    return result;
}
WaitState::WaitState(uint64_t count,uint64_t initial,uint64_t timeout):requested(count),start(initial),timeout_ms(timeout) {
    if(count==0||count>5000||timeout==0||timeout>250000) throw std::invalid_argument("wait exceeds advertised bounds");
}
bool WaitState::Complete(uint64_t current) const { return current>=start&&current-start>=requested; }
Json WaitState::Terminal(uint64_t current,const char* status) const {
    if(current<start) throw std::runtime_error("native render counter went backwards");
    const auto observed=current-start;
    return {{"status",status},{"domain","native_render_present"},{"requested",requested},
        {"start",start},{"end",current},{"observed",observed},
        {"overshoot",observed>requested?observed-requested:0},{"state","running"}};
}
bool Config::Enabled() {return !Env("EMUCAP_PORT").empty();}
Config Config::FromEnvironment(Json profile,std::string renderer,std::string content,std::string effective_root,std::string adapter_build,std::string native_system) {
    std::ifstream expected_file(std::filesystem::u8path(Env("EMUCAP_BUILD_PROFILE")),std::ios::binary);
    std::string expected_bytes;
    char byte;
    while(expected_file.get(byte)) {
        if(expected_bytes.size()>=65536) throw std::invalid_argument("build profile exceeds limit");
        expected_bytes+=byte;
    }
    if(expected_file.bad()||expected_bytes.empty()||Json::parse(expected_bytes,nullptr,false)!=profile)
        throw std::invalid_argument("selected build profile differs from compiled native profile");
    const auto port_text=Env("EMUCAP_PORT");size_t end=0;
    const auto port_value=std::stoul(port_text,&end);
    Config result{uint16_t(port_value),Env("EMUCAP_SESSION_TOKEN"),Env("EMUCAP_LAUNCH_ID"),
        Env("EMUCAP_SYSTEM"),std::move(renderer),std::move(content),std::move(effective_root),std::move(adapter_build),std::move(profile)};
    if(end!=port_text.size()||port_value==0||port_value>65535||
        !emucap_front_auth::detail::ValidLaunchId(result.launch_id)||
        emucap_front_auth::detail::Boundary(result.front_key)==0||result.content.empty()||
        !std::filesystem::u8path(result.user_root).is_absolute()||
        std::filesystem::weakly_canonical(std::filesystem::u8path(result.user_root))!=std::filesystem::weakly_canonical(std::filesystem::u8path(Env("EMUCAP_USER_ROOT")))||
        result.build_profile.value("schema","")!="emucap-emulator-build/v1"||
        result.build_profile.value("family","")!="eden-family"||result.build_profile.value("bridge_api",0)!=1||
        result.system!=native_system||result.adapter_build.empty()||!Has(result.build_profile["systems"],result.system)||!Has(result.build_profile["renderers"],result.renderer))
        throw std::invalid_argument("managed Eden bridge environment/build mismatch");
    if(Env("EMUCAP_RENDERER")!=result.renderer)
        throw std::invalid_argument("selected renderer differs from native renderer");
    return result;
}

struct Bridge::Impl {
    struct Job { Json request;std::mutex mutex;std::optional<Json> response; };
    struct CaptureState {
        std::mutex mutex;
        bool active=true,pending=false;
        uint64_t sequence=0;
        std::optional<Json> last;
    };
    Config config;Hooks hooks;
    std::atomic<bool> stop{false};
    std::atomic<Socket> active_socket{InvalidSocket};
    std::mutex socket_mutex;
    std::thread thread;
    std::mutex queue_mutex;
    std::deque<std::shared_ptr<Job>> queue;
    std::shared_ptr<CaptureState> capture=std::make_shared<CaptureState>();
    explicit Impl(Config c,Hooks h):config(std::move(c)),hooks(std::move(h)) {}
    static void Finish(const std::shared_ptr<Job>& job,Json response) {
        std::lock_guard lock(job->mutex);job->response=std::move(response);
    }
    [[noreturn]] void Retire(const char* reason) {
        emucap_publish_native_failure("eden-family-native",config.adapter_build.c_str(),
            hooks.counter(),"control_cleanup",reason,true,"unknown");
        std::_Exit(70);
    }
    std::shared_ptr<Job> Submit(Json request) {
        auto job=std::make_shared<Job>();job->request=std::move(request);
        std::lock_guard lock(queue_mutex);
        if(queue.size()>=8) throw std::runtime_error("native owner queue is full");
        queue.push_back(job);return job;
    }
    Json Hello() const {
        Json axes=Json::object();for(auto name:Axes) axes[name]={{"minimum",-32767},{"neutral",0},{"maximum",32767}};
        Json result={{"protocol_version",1},{"adapter","eden-family-native"},{"system",config.system},
            {"build",config.adapter_build},{"host_build",config.build_profile},
            {"renderer",config.renderer},{"content",config.content},{"launch_id",config.launch_id},
            {"host_features",{"native_input","native_render_present","single_touch","owned_capture"}},
            {"methods",{"hello","status","get_rom_info","set_input","touch","screenshot","wait_for_running_frames","cancel_operation"}},
            {"contracts",{{"catalog","emucap-feature-contracts/v3"},{"active_exceptions",{"eden.input-touch.persistent-only"}}}},
            {"input_buttons",Buttons},
            {"input_axes",{{"semantics","complete_persistent_controller_state"},{"ports",Json::array({{{"port",0},{"axes",axes}}})}}},
            {"touch_capability",{{"ports",{0}},{"width",TouchWidth},{"height",TouchHeight},{"coordinate_space","touchscreen"},{"contacts",1},
                {"bounds",{{"x_min",TouchXMin},{"x_max",TouchXMax},{"y_min",TouchYMin},{"y_max",TouchYMax}}}}},
            {"progress_capability",{{"domain","native_render_present"},{"max_count",5000},{"max_timeout_ms",250000},{"overshoot",true},{"running_only",true}}},
            {"temporal_cancellation_capability",{{"methods",{"wait_for_running_frames"}},{"control_service_ms",25},{"stop_host_ms",500}}},
            {"control_session_lifecycle",true},{"managed_user_root",config.user_root},
            {"capability_notes",Json::array({"Experimental source bridge; no exact stepping or deterministic execution claim.",
                "Progress counts nonempty native renderer Composite events, not guest frames, GPU completion or instructions.",
                "Capture uses the last completed image when paused; no implicit resume."})}};
        if(!Env("EMUCAP_NAME").empty()) result["name"]=Env("EMUCAP_NAME");
        return result;
    }
    Json Status() const {
        const bool running=hooks.running();
        auto result=Hello();result["connected"]=true;result["state"]=running?"running":"paused";
        result["paused"]=!running;result["frozen"]=false;
        result["native_render_present"]=hooks.counter();return result;
    }
    void Owner(const std::shared_ptr<Job>& job) {
        const auto id=job->request["id"].get<uint64_t>();
        try {
            const auto method=job->request["method"].get<std::string>();
            const auto& params=job->request["params"];
            if(method=="_release") { hooks.input({});hooks.touch({});Finish(job,Success(id,{{"released",true}})); }
            else if(method=="set_input") { auto input=DecodeInput(params);hooks.input(input);Finish(job,Success(id,{{"input_set",true},{"port",0}})); }
            else if(method=="touch") { auto value=DecodeTouch(params);hooks.touch(value);Finish(job,Success(id,{{"released",!value.has_value()},{"port",0}})); }
            else if(method=="screenshot") {
                std::unique_lock lock(capture->mutex);
                if(!hooks.running()) {
                    if(!capture->last) throw std::runtime_error("no completed image available while paused");
                    auto image=*capture->last;image["fresh"]=false;Finish(job,Success(id,std::move(image)));return;
                }
                if(capture->pending) {Finish(job,Error(id,"busy","a renderer capture is pending"));return;}
                auto pixels=std::make_shared<CaptureBuffer>();auto shared=capture;
                const auto request_counter=hooks.counter();
                const auto capture_id=config.launch_id+"-capture-"+std::to_string(++capture->sequence);
                capture->pending=true;
                lock.unlock();
                hooks.capture(pixels,[shared,pixels,job,id,request_counter,capture_id](bool invert_y) {
                    try {
                        auto png=EncodePng(pixels->width,pixels->height,pixels->pixels,invert_y);
                        auto image=Json{{"width",pixels->width},{"height",pixels->height},{"png_base64",Base64(png)},
                            {"format","png"},{"capture_domain","native_render_present"},
                            {"capture_request_counter",request_counter},{"capture_id",capture_id},{"fresh",true}};
                        std::lock_guard guard(shared->mutex);shared->pending=false;
                        if(shared->active) {shared->last=image;Finish(job,Success(id,std::move(image)));}
                    } catch(const std::exception& error) {
                        std::lock_guard guard(shared->mutex);shared->pending=false;
                        if(shared->active) Finish(job,Error(id,"capture_failed",error.what()));
                    }
                });
            } else Finish(job,Error(id,"unsupported","operation is not implemented by the native bridge"));
        } catch(const std::exception& error) {
            if(job->request["method"]=="screenshot") {std::lock_guard lock(capture->mutex);capture->pending=false;}
            Finish(job,Error(id,"bad_params",error.what()));
        }
    }
    void Pump() {
        std::deque<std::shared_ptr<Job>> jobs;
        {std::lock_guard lock(queue_mutex);jobs.swap(queue);}
        for(auto& job:jobs) Owner(job);
    }
    bool Receive(Socket socket,std::string& pending,std::deque<Json>& messages) {
        char bytes[4096];const int count=recv(socket,bytes,sizeof(bytes),0);
        if(count<=0) return false;
        for(int index=0;index<count;++index) {
            if(bytes[index]=='\n') {
                if(pending.empty()) continue;
                auto value=Json::parse(pending,nullptr,false);pending.clear();
                if(value.is_discarded()||messages.size()>=8) return false;
                messages.push_back(std::move(value));
            } else {if(pending.size()>=MaxFrameBytes) return false;pending+=bytes[index];}
        }
        return true;
    }
    void ReleaseOwned() {
        if(stop) return;
        auto release=Submit({{"id",0},{"method","_release"},{"params",Json::object()}});
        const auto deadline=Clock::now()+500ms;
        while(!stop&&Clock::now()<deadline) {
            {std::lock_guard lock(release->mutex);if(release->response) return;}
            std::this_thread::sleep_for(5ms);
        }
        if(!stop) Retire("native owner did not verify input release before reconnect");
    }
    bool Serve(Socket socket) {
        std::string pending;std::deque<Json> messages;
        std::shared_ptr<Job> active;
        std::optional<WaitState> wait;
        Json wait_key,attachment,registration;bool broker=false;
        uint64_t wait_id=0;auto deadline=Clock::now();auto working=Clock::now();
        bool dirty=false;
        while(!stop) {
            if(active) {
                std::optional<Json> result;
                {std::lock_guard lock(active->mutex);if(active->response) result=std::move(active->response);}
                if(result) {if(!WriteJson(socket,*result)) break;active.reset();}
                else if(Clock::now()>=deadline) {
                    if(active->request["method"]=="screenshot") {
                        if(!WriteJson(socket,Error(active->request["id"].get<uint64_t>(),"timeout","renderer capture did not complete; storage remains owned"))) break;
                        active.reset();
                    } else Retire("native owner failed to complete admitted input operation");
                }
            }
            if(wait) {
                const auto current=hooks.counter();
                const char* terminal=nullptr;
                if(!hooks.running()) {if(!WriteJson(socket,Error(wait_id,"bad_state","guest stopped running during observed wait"))) break;wait.reset();}
                else if(wait->Complete(current)) terminal="completed";
                else if(Clock::now()>=deadline) terminal="timed_out";
                if(wait&&terminal) {if(!WriteJson(socket,Success(wait_id,wait->Terminal(current,terminal)))) break;wait.reset();}
            }
            if((wait||active)&&Clock::now()>=working) {
                if(!WriteJson(socket,Success(wait?wait_id:active->request["id"].get<uint64_t>(),{{"status","working"}}))) break;
                working=Clock::now()+1s;
            }
            if(messages.empty()) {
                if(!Readable(socket,25)) continue;
                if(!Receive(socket,pending,messages)) break;
            }
            if(messages.empty()) continue;
            auto request=std::move(messages.front());messages.pop_front();
            uint64_t id=0;
            try {
                if(request.contains("_control_session")) {
                    const auto& event=request["_control_session"];
                    if(request.size()!=1||event.value("runtime","")!=config.launch_id||!ValidAttachment(event["attachment"])) break;
                    const auto kind=event.value("kind","");
                    if(kind=="attach") {
                        const auto& next=event["attachment"];
                        const auto identity=Json{{"broker_instance",next["broker_instance"]},{"registration",next["registration"]}};
                        if(!broker) {if(dirty) ReleaseOwned();broker=true;registration=identity;}
                        else if(registration!=identity) break;
                        if(!attachment.is_null()&&attachment!=event["attachment"]) break;
                        attachment=event["attachment"];
                    } else if(kind=="detach") {
                        if(attachment==event["attachment"]) {
                            if(wait) {if(!WriteJson(socket,Success(wait_id,wait->Terminal(hooks.counter(),"interrupted")))) break;wait.reset();}
                            ReleaseOwned();dirty=false;active.reset();attachment=nullptr;
                        }
                    } else break;
                    continue;
                }
                if(!request.is_object()||!request.contains("v")||!request["v"].is_number_unsigned()||request["v"]!=1||
                    !request.contains("id")||!request["id"].is_number_unsigned()||
                    !request.contains("method")||!request["method"].is_string()) break;
                id=request["id"].get<uint64_t>();const auto method=request["method"].get<std::string>();
                auto params=request.value("params",Json::object());if(params.is_null()) params=Json::object();
                if(!params.is_object()||request.contains("_control_attachment")||params.contains("_control_session")) break;
                const bool stamped=params.contains("_control_attachment");
                if(stamped!=broker||(broker&&(attachment.is_null()||params["_control_attachment"]!=attachment))) break;
                params.erase("_control_attachment");
                if(method=="cancel_operation") {
                    if(!ValidKey(params,config.launch_id)) {if(!WriteJson(socket,Error(id,"bad_params","invalid cancellation identity"))) break;continue;}
                    const bool matching=wait&&params==wait_key;
                    if(!WriteJson(socket,Success(id,{{"status",matching?"requested":"not_active"}}))) break;
                    if(matching) {if(!WriteJson(socket,Success(wait_id,wait->Terminal(hooks.counter(),"interrupted")))) break;wait.reset();}
                    continue;
                }
                if(active||wait) {if(!WriteJson(socket,Error(id,"busy","another operation is active"))) break;continue;}
                if(params.contains("_control")&&(method!="wait_for_running_frames"||!ValidKey(params["_control"],config.launch_id))) {
                    if(!WriteJson(socket,Error(id,"bad_params","invalid temporal method or identity"))) break;
                    continue;
                }
                if(params.contains("_temporal_owner")) {if(!WriteJson(socket,Error(id,"unsupported","parent temporal scopes are unsupported"))) break;continue;}
                if(method=="hello"||method=="status") {if(!WriteJson(socket,Success(id,method=="hello"?Hello():Status()))) break;}
                else if(method=="get_rom_info") {if(!WriteJson(socket,Success(id,{{"path",config.content},{"system",config.system},{"content",config.content}}))) break;}
                else if(method=="wait_for_running_frames") {
                    if(!hooks.running()) {if(!WriteJson(socket,Error(id,"bad_state","observed wait requires an already running guest"))) break;continue;}
                    wait.emplace(Number(params,"frames",0),hooks.counter(),Number(params,"timeout_ms",30000));
                    wait_key=params.value("_control",Json());wait_id=id;
                    deadline=Clock::now()+std::chrono::milliseconds(wait->timeout_ms);working=Clock::now()+1s;
                } else if(method=="set_input"||method=="touch"||method=="screenshot") {
                    request["params"]=std::move(params);active=Submit(std::move(request));
                    if(method!="screenshot") dirty=true;
                    deadline=Clock::now()+(method=="screenshot"?5s:500ms);working=Clock::now()+1s;
                } else if(!WriteJson(socket,Error(id,"unsupported","operation is unavailable"))) break;
            } catch(const std::exception& error) {
                if(!WriteJson(socket,Error(id,"bad_params",error.what()))) break;
            }
        }
        if(dirty||active) ReleaseOwned();
        return false;
    }
    void Run() {
#ifdef _WIN32
        WSADATA data{};if(WSAStartup(MAKEWORD(2,2),&data)!=0) return;
#endif
        while(!stop) {
            Socket socket=::socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);
            if(socket==InvalidSocket) break;
            sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(config.port);address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
            if(Connect(socket,address,stop)) {
                {std::lock_guard lock(socket_mutex);active_socket=socket;}
#ifdef _WIN32
                DWORD send_timeout=25;
                setsockopt(socket,SOL_SOCKET,SO_SNDTIMEO,reinterpret_cast<const char*>(&send_timeout),sizeof(send_timeout));
#else
                timeval send_timeout{0,25000};
                setsockopt(socket,SOL_SOCKET,SO_SNDTIMEO,&send_timeout,sizeof(send_timeout));
#endif
                const auto auth_deadline=Clock::now()+5s;
                const auto read=[&](uint8_t* bytes,size_t size) {
                    while(size&&!stop&&Clock::now()<auth_deadline) {
                        if(!Readable(socket,25)) continue;
                        const int count=recv(socket,reinterpret_cast<char*>(bytes),int(size),0);
                        if(count<=0) return false;
                        bytes+=count;size-=size_t(count);
                    }
                    return size==0;
                };
                const auto write=[&](const uint8_t* bytes,size_t size) {return WriteBytes(socket,bytes,size);};
                if(emucap_front_auth::Authenticate(config.front_key,config.launch_id,config.port,read,write)) Serve(socket);
                {std::lock_guard lock(socket_mutex);active_socket=InvalidSocket;Close(socket);}
                socket=InvalidSocket;
            }
            if(socket!=InvalidSocket) Close(socket);
            for(int i=0;i<20&&!stop;++i) std::this_thread::sleep_for(10ms);
        }
#ifdef _WIN32
        WSACleanup();
#endif
    }
};
Bridge::Bridge(Config config,Hooks hooks):impl(std::make_unique<Impl>(std::move(config),std::move(hooks))) {
    impl->thread=std::thread([this]{impl->Run();});
}
Bridge::~Bridge() {Stop();}
void Bridge::Pump() {impl->Pump();}
void Bridge::Stop() {
    if(!impl||impl->stop.exchange(true)) return;
    {std::lock_guard lock(impl->capture->mutex);impl->capture->active=false;}
    impl->hooks.input({});impl->hooks.touch({});
    {
    std::lock_guard lock(impl->socket_mutex);
    const auto socket=impl->active_socket.load();
    if(socket!=InvalidSocket) {
#ifdef _WIN32
        shutdown(socket,SD_BOTH);
#else
        shutdown(socket,SHUT_RDWR);
#endif
    }
    }
    if(impl->thread.joinable()) impl->thread.join();
}
} // namespace EmucapEden
