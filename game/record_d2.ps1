param(
    [string]$PackageRoot = 'D:\CST AI\脑电运动想象\D2_S001_work\D2_S001',
    [string]$Python = 'D:\CST AI\脑电运动想象\motion-imagery-eeg\.venv\Scripts\python.exe'
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'd2_recording_main.py'
$target = Join-Path $PackageRoot 'game\platformer\main.py'
$original = Join-Path $PackageRoot 'game\platformer\main.original.py'
if (-not (Test-Path -LiteralPath $original)) { Copy-Item -LiteralPath $target -Destination $original }
Copy-Item -LiteralPath $source -Destination $target -Force
$log = Join-Path $PackageRoot 'artifacts\d2_s001\d2_decoder.log'
$err = Join-Path $PackageRoot 'artifacts\d2_s001\d2_decoder.err.log'
$video = Join-Path $PSScriptRoot 'd2_game_20261117.mp4'
$decoder = Start-Process -FilePath $Python -ArgumentList '-u','-m','bci_decoder.cli','run','--config','artifacts/d2_s001/replay.yaml' -WorkingDirectory $PackageRoot -RedirectStandardOutput $log -RedirectStandardError $err -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 2
    $env:SDL_VIDEODRIVER = 'dummy'
    Push-Location $PackageRoot
    try {
        & $Python -m game.platformer.main --mode ws --ws-url ws://127.0.0.1:18765 --record $video --decoder-log $log --duration 35
        if ($LASTEXITCODE -ne 0) { throw 'Game recording failed' }
    } finally { Pop-Location }
} finally {
    Stop-Process -Id $decoder.Id -Force -ErrorAction SilentlyContinue
}
Write-Host "Video: $video"
Write-Host "Decoder log: $log"
