// SPDX-License-Identifier: MIT
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using Ryujinx.Graphics.GAL;
using Ryujinx.HLE.HOS.Services.Hid;
using Ryujinx.HLE.HOS.Services.Hid.Types.SharedMemory.TouchScreen;
using Ryujinx.Common.Configuration;

namespace Ryujinx.Headless;

// All effects run in Pump on the SDL owner. Capture bytes are copied during the
// synchronous GPU callback. This object and its delegates outlive renderer shutdown.
internal sealed class EmucapSession : IDisposable
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate uint VersionFn();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate IntPtr CreateFn(ref NativeOptions o, ref Callbacks c, IntPtr error, nuint size);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int HandleFn(IntPtr h, IntPtr error, nuint size);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate void DestroyFn(IntPtr h);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int CompleteFn(IntPtr h, ulong id, uint w, uint height, IntPtr bytes, nuint length, int bgra, int flipX, int flipY, IntPtr error, nuint size);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int FailFn(IntPtr h, ulong id, IntPtr error, nuint size);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int RunningFn(IntPtr user);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate ulong CounterFn(IntPtr user);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int InputFn(IntPtr user, uint buttons, int x, int y, int cx, int cy);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int TouchFn(IntPtr user, int active, uint x, uint y);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int CaptureFn(IntPtr user, ulong id);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int SetRunningFn(IntPtr user, int running);
    [StructLayout(LayoutKind.Sequential)] private struct NativeOptions
    {
        public uint Size, Version;
        [MarshalAs(UnmanagedType.LPUTF8Str)] public string Profile;
        [MarshalAs(UnmanagedType.LPUTF8Str)] public string Renderer;
        [MarshalAs(UnmanagedType.LPUTF8Str)] public string Content;
        [MarshalAs(UnmanagedType.LPUTF8Str)] public string Root;
        [MarshalAs(UnmanagedType.LPUTF8Str)] public string Build;
        [MarshalAs(UnmanagedType.LPUTF8Str)] public string System;
    }
    [StructLayout(LayoutKind.Sequential)] private struct Callbacks
    {
        public uint Size, Version;
        public IntPtr User;
        public RunningFn Running;
        public CounterFn Counter;
        public InputFn Input;
        public TouchFn Touch;
        public CaptureFn Capture;
        public SetRunningFn SetRunning;
    }
    private readonly WindowBase _window;
    private readonly IntPtr _library;
    private readonly HandleFn _pump, _stop;
    private readonly DestroyFn _destroy;
    private readonly CompleteFn _complete;
    private readonly FailFn _fail;
    private readonly Callbacks _callbacks;
    private IntPtr _handle;
    private GamepadInput _input;
    private bool _touch, _previousTouch;
    private uint _x, _y;
    private long _captureId;
    private long _issuedCaptureId;
    private bool _stopped;
    private int _runningState;
    private T Export<T>(string name) where T : Delegate => Marshal.GetDelegateForFunctionPointer<T>(NativeLibrary.GetExport(_library, name));
    private static int Guard(Action action) { try { action(); return 1; } catch { return 0; } }

    internal EmucapSession(WindowBase window, string renderer, string content)
    {
        _window = window;
        Volatile.Write(ref _runningState, window.Device.System.IsPaused ? 0 : 1);
        EmucapStartup.VerifyNative();
        _library = NativeLibrary.Load(Path.Combine(AppContext.BaseDirectory, EmucapBuild.NativeFile));
        if (Export<VersionFn>("emucap_native_abi_version")() != 1) throw new InvalidOperationException("Native ABI mismatch");
        _pump = Export<HandleFn>("emucap_native_pump");
        _stop = Export<HandleFn>("emucap_native_stop");
        _destroy = Export<DestroyFn>("emucap_native_destroy");
        _complete = Export<CompleteFn>("emucap_native_complete_capture");
        _fail = Export<FailFn>("emucap_native_fail_capture");
        _callbacks = new Callbacks {
            Size = (uint)Marshal.SizeOf<Callbacks>(), Version = 1,
            Running = _ => Volatile.Read(ref _runningState),
            Counter = _ => { try { return (ulong)window.Renderer.PresentedFrameCount; } catch { return 0; } },
            Input = (_, buttons, x, y, cx, cy) => Guard(() => {
                if ((buttons & ~0x3ffffu) != 0) throw new ArgumentException("Unsupported button");
                ControllerKeys keys = (ControllerKeys)(buttons & 0xffff);
                if ((buttons & (1u << 16)) != 0) keys |= ControllerKeys.Sl;
                if ((buttons & (1u << 17)) != 0) keys |= ControllerKeys.Sr;
                _input = new GamepadInput { Buttons = keys, LStick = Stick(x, y), RStick = Stick(cx, cy) };
            }),
            Touch = (_, active, x, y) => Guard(() => {
                if (x > 1279 || y > 719) throw new ArgumentException("Touch out of bounds");
                _touch = active != 0;
                if (_touch) { _x = x; _y = y; }
            }),
            Capture = (_, id) => { try { return Interlocked.CompareExchange(ref _captureId, (long)id, 0) == 0 ? 1 : 0; } catch { return 0; } },
            SetRunning = (_, running) => SetRunning(running != 0),
        };
        NativeOptions options = new() {
            Size = (uint)Marshal.SizeOf<NativeOptions>(), Version = 1,
            Profile = EmucapBuild.Profile, Renderer = renderer, Content = content,
            Root = AppDataManager.BaseDirPath, Build = EmucapBuild.AdapterBuild, System = "switch",
        };
        _handle = Export<CreateFn>("emucap_native_create")(ref options, ref _callbacks, IntPtr.Zero, 0);
        if (_handle == IntPtr.Zero) throw new InvalidOperationException("Native bridge rejected frontend identity");
        window.NpadManager.ManagedInput = player => player == PlayerIndex.Player1 ? _input : null;
        window.Renderer.ScreenCaptured += Captured;
    }
    private int SetRunning(bool running)
    {
        try
        {
            _window.Device.System.TogglePauseEmulation(!running);
            // Only the owner touches Horizon. Publish its actual readback for
            // the transport thread after the activity/tick-source effect returns.
            bool paused = _window.Device.System.IsPaused;
            Volatile.Write(ref _runningState, paused ? 0 : 1);
            return paused == !running ? 1 : 0;
        }
        catch { return 0; }
    }
    private static JoystickPosition Stick(int x, int y)
    {
        if (x < -32767 || x > 32767 || y < -32767 || y > 32767) throw new ArgumentException("Stick out of range");
        double magnitude = Math.Sqrt((double)x * x + (double)y * y);
        double scale = magnitude > 32767 ? 32767 / magnitude : 1;
        return new JoystickPosition { Dx = (int)(x * scale), Dy = (int)(y * scale) };
    }
    internal void Pump()
    {
        if (_pump(_handle, IntPtr.Zero, 0) == 0) throw new InvalidOperationException("Native owner pump failed");
    }
    internal void UpdateTouch()
    {
        if (_touch || _previousTouch) _window.Device.Hid.Touchscreen.Update(new TouchPoint {
            Attribute = _touch ? (_previousTouch ? TouchAttribute.None : TouchAttribute.Start) : TouchAttribute.End,
            X = _x, Y = _y, DiameterX = 10, DiameterY = 10, Angle = 90,
        });
        else _window.Device.Hid.Touchscreen.Update();
        _previousTouch = _touch;
    }
    internal void CaptureOnRenderer()
    {
        // Only the GPU loop initiates the renderer's one outstanding capture flag.
        long id = Interlocked.Read(ref _captureId);
        if (id != 0 && id != _issuedCaptureId)
        {
            _issuedCaptureId = id;
            _window.Renderer.Screenshot();
        }
    }
    private unsafe void Captured(object sender, ScreenCaptureImageInfo info)
    {
        ulong id = (ulong)Interlocked.Exchange(ref _captureId, 0);
        if (id == 0) return;
        try {
            fixed (byte* bytes = info.Data) {
                if (_complete(_handle, id, (uint)info.Width, (uint)info.Height, (IntPtr)bytes, (nuint)info.Data.Length,
                    info.IsBgra ? 1 : 0, info.FlipX ? 1 : 0, info.FlipY ? 1 : 0, IntPtr.Zero, 0) != 0) return;
            }
        } catch { }
        _fail(_handle, id, IntPtr.Zero, 0);
    }
    internal void Stop()
    {
        if (_stopped) return;
        _stopped = true;
        if (_stop(_handle, IntPtr.Zero, 0) == 0) throw new InvalidOperationException("Native stop failed");
        UpdateTouch();
        _window.NpadManager.Update();
    }
    public void Dispose()
    {
        // Caller has finished all renderer callbacks and already stopped on owner.
        _window.Renderer.ScreenCaptured -= Captured;
        _window.NpadManager.ManagedInput = null;
        _destroy(_handle);
        _handle = IntPtr.Zero;
        GC.KeepAlive(_callbacks);
        NativeLibrary.Free(_library);
    }
}
