# -*- coding: utf-8 -*-
# OpenBMI (moabb Lee2019_MI) 分片并发下载器 v3（并发拉满带宽 + 分片级校验轮次 + 重试）
# 用法: powershell -ExecutionPolicy Bypass -File .tools/openbmi_download.ps1
# 参数: -Subject 1 -Sessions '1,2' -BaseDir 'D:/校企合作项目/.deepworks/mne_data'
# 原理: wasabi S3 单连接限速~20KB/s, 并发 Chunks 路 Range 拉到~600KB/s;
#       每片独立 curl 自带 --retry-all-errors 自动重连; 主脚本每轮校验各片字节数,
#       不满足则整轮重取故障片; 全部就位后按偏移升序合并, 校验总量等于 Content-Length.
param(
    [int]$Subject = 1,
    [string]$Sessions = '1,2',
    [string]$BaseDir = 'D:/校企合作项目/.deepworks/mne_data',
    [int]$Chunks = 32,
    [int]$MaxRounds = 6
)

$ErrorActionPreference = 'Stop'
$urlRoot = 'https://s3.ap-northeast-1.wasabisys.com/gigadb-datasets/live/pub/10.5524/100001_101000/100542'
$root = Join-Path $BaseDir 'MNE-lee2019-mi-data/gigadb-datasets/live/pub/10.5524/100001_101000/100542'

function Get-RemoteSize($url) {
    $h = & curl.exe -s -I $url
    foreach ($line in $h) {
        if ($line -match '^Content-Length:\s*(\d+)') { return [long]$Matches[1] }
    }
    throw "cannot read Content-Length for $url"
}

function Get-FileSize($p) { if (Test-Path -LiteralPath $p) { return (Get-Item -LiteralPath $p).Length } else { return 0L } }

# 内容抽查: MATLAB v5 文件头必须包含 "MATLAB 5.0 MAT-file". 仅字节数相等但内容损坏(如合并顺序错误)
# 会被此处拦下并重下, 避免把坏文件误判为 "already complete".
function Test-MatHeader($p) {
    if (-not (Test-Path -LiteralPath $p)) { return $false }
    try {
        $fs = [System.IO.File]::OpenRead($p)
        try {
            $buf = New-Object byte[] 128
            $n = $fs.Read($buf, 0, 128)
            $txt = [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
            return $txt.Contains('MATLAB 5.0 MAT-file')
        } finally { $fs.Dispose() }
    } catch { return $false }
}

foreach ($s_ in ($Sessions -split ',')) {
    $s = [int]$s_
    $dir = Join-Path $root ("session$s/s$Subject")
    $file = Join-Path $dir ("sess{0:00}_subj{1:00}_EEG_MI.mat" -f $s, $Subject)
    $url = "$urlRoot/session$s/s$Subject/sess{0:00}_subj{1:00}_EEG_MI.mat" -f $s, $Subject
    New-Item -ItemType Directory -Path $dir -Force | Out-Null

    $total = Get-RemoteSize $url
    Write-Output ("[{0:HH:mm:ss}] session${s} subj${Subject}: want=$total chunks=$Chunks" -f (Get-Date))

    # 每次重新全量下载; 仅当字节数相等且内容抽查通过(合法 MATLAB v5)才跳过
    if ((Get-FileSize $file) -eq $total -and (Test-MatHeader $file)) { Write-Output ("[{0:HH:mm:ss}]   already complete + header OK, skip" -f (Get-Date)); continue }
    if (Test-Path -LiteralPath $file) {
        Write-Output ("[{0:HH:mm:ss}]   existing file size={1} headerOk={2}, remove & redownload" -f (Get-Date), (Get-FileSize $file), (Test-MatHeader $file))
        Remove-Item -LiteralPath $file -Force
    }

    $scratch = Join-Path (Resolve-Path $BaseDir) ('_openbmi_tmp_s{0}_subj{1:00}' -f $s, $Subject)
    if (Test-Path -LiteralPath $scratch) { Remove-Item -LiteralPath $scratch -Recurse -Force }
    New-Item -ItemType Directory -Path $scratch | Out-Null

    $range = [Math]::Ceiling($total / $Chunks)
    $list = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt $Chunks; $i++) {
        $from = $i * $range
        $to = [Math]::Min($from + $range - 1, $total - 1)
        if ($from -ge $total) { break }
        [void]$list.Add(@{ from = $from; to = $to; part = (Join-Path $scratch ("p{0:D3}.bin" -f $i)); expect = ($to - $from + 1) })
    }

    # 并发下载直到全部分片字节数匹配
    for ($round = 1; $round -le $MaxRounds; $round++) {
        $todo = $list | Where-Object { (Get-FileSize $_.part) -ne $_.expect }
        if (-not $todo) { break }
        Write-Output ("[{0:HH:mm:ss}]   round {1}: fetching {2}/{3} chunks ..." -f (Get-Date), $round, ($todo | Measure-Object).Count, $list.Count)
        $procs = @()
        foreach ($item in $todo) {
            if (Test-Path -LiteralPath $item.part) { Remove-Item -LiteralPath $item.part -Force }
            $p = Start-Process -FilePath 'curl.exe' -ArgumentList @('-s','-L','-o',$item.part,'--fail','--max-time','1800','--retry','10','--retry-delay','2','--retry-all-errors','-r',("{0}-{1}" -f $item.from,$item.to),$url) -WindowStyle Hidden -PassThru
            $procs += $p
        }
        foreach ($p in $procs) { $null = $p.WaitForExit(1900000) ; if (-not $p.HasExited) { $p.Kill() } }
    }

    $bad = $list | Where-Object { (Get-FileSize $_.part) -ne $_.expect }
    if ($bad) {
        foreach ($b in $bad) { Write-Output ("      FAILED chunk {0}-{1} want={2} got={3}" -f $b.from, $b.to, $b.expect, (Get-FileSize $b.part)) }
        $msg = ("session{0}: {1} chunks still bad after {2} rounds" -f $s, ($bad | Measure-Object).Count, $MaxRounds)
        throw $msg
    }

    Write-Output ("[{0:HH:mm:ss}]   all {1} chunks OK, merging ..." -f (Get-Date), $list.Count)
    $fs = [System.IO.File]::Open($file, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $buf = New-Object byte[] 4194304
        # 注意: 请勿用 `Sort-Object from` (按属性名), 它对 Hashtable 排序顺序错误(已复现),
        # 必须用脚本块 `Sort-Object { $_.from }` 显式取属性值, 否则合并出的文件内容错乱.
        foreach ($item in ($list | Sort-Object { $_.from })) {
            $in = [System.IO.File]::OpenRead($item.part)
            try { while (($n = $in.Read($buf, 0, $buf.Length)) -gt 0) { $fs.Write($buf, 0, $n) } }
            finally { $in.Dispose() }
        }
    } finally { $fs.Dispose() }

    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
    $got = (Get-Item -LiteralPath $file).Length
    if ($got -eq $total -and (Test-MatHeader $file)) {
        Write-Output ("[{0:HH:mm:ss}]   COMPLETE session${s} subj${Subject}: {1} bytes OK + MATLAB header verified" -f (Get-Date), $got)
    } elseif ($got -ne $total) {
        throw ("MISMATCH session{0} subj{1}: got={2} want={3}" -f $s, $Subject, $got, $total)
    } else {
        throw ("BADHEADER session{0} subj{1}: {2} bytes but MATLAB header missing" -f $s, $Subject, $got)
    }
}
Write-Output ("[{0:HH:mm:ss}] openbmi_download DONE" -f (Get-Date))
