$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = (Get-Command py).Source
    $Arguments = @("-3", "-m", "game.platformer.serve_web")
} else {
    $Arguments = @("-m", "game.platformer.serve_web")
}

$Address = "http://127.0.0.1:8766/"
$Handler = [System.Net.Http.HttpClientHandler]::new()
$Handler.UseProxy = $false
$Client = [System.Net.Http.HttpClient]::new($Handler)
$Client.Timeout = [TimeSpan]::FromSeconds(2)
$Listener = Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue
if (-not $Listener) {
    $StdoutLog = Join-Path $env:TEMP "mi-pixel-run-server.out.log"
    $StderrLog = Join-Path $env:TEMP "mi-pixel-run-server.err.log"
    Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden
}

$Healthy = $false
for ($Attempt = 0; $Attempt -lt 12; $Attempt++) {
    Start-Sleep -Milliseconds 300
    try {
        $Response = $Client.GetAsync($Address).GetAwaiter().GetResult()
        if ([int]$Response.StatusCode -eq 200) { $Healthy = $true; break }
    } catch {
        # Keep checking while a newly started local server finishes binding.
    }
}
$Client.Dispose()
$Handler.Dispose()
if (-not $Healthy) {
    throw "游戏网页服务未能正常响应 http://localhost:8766/。若端口已被其他程序占用，请先关闭该程序后重试。"
}

Start-Process "http://localhost:8766/"
Write-Host "游戏地址：http://localhost:8766/"
Write-Host "网页服务已通过 HTTP 健康检查。可以收藏此地址；本机重启后再次运行 game\platformer\start_game.ps1。"
