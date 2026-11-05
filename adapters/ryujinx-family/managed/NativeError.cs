// SPDX-License-Identifier: MIT
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace Ryujinx.Headless;

internal sealed class NativeError : IDisposable
{
    internal const int Capacity = 4096;
    internal IntPtr Address { get; private set; } = Marshal.AllocHGlobal(Capacity);
    internal nuint Size => Capacity;

    internal NativeError() => Marshal.WriteByte(Address, 0);

    internal string Message
    {
        get
        {
            byte[] bytes = new byte[Capacity];
            Marshal.Copy(Address, bytes, 0, bytes.Length);
            int end = Array.IndexOf(bytes, (byte)0);
            return Encoding.UTF8.GetString(bytes, 0, end < 0 ? bytes.Length : end);
        }
    }

    internal void Check(bool success, string context)
    {
        if (success) return;
        string detail = Message;
        throw new InvalidOperationException(detail.Length == 0 ? context : context + ": " + detail);
    }

    public void Dispose()
    {
        if (Address == IntPtr.Zero) return;
        Marshal.FreeHGlobal(Address);
        Address = IntPtr.Zero;
    }
}
