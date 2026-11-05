// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <condition_variable>
#include <functional>
#include <mutex>
#include <optional>
#include <thread>

namespace EmucapEden {
// One active and at most one queued job. Bridge capture admission remains single-flight.
class CaptureEncoder {
    std::mutex mutex;
    std::condition_variable ready;
    std::optional<std::function<void()>> pending;
    bool closed=false;
    std::thread worker;
public:
    CaptureEncoder():worker([this] {
        std::unique_lock lock(mutex);
        for(;;) {
            ready.wait(lock,[this] {return closed||pending.has_value();});
            if(closed) return;
            auto task=std::move(*pending);pending.reset();
            lock.unlock();task();task={};lock.lock();
        }
    }) {}
    ~CaptureEncoder() {Close();Join();}
    CaptureEncoder(const CaptureEncoder&)=delete;
    CaptureEncoder& operator=(const CaptureEncoder&)=delete;
    bool Submit(std::function<void()> task) {
        std::lock_guard lock(mutex);
        if(closed||pending) return false;
        pending=std::move(task);ready.notify_one();return true;
    }
    void Close() {
        std::lock_guard lock(mutex);closed=true;pending.reset();ready.notify_one();
    }
    void Join() {if(worker.joinable()) worker.join();}
};
}
