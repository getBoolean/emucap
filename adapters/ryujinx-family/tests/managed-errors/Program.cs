// SPDX-License-Identifier: MIT
using System.Runtime.InteropServices;
using System.Text;
using Ryujinx.Headless;

foreach (string operation in new[] { "creation", "pump", "stop", "capture completion", "capture failure" })
{
    using NativeError error = new();
    string diagnostic = "native " + operation + " rejected: é橋";
    byte[] bytes = Encoding.UTF8.GetBytes(diagnostic + "\0");
    Marshal.Copy(bytes, 0, error.Address, bytes.Length);
    error.Check(true, operation);
    try { error.Check(false, operation); throw new Exception("Missing native failure"); }
    catch (InvalidOperationException failure)
    {
        if (failure.Message != operation + ": " + diagnostic) throw;
    }
}
using (NativeError error = new())
{
    try { error.Check(false, "fallback"); throw new Exception("Missing failure"); }
    catch (InvalidOperationException failure) { if (failure.Message != "fallback") throw; }
    byte[] unterminated = Enumerable.Repeat((byte)'a', NativeError.Capacity).ToArray();
    Marshal.Copy(unterminated, 0, error.Address, unterminated.Length);
    if (error.Message.Length != NativeError.Capacity) throw new Exception("Unbounded error read");
    error.Dispose();error.Dispose();
}
Console.WriteLine("Bounded UTF-8 native error preservation passed.");
