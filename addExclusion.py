# win_defender_exclusions.py
import ctypes
import sys
import subprocess
import base64

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def run_powershell_command(ps_command: str) -> subprocess.CompletedProcess:
    """
    Run a PowerShell command using -EncodedCommand to avoid quoting problems.
    Returns CompletedProcess.
    """
    # Encode as UTF-16-LE then base64 per PowerShell's -EncodedCommand spec
    encoded = base64.b64encode(ps_command.encode('utf-16-le')).decode('ascii')
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
    # Use check=False so we can return stdout/stderr and status rather than throwing
    return subprocess.run(cmd, capture_output=True, text=True)

def add_exclusion_path(path: str):
    ps = fr"Add-MpPreference -ExclusionPath '{path}'"
    return run_powershell_command(ps)

def add_exclusion_extension(ext: str):
    # ext should be like "exe" or "dll" (no leading dot)
    ps = fr"Add-MpPreference -ExclusionExtension '{ext}'"
    return run_powershell_command(ps)

def add_exclusion_process(process_name: str):
    # e.g. "mimikatz.exe" or "C:\Program Files\app\app.exe"
    ps = fr"Add-MpPreference -ExclusionProcess '{process_name}'"
    return run_powershell_command(ps)

def list_exclusions():
    ps = "Get-MpPreference | Select-Object ExclusionPath,ExclusionProcess,ExclusionExtension | ConvertTo-Json -Depth 4"
    return run_powershell_command(ps)

def remove_exclusion_path(path: str):
    ps = fr"Remove-MpPreference -ExclusionPath '{path}'"
    return run_powershell_command(ps)

def ensure_admin_and_run(func, *args, **kwargs):
    if not is_admin():
        # Relaunch with elevation (opens UAC), pass the same script + args to python
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        # ShellExecuteW 'runas' to elevate and run the same interpreter + script
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join([sys.argv[0], params]), None, 1)
        sys.exit(0)
    else:
        return func(*args, **kwargs)

if __name__ == "__main__":
    # Example usage: add an exclusion for a single file path
    path = r"C:\Users\Ryder7223\Documents\scripts\testing\Over WiFi\File Share\uploads\log.exe"
    
    ensure_admin_and_run(add_exclusion_path, path)

    # Show the result
    res = list_exclusions()
    print("Return code:", res.returncode)
    print("stdout:\n", res.stdout)
    print("stderr:\n", res.stderr)