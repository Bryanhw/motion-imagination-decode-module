#requires -Version 5.1
<#
.SYNOPSIS
    Collect an environment snapshot for the A8 demo on the target machine.

.DESCRIPTION
    Writes one plain-text file next to this script:
      A8_<ENV>_<hostname>_<yyyyMMdd_HHmm>.txt

    Use it on the machine that will actually run the demo, so the archived
    evidence records the real hostname / Python / display / port state
    instead of the source machine's.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File collect_env.ps1
#>
param(
    [string]$OutDir = ""
)

if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = (Get-Location).Path }

$ErrorActionPreference = "Continue"
$lines = New-Object System.Collections.Generic.List[string]

function Add-Head([string]$t) {
    $lines.Add("")
    $lines.Add("==== $t ====")
}
function Try-Run([string]$block) {
    try { & ([scriptblock]::Create($block)) } catch { $lines.Add("  <error> $($_.Exception.Message)") }
}

$now = Get-Date
$envTagName = "演示环境"
Add-Head "SNAPSHOT"
$lines.Add("collected_at : $($now.ToString('yyyy-MM-dd HH:mm:ss'))")
$lines.Add("host : $env:COMPUTERNAME")
$lines.Add("user : $env:USERNAME")
$lines.Add("script_dir : $PSScriptRoot")

Add-Head "OS / HARDWARE"
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$lines.Add("os : $($os.Caption) $($os.Version) $($os.OSArchitecture)".Trim())
$lines.Add("cpu : $($cpu.Name)")
$lines.Add("cores : logical=$($cs.NumberOfLogicalProcessors) physical_cores=$($cpu.NumberOfCores)")
$lines.Add("ram_gb : {0:N1}" -f ($cs.TotalPhysicalMemory / 1GB))
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$((Get-Item -LiteralPath $PSScriptRoot).PSDrive.Name):'" -ErrorAction SilentlyContinue
if ($disk) { $lines.Add("disk_free_gb : {0:N1} of {1:N1}" -f ($disk.FreeSpace/1GB), ($disk.Size/1GB)) }

Add-Head "PYTHON"
$pyList = @()
foreach ($cand in @("python", "py -3")) {
    $parts = $cand.Split(" ")
    try {
        $v = & $parts[0] $parts[1..($parts.Count-1)] -c "import sys,platform; print(sys.version.split()[0], platform.architecture()[0], sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0) { $pyList += "$cand -> $v" }
    } catch { }
}
if ($pyList.Count -eq 0) { $lines.Add("python_on_path : NOT FOUND") } else { $pyList | ForEach-Object { $lines.Add($_) } }

$vpy = $null
$probe = $PSScriptRoot
for ($i = 0; $i -lt 3; $i++) {
    $cand = Join-Path $probe ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $cand) { $vpy = $cand; break }
    $probe = Split-Path $probe -Parent
}
if ($vpy) {
    $lines.Add("venv_python : $(& $vpy -c 'import sys; print(sys.version.split()[0])')  ($vpy)")
    Add-Head "PACKAGES"
    & $vpy -m pip list --format=freeze 2>$null | Where-Object {
        $_ -match '^(numpy|scipy|scikit-learn|PyYAML|joblib|websockets|pygame|pygame-ce|pytest)='
    } | ForEach-Object { $lines.Add($_) }
    Add-Head "IMPORT CHECK"
    & $vpy -c "import pygame, bci_decoder, game.platformer; print('imports ok')" 2>&1 | ForEach-Object { $lines.Add("  $_") }
} else {
    $lines.Add("venv_python : MISSING (run setup.ps1 first)")
}

Add-Head "DISPLAY"
try {
    Add-Type -AssemblyName System.Windows.Forms
    $s = [System.Windows.Forms.Screen]::PrimaryScreen
    $lines.Add("primary_screen : $($s.Bounds.Width)x$($s.Bounds.Height)")
    $lines.Add("screen_count : $([System.Windows.Forms.Screen]::AllScreens.Count)")
} catch { $lines.Add("display : <unavailable>") }
try {
    $applied = (Get-ItemProperty -Path 'HKCU:\Control Panel\Desktop\WindowMetrics' -Name AppliedDPI -ErrorAction Stop).AppliedDPI
    $lines.Add("dpi_scale : $([int]([math]::Round($applied/96*100)))%  (AppliedDPI=$applied)")
} catch {
    try {
        $lp = (Get-ItemProperty -Path 'HKCU:\Control Panel\Desktop' -Name LogPixels -ErrorAction Stop).LogPixels
        $lines.Add("dpi_scale : $([int]($lp/96*100))%  (LogPixels=$lp)")
    } catch { $lines.Add("dpi_scale : default 100% (not reported by registry)") }
}

Add-Head "PORT STATE"
foreach ($port in 8765, 8766) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $pids = ($conns | Select-Object -ExpandProperty OwningProcess -Unique) -join ','
        $lines.Add("port_$port : LISTENING pid=$pids")
    } else {
        $lines.Add("port_$port : free")
    }
}
$pyProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pyProcs) { $lines.Add("python_processes : " + (($pyProcs | ForEach-Object { "pid=$($_.Id) ws={0:N1}MB" -f ($_.WorkingSet64/1MB) }) -join '; ')) }
else { $lines.Add("python_processes : none") }

Add-Head "NETWORK / PROXY"
try {
    $ie = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    $lines.Add("proxy_enable : $($ie.ProxyEnable)")
    if ($ie.ProxyServer) { $lines.Add("proxy_server : $($ie.ProxyServer)") }
} catch { }
$lines.Add("net_127001 : " + (Test-NetConnection -ComputerName 127.0.0.1 -Port 8765 -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue))

Add-Head "FIREWALL"
try {
    Get-NetFirewallProfile | ForEach-Object { $lines.Add("profile $($_.Name) : enabled=$($_.Enabled)") }
} catch { $lines.Add("firewall : <unavailable>") }

Add-Head "TIME BUDGET (fill in during rehearsal)"
$lines.Add("cold_start_to_first_idle_s : ____")
$lines.Add("first_frame_s              : ____")
$lines.Add("second_run_idle_s          : ____   (should be close to cold_start after pyc compiled)")

$stamp = $now.ToString("yyyyMMdd_HHmm")
$out = Join-Path $OutDir ("A8_" + $envTagName + "_" + $env:COMPUTERNAME + "_" + $stamp + ".txt")
[System.IO.File]::WriteAllLines($out, $lines, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Snapshot written: $out"
Write-Host ("Lines: {0}" -f $lines.Count)
Write-Host "Copy this file into docs\evidence\W9_1027\ as the A8 environment record."
