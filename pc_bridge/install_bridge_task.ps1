# install_bridge_task.ps1 - Register bridge service as auto-start (at logon)
# Usage: powershell -ExecutionPolicy Bypass -File install_bridge_task.ps1
# Uninstall: schtasks /Delete /TN "DSH-Pi-Bridge" /F

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Prefer pythonw.exe (no console window); fall back to python.exe
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Write-Error "python not found. Install Python 3.9+ first." }
$pyw = Join-Path (Split-Path $py) "pythonw.exe"
$exe = if (Test-Path $pyw) { $pyw } else { $py }

$script = Join-Path $dir "bridge.py"
if (-not (Test-Path $script)) { Write-Error "bridge.py not found at $script" }

$action = New-ScheduledTaskAction -Execute $exe -Argument "`"$script`"" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName "DSH-Pi-Bridge" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Registered auto-start task: DSH-Pi-Bridge"
Write-Host "Start it now with:"
Write-Host "  Start-ScheduledTask -TaskName DSH-Pi-Bridge"
Write-Host "Verify: curl http://127.0.0.1:8123/health"
Write-Host "Log file: $dir\bridge.log"
