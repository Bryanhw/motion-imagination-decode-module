<#
.SYNOPSIS
    A10 soak runner: launch the decoder, sample RSS / private bytes / handles / CPU,
    write a CSV plus a PASS-FAIL summary.

.DESCRIPTION
    Runs in bci-decoder/ (script resolves the repo root from its own path).
    Defaults match the A10 acceptance item: 60 minutes, sample every 60 s.

    Sampling resolves the REAL decoder process through Win32_Process CommandLine
    (Start-Process on .venv\Scripts\python.exe returns a small shim PID).

    Decoder console log is human-readable:
        [    1.996s] idle   conf=1.00  probs=[1.00 0.00]  compute=7.2ms  win=2.0s state=running

    PASS criteria
      1. peak RSS                          <= 500 MB
      2. drift (mean of last window - mean of first window) <= 50 MB
      3. decision rate                     1.8 .. 2.2 messages/s  (0.5 s step)
      4. decoder stderr log                empty (no traceback)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\soak_rss.ps1 -Minutes 3 -IntervalSeconds 10

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\soak_rss.ps1 -Minutes 60 -IntervalSeconds 60
#>
param(
    [int]$Minutes = 60,
    [int]$IntervalSeconds = 60,
    [string]$Config = 'configs\demo_online.yaml',
    [string]$OutDir = 'artifacts\soak'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $root

$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) { throw "python not found: $py" }
if (-not (Test-Path -LiteralPath (Join-Path $root $Config))) { throw "config not found: $Config" }

# realtime: true  -> one decision per 0.5 s of WALL clock (paced source)
# realtime: false -> source runs as fast as possible, wall-clock rate is meaningless
$cfgText = Get-Content -LiteralPath (Join-Path $root $Config) -Encoding UTF8 -Raw
$isRealtime = ($cfgText -match '(?m)^\s*realtime:\s*true')

$outAbs = Join-Path $root $OutDir
New-Item -ItemType Directory -Path $outAbs -Force | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$csv = Join-Path $outAbs "rss_$stamp.csv"
$log = Join-Path $outAbs "decoder_$stamp.log"
$err = Join-Path $outAbs "decoder_$stamp.err.log"
$sum = Join-Path $outAbs "summary_$stamp.txt"

function Get-DecoderProcess {
    param([int]$FallbackId)
    $cim = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like '*bci_decoder.cli*' }
    $procs = foreach ($c in $cim) { Get-Process -Id $c.ProcessId -ErrorAction SilentlyContinue }
    if ($procs) { return ($procs | Sort-Object WorkingSet64 -Descending | Select-Object -First 1) }
    return (Get-Process -Id $FallbackId -ErrorAction SilentlyContinue)
}

Write-Host "[soak] config   : $Config"
Write-Host "[soak] duration : $Minutes min, sample every $IntervalSeconds s"
Write-Host "[soak] out      : $outAbs"

$launcher = Start-Process -FilePath $py `
        -ArgumentList '-u','-m','bci_decoder.cli','run','--config',$Config `
        -WorkingDirectory $root `
        -RedirectStandardOutput $log -RedirectStandardError $err `
        -PassThru -WindowStyle Hidden

$t0 = Get-Date
$deadline = $t0.AddMinutes($Minutes)
$rows = New-Object System.Collections.ArrayList
$earlyExit = $false
$decoderPid = 0

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $IntervalSeconds
    $proc = Get-DecoderProcess -FallbackId $launcher.Id
    if (-not $proc) { Write-Host '[soak] decoder process not found'; $earlyExit = $true; break }
    $decoderPid = $proc.Id
    $elapsed = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
    [void]$rows.Add([pscustomobject]@{
            elapsed_s  = $elapsed
            pid        = $proc.Id
            rss_mb     = [math]::Round($proc.WorkingSet64 / 1MB, 1)
            private_mb = [math]::Round($proc.PrivateMemorySize64 / 1MB, 1)
            handles    = $proc.HandleCount
            threads    = $proc.Threads.Count
            cpu_s      = [math]::Round($proc.TotalProcessorTime.TotalSeconds, 1)
        })
    Write-Host ("[soak] {0,6}s  rss={1,7} MB  priv={2,7} MB  handles={3,5}" -f $elapsed, $rows[-1].rss_mb, $rows[-1].private_mb, $rows[-1].handles)
}

if ($decoderPid -gt 0) { Stop-Process -Id $decoderPid -Force -ErrorAction SilentlyContinue }
Stop-Process -Id $launcher.Id -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$rows | Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8

# ---- parse the human-readable decoder log ----
$msgCount = 0
$rate = 0.0
$spanS = 0.0
$labels = [ordered]@{}
$tMin = [double]::MaxValue
$tMax = [double]::MinValue
$haveSpan = $false

if (Test-Path -LiteralPath $log) {
    $rx = [regex]'^\s*\[\s*([0-9]+(?:\.[0-9]+)?)s\]\s*([A-Za-z_]+)'
    foreach ($line in [System.IO.File]::ReadLines($log)) {
        $m = $rx.Match($line)
        if (-not $m.Success) { continue }
        $msgCount++
        $t = [double]$m.Groups[1].Value
        if ($t -lt $tMin) { $tMin = $t }
        if ($t -gt $tMax) { $tMax = $t }
        $k = $m.Groups[2].Value
        if ($labels.Contains($k)) { $labels[$k] = $labels[$k] + 1 } else { $labels[$k] = 1 }
    }
    if ($tMax -gt $tMin) { $spanS = [math]::Round($tMax - $tMin, 1); $rate = [math]::Round($msgCount / $spanS, 2); $haveSpan = $true }
}

# ---- memory stats ----
$peak = 0.0; $drift = 0.0; $slope = 0.0; $handlesDelta = 0
if ($rows.Count -ge 2) {
    $peak = ($rows | Measure-Object -Property rss_mb -Maximum).Maximum
    $totalS = $rows[-1].elapsed_s
    $winS = [math]::Min(600, $totalS / 2)
    $head = $rows | Where-Object { $_.elapsed_s -le $winS }
    $tail = $rows | Where-Object { $_.elapsed_s -ge ($totalS - $winS) }
    $headAvg = ($head | Measure-Object -Property rss_mb -Average).Average
    $tailAvg = ($tail | Measure-Object -Property rss_mb -Average).Average
    $drift = [math]::Round($tailAvg - $headAvg, 1)
    $hours = [math]::Max($totalS / 3600.0, 0.0001)
    $slope = [math]::Round(($tailAvg - $headAvg) / $hours, 1)
    $handlesDelta = $rows[-1].handles - $rows[0].handles
}

$errLen = 0
if (Test-Path -LiteralPath $err) { $errLen = (Get-Item -LiteralPath $err).Length }

$wallS = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
$wallRate = if ($wallS -gt 0) { [math]::Round($msgCount / $wallS, 2) } else { 0.0 }

$c1 = ($peak -le 500)
$c2 = ($drift -le 50)
$c3 = if ($isRealtime) { ($wallRate -ge 1.8 -and $wallRate -le 2.2) } else { $true }
$c4 = ($errLen -eq 0)
$pass = $c1 -and $c2 -and $c3 -and $c4 -and (-not $earlyExit)

$hist = ($labels.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ' '

$report = @()
$report += "A10 soak summary  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$report += "config            : $Config"
$report += "duration_min      : $Minutes"
$report += "samples           : $($rows.Count)"
$report += "decoder_pid       : $decoderPid"
$report += "early_exit        : $earlyExit"
$report += "messages          : $msgCount"
$report += "log_span_s        : $spanS"
$report += "realtime_source   : $isRealtime"
$report += "wall_clock_s      : $wallS"
$report += "wall_rate         : $wallRate /s  (paced source only, target 1.8-2.2)"
$report += "decision_rate     : $rate /s   (per DATA clock, always 2.0 by design)"
$report += "label_hist        : $hist"
$report += "rss_peak_mb       : $peak   (<= 500)"
$report += "rss_drift_mb      : $drift  (tail - head; upper bound 50, negative = GC reclaim is OK)"
$report += "rss_slope_mb_h    : $slope"
$report += "handles_delta     : $handlesDelta"
$report += "stderr_bytes      : $errLen  (must be 0)"
$report += "checks            : peak=$c1 drift=$c2 rate=$c3 stderr=$c4"
$report += "RESULT            : $(if ($pass) { 'PASS' } else { 'FAIL' })"
$report += "files             : $csv | $log | $err"

$report | Set-Content -LiteralPath $sum -Encoding UTF8
$report | ForEach-Object { Write-Host $_ }

if ($pass) { exit 0 } else { exit 1 }
