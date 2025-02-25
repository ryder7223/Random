# Ensure the script runs as Admin
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Please run this script as Administrator!" -ForegroundColor Red
    exit
}

# Define registry path
$registryPath = "HKLM:\SYSTEM\Setup\LabConfig"

# Check if the key exists, if not, create it
if (-not (Test-Path $registryPath)) {
    New-Item -Path "HKLM:\SYSTEM\Setup" -Name "LabConfig" -Force
}

# Add registry values
New-ItemProperty -Path $registryPath -Name "BypassTPMCheck" -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $registryPath -Name "BypassSecureBootCheck" -Value 1 -PropertyType DWORD -Force
New-ItemProperty -Path $registryPath -Name "BypassRAMCheck" -Value 1 -PropertyType DWORD -Force

Write-Host "Registry keys successfully added!" -ForegroundColor Green
