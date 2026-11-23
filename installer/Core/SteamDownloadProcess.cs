// Runs the official downloader with live QR/progress output. In QR mode stdin
// is closed so a missing saved token can never block on a password prompt.
using System;
using System.Diagnostics;
using System.Text.RegularExpressions;

namespace PerditionSteam025 {
    public sealed class DownloadResult {
        public int ExitCode;
        public bool Authenticated;
        public bool PasswordRequired;
        public bool TokenRejected;
        public bool AuthenticationFailed;
        public bool AuthPollMissing;
        public string AccountName = "";
    }

    public static class DownloadProcess {
        public static DownloadResult Run(string executable, string arguments, string workingDirectory) {
            var result = new DownloadResult();
            var gate = new object();
            using (var process = new Process()) {
                process.StartInfo = new ProcessStartInfo {
                    FileName = executable,
                    Arguments = arguments,
                    WorkingDirectory = workingDirectory,
                    UseShellExecute = false,
                    RedirectStandardInput = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    // The official .NET 9 program uses the inherited Windows
                    // console code page (often OEM 437), including QR blocks.
                    // Assuming UTF-8 here would corrupt an otherwise valid QR.
                    StandardOutputEncoding = Console.OutputEncoding,
                    StandardErrorEncoding = Console.OutputEncoding,
                    CreateNoWindow = true
                };
                DataReceivedEventHandler receive = delegate(object sender, DataReceivedEventArgs ev) {
                    if (ev.Data == null) return;
                    string line = Regex.Replace(ev.Data, @"\x1b\[[0-?]*[ -/]*[@-~]", "");
                    lock (gate) {
                        // Program.InitializeSteam requests this only when the
                        // official account store has no token for the account.
                        // Suppress the prompt and report fresh-QR recovery.
                        if (line.IndexOf("Enter account password for", StringComparison.OrdinalIgnoreCase) >= 0) {
                            result.PasswordRequired = true;
                            try { process.Kill(); } catch (InvalidOperationException) { }
                            return;
                        }
                        var success = Regex.Match(line, @"^Success! Next time you can login with -username (.+?) -remember-password instead of -qr\.$");
                        var logging = Regex.Match(line, @"^Logging '(.+)' into Steam3\.\.\.$");
                        if (success.Success) result.AccountName = success.Groups[1].Value;
                        else if (logging.Success) result.AccountName = logging.Groups[1].Value;
                        if (line.StartsWith("Using Steam3 suggested CellID:", StringComparison.Ordinal) ||
                            Regex.IsMatch(line, @"^Got [0-9]+ licenses for account!$")) result.Authenticated = true;
                        if (line.IndexOf("Access token was rejected", StringComparison.OrdinalIgnoreCase) >= 0)
                            result.TokenRejected = true;
                        if (line.IndexOf("Failed to authenticate with Steam:", StringComparison.OrdinalIgnoreCase) >= 0 ||
                            line.IndexOf("Unable to login to Steam3:", StringComparison.OrdinalIgnoreCase) >= 0)
                            result.AuthenticationFailed = true;
                        if (line.IndexOf("Failed to poll status with result FileNotFound", StringComparison.OrdinalIgnoreCase) >= 0)
                            result.AuthPollMissing = true;
                        Console.WriteLine(ev.Data);
                    }
                };
                process.OutputDataReceived += receive;
                process.ErrorDataReceived += receive;
                bool started = false;
                try {
                    process.Start(); started = true;
                    process.BeginOutputReadLine();
                    process.BeginErrorReadLine();
                    process.StandardInput.Close();
                    process.WaitForExit();
                    result.ExitCode = process.ExitCode;
                } finally {
                    if (started) {
                        try { if (!process.HasExited) process.Kill(); }
                        catch (InvalidOperationException) { }
                    }
                }
            }
            return result;
        }
    }
}
