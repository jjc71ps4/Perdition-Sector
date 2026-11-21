using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using System.Management.Automation;
using System.Management.Automation.Runspaces;
using System.Threading;

internal static class SetupBootstrap {
    [STAThread]
    private static int Main() {
        try {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string script = Path.Combine(root, "Setup.ps1");
            if (!File.Exists(script)) throw new FileNotFoundException("Extract the complete installer ZIP before starting setup.", script);
            var initial = InitialSessionState.CreateDefault();
            initial.ExecutionPolicy = Microsoft.PowerShell.ExecutionPolicy.Bypass;
            using (var runspace = RunspaceFactory.CreateRunspace(initial)) {
                runspace.ApartmentState = ApartmentState.STA;
                runspace.ThreadOptions = PSThreadOptions.ReuseThread;
                runspace.Open();
                using (var powershell = PowerShell.Create()) {
                    powershell.Runspace = runspace;
                    powershell.AddCommand(script).Invoke();
                    if (powershell.HadErrors) {
                        string message = powershell.Streams.Error.Count > 0 ? powershell.Streams.Error[0].ToString() : "Setup could not initialize.";
                        throw new InvalidOperationException(message);
                    }
                    return 0;
                }
            }
        } catch (Exception error) {
            MessageBox.Show(error.Message, "Perdition Sector Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
