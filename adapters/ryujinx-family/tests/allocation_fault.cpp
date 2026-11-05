// SPDX-License-Identifier: GPL-3.0-or-later
// Linked only into the synthetic ABI fixture, never an emulator build.
#include <atomic>
#include <cstdlib>
#include <new>
namespace {std::atomic<size_t> fail_size{0};}
#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif
extern "C" API void emucap_test_fail_allocation(size_t size) {fail_size=size;}
void* operator new(size_t size) {
    size_t expected=size;
    if(size&&fail_size.compare_exchange_strong(expected,0)) throw std::bad_alloc();
    if(auto* data=std::malloc(size?size:1)) return data;
    throw std::bad_alloc();
}
void* operator new[](size_t size) {return ::operator new(size);}
void operator delete(void* data) noexcept {std::free(data);}
void operator delete[](void* data) noexcept {std::free(data);}
void operator delete(void* data,size_t) noexcept {std::free(data);}
void operator delete[](void* data,size_t) noexcept {std::free(data);}
