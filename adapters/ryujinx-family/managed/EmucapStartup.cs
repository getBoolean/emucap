// SPDX-License-Identifier: MIT
using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.Json;

namespace Ryujinx.Headless;

internal static class EmucapStartup
{
    internal static bool Enabled => !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("EMUCAP_PORT"));
    internal static string Root { get; private set; }
    internal static bool Enter(string[] args)
    {
        if (args.Contains("--emucap-build-profile"))
        {
            VerifyNative();
            Console.WriteLine(EmucapBuild.Profile);
            return true;
        }
        if (!Enabled) return false;
        VerifyNative();
        Root = Path.GetFullPath(Environment.GetEnvironmentVariable("EMUCAP_USER_ROOT") ?? throw new InvalidOperationException("Missing managed root"));
        Directory.CreateDirectory(Root);
        if ((File.GetAttributes(Root) & FileAttributes.ReparsePoint) != 0) throw new InvalidOperationException("Managed root must not be a link");
        if (!args.Contains("--no-gui")) throw new InvalidOperationException("Managed launch requires the headless frontend");
        return false;
    }
    internal static void VerifyNative()
    {
        string path = Path.Combine(AppContext.BaseDirectory, EmucapBuild.NativeFile);
        string actual = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        if (!string.Equals(actual, EmucapBuild.NativeSha256, StringComparison.Ordinal)) throw new InvalidOperationException("Native bridge hash does not match the compiled build");
    }
    internal static void Configure(Options options)
    {
        if (!Enabled) return;
        options.BaseDataDir = Root;
        options.InheritConfig = false;
        options.DisableMainInputConfig = true;
        options.DisableDockedMode = true;
        options.EnableKeyboard = false;
        options.EnableMouse = false;
        string path = Path.Combine(Root, "emucap-config.json");
        if (!File.Exists(path)) return;
        using JsonDocument document = JsonDocument.Parse(File.ReadAllBytes(path));
        if (document.RootElement.ValueKind != JsonValueKind.Object) throw new InvalidOperationException("Managed config must be an object");
        foreach (JsonProperty field in document.RootElement.EnumerateObject())
        {
            if (field.Name != "preferred_gpu_vendor" || field.Value.ValueKind != JsonValueKind.String)
                throw new InvalidOperationException("Unsupported managed config field: " + field.Name);
            string vendor = field.Value.GetString();
            if (vendor.Length > 128 || vendor.Any(char.IsControl)) throw new InvalidOperationException("Invalid GPU vendor");
            options.PreferredGPUVendor = vendor;
        }
    }
}
