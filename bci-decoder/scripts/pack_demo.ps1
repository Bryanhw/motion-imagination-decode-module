#requires -Version 5.1
<#
.SYNOPSIS
    Build a portable A8 demo bundle for running the decoder on another machine.

.DESCRIPTION
    Copies source, configs, model artifacts, mock data and requirements into a
    self-contained folder. The .venv is NOT copied (it is tied to the machine
    that created it). Instead, the bundle ships setup.ps1 which recreates the
    venv on the target machine.

    Everything the project uses is relative-path based, CPU only, no network
    service required (except pip during setup).

.PARAMETER OutDir
    Target folder. Defaults to <repo>\dist\A8_demo_bundle_<timestamp>.
    Never overwrites: if the folder exists the script stops.

.PARAMETER Zip
    Also produce a .zip next to the folder.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\pack_demo.ps1 -Zip
#>
param(
    [string]$OutDir = "",
    [switch]$Zip
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([string]::IsNullOrWhiteSpace($OutDir)) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmm"
    $OutDir = Join-Path (Join-Path $root "dist") "A8_demo_bundle_$stamp"
}

if (Test-Path -LiteralPath $OutDir) {
    throw "Target already exists: $OutDir  (choose another -OutDir or remove it manually)"
}

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

function Copy-Tree {
    param([string]$Name)
    $src = Join-Path $root $Name
    if (-not (Test-Path -LiteralPath $src)) { Write-Host "skip (missing): $Name"; return }
    $dst = Join-Path $OutDir $Name
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    Get-ChildItem -LiteralPath $src -Recurse -File |
        Where-Object { $_.FullName -notmatch '__pycache__' -and $_.Extension -ne '.pyc' } |
        ForEach-Object {
            $rel = $_.FullName.Substring($src.Length).TrimStart('\')
            $target = Join-Path $dst $rel
            $dir = Split-Path $target -Parent
            if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            Copy-Item -LiteralPath $_.FullName -Destination $target -Force
        }
    Write-Host "copied: $Name"
}

"Packaging from: $root"
"Packaging to  : $OutDir"
""

foreach ($d in @("bci_decoder", "game", "configs", "data", "scripts", "tests")) {
    Copy-Tree $d
}

# artifacts: models + configs only (skip logs, soak output, jsonl dumps)
$artSrc = Join-Path $root "artifacts"
$artDst = Join-Path $OutDir "artifacts"
New-Item -ItemType Directory -Path $artDst -Force | Out-Null
Get-ChildItem -LiteralPath $artSrc -File |
    Where-Object { $_.Extension -in @(".joblib", ".yaml", ".yml", ".json") } |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $artDst $_.Name) -Force }
Write-Host "copied: artifacts (models only)"

Copy-Item -LiteralPath (Join-Path $root "requirements.txt") -Destination (Join-Path $OutDir "requirements.txt") -Force
Write-Host "copied: requirements.txt"

# ---- setup.ps1 (runs on the target machine, ASCII only) ----
$setup = @'
#requires -Version 5.1
# One-time environment setup for the A8 demo bundle (run on the target PC).
# Usage: powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "[1/4] Checking Python..."
$py = $null
foreach ($cand in @("python", "py -3.14", "py -3.13", "py -3.12", "py -3.11", "py -3.10")) {
    $parts = $cand.Split(" ")
    $exe = $parts[0]
    $pre = @()
    if ($parts.Count -gt 1) { $pre = $parts[1..($parts.Count-1)] }
    try {
        $out = & $exe @pre -c "import sys; print(sys.version_info[0], sys.version_info[1])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $major, $minor = $out.Trim().Split(" ")
            if ([int]$major -eq 3 -and [int]$minor -ge 10) {
                $py = @($exe) + $pre
                Write-Host "      found: $cand -> Python $major.$minor"
                break
            }
        }
    } catch { }
}
if (-not $py) {
    throw "Python 3.10+ not found. Install Python 3.12/3.13 (64-bit), tick 'Add to PATH', then re-run."
}

Write-Host "[2/4] Creating .venv ..."
& $py[0] @($py[1..($py.Count-1)]) -m venv .venv
$vpy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $vpy)) { throw "venv creation failed" }

Write-Host "[3/4] Installing dependencies (needs network or a local wheel cache) ..."
& $vpy -m pip install --upgrade pip --quiet
& $vpy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed. For offline site: run 'pip download -r requirements.txt -d wheels' on a networked PC, then 'pip install --no-index --find-links wheels -r requirements.txt'." }

Write-Host "[4/4] Self-check ..."
& $vpy -c "import pygame, bci_decoder, game.platformer; print('imports ok')"
if ($LASTEXITCODE -ne 0) { throw "import check failed" }
$models = @("artifacts\demo_csp.joblib", "artifacts\demo_lda.joblib", "artifacts\ood.joblib")
foreach ($m in $models) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $m))) { throw "missing model: $m" }
}
Write-Host ""
Write-Host "READY. Start order (important):"
Write-Host "  1) decoder : .venv\Scripts\python.exe -m bci_decoder.cli run --config configs\demo_game_ws.yaml"
Write-Host "  2) wait ~15s until it prints idle"
Write-Host "  3) game    : .venv\Scripts\python.exe -m game.platformer.main --mode ws --ws-url ws://127.0.0.1:8765 --timeout 1.5"
Write-Host "Keyboard-only fallback: .venv\Scripts\python.exe -m game.platformer.main --mode keyboard"
'@
[System.IO.File]::WriteAllText((Join-Path $OutDir "setup.ps1"), $setup, [System.Text.UTF8Encoding]::new($false))

# ---- RUN_A8.md (Chinese, UTF-8 with BOM for Notepad compatibility) ----
$readme = @'
# A8 现场演示包（可拷到任意 Windows 电脑运行）

## 这个包是什么

`bci-decoder` 的**自包含副本**：源码 + 配置 + 模型 + mock 数据 + 游戏端。
不含 `.venv`（虚拟环境与本机路径绑定，搬到别的电脑会失效），由 `setup.ps1` 在目标机重建。

**依赖情况**：纯 CPU（numpy/scipy/scikit-learn），不需要 GPU、不需要联网服务、不需要企业设备。
只需 Python 3.10+ 和一次 pip 安装。

## 在目标电脑上的步骤（首次约 5 分钟）

```powershell
# 1) 解压后进入目录，装环境
powershell -ExecutionPolicy Bypass -File setup.ps1

# 2) 启动顺序不能反（重要）
.venv\Scripts\python.exe -m bci_decoder.cli run --config configs\demo_game_ws.yaml
#   ↑ 等它打印 idle（约 13-15 秒），再开下一步

.venv\Scripts\python.exe -m game.platformer.main --mode ws --ws-url ws://127.0.0.1:8765 --timeout 1.5
```

键盘版（不依赖解码器，用于开场演示）：

```powershell
.venv\Scripts\python.exe -m game.platformer.main --mode keyboard
```

## 目标机要求

| 项 | 要求 | 说明 |
|---|---|---|
| 系统 | Windows 10/11 64 位 | 与源机一致最稳 |
| Python | 3.10+（推荐 3.12/3.13） | 装时勾选 “Add python.exe to PATH” |
| 网络 | 首次 pip 需要 | 现场没网就提前在有网电脑上 `pip download -r requirements.txt -d wheels`，把 wheels 目录一起拷来 |
| 端口 | 8765 空闲 | 被占用会启动失败，`netstat -ano \| findstr 8765` 可查 |
| 防火墙 | 首次弹窗选“允许” | 只监听 127.0.0.1，一般不会弹 |

## 已知差异（在新机器上要注意）

1. **冷启动更慢**：源机 13 秒到端口就绪，机械盘/杀毒软件在管的新机器可能 20 秒以上。
   所以启动顺序必须“先解码器、后游戏”，且游戏端 `--timeout 1.5` 会自动重连，不要手动重启。
2. **首次运行会编译 pyc**：第一次启动明显更慢，第二次恢复正常。**彩排时至少要跑两遍**。
3. **屏幕分辨率/缩放不同**：pygame 窗口尺寸按像素算，换机器前先在目标机上看一眼窗口是否完整。
4. **中文路径**：包放在纯英文路径下最稳（如 `D:\A8_demo`），避免 `文档\新建文件夹` 这类路径。

## 自检清单（彩排时逐条打勾）

- [ ] `setup.ps1` 打印 `imports ok` 和 `READY`
- [ ] 解码器启动后 15 秒内打印第一条 `idle`
- [ ] `netstat -ano | findstr 8765` 显示 LISTENING
- [ ] 游戏 `--mode ws` 能连上，首帧 < 3 秒
- [ ] 键盘版能跑（不依赖解码器）
- [ ] 三类场景切换（键盘 → 解码 → 断线）各跑一次
- [ ] 关闭窗口后 `Get-Process python` 无残留
- [ ] **至少跑两遍**（第一遍要编译 pyc，明显更慢，把这份慢消耗在彩排里）
- [ ] 记录计时：冷启动 ____ s、首帧 ____ s（新机器比源机的 13 s 慢是正常的，写进环境快照）

## 回滚

源机环境保持可用不要动；U 盘带这份包。现场若目标机故障 → 直接换回源机，命令完全一致。
注意：换机演示时，环境快照要记**目标机**的 `hostname` 与 Python 版本。

## 出问题时

| 现象 | 处理 |
|---|---|
| `python` 不是内部命令 | 重装 Python 并勾选 Add to PATH，或改用 `py -3.12` |
| pip 装 pygame 失败 | 必须装 `pygame-ce`（已在 requirements 里），不要改装上游 `pygame` |
| 游戏显示未连接 | 先确认解码器已打印 idle；`netstat` 看 8765；关掉系统代理 |
| 端口被占 | `taskkill /PID <pid> /F`，或改 `configs\demo_game_ws.yaml` 的 `ws_port` 与游戏 `--ws-url` |
| 启动即崩 | 换回源机跑；把报错整段发回来 |

## 这个包和仓库的关系

内容来自 `D:\校企合作项目` 的当前提交。证据归档仍以源机 `docs/evidence/W9_1027/` 为准；
本包只用于**运行**，不用于产生新的验收证据（新的证据必须记录目标机环境，见 A8 手册 §6）。
'@
[System.IO.File]::WriteAllText((Join-Path $OutDir "RUN_A8.md"), $readme, [System.Text.UTF8Encoding]::new($true))

$total = (Get-ChildItem -LiteralPath $OutDir -Recurse -File | Measure-Object Length -Sum).Sum
""
"Bundle size: {0:N1} MB" -f ($total / 1MB)

if ($Zip) {
    $zipPath = "$OutDir.zip"
    if (Test-Path -LiteralPath $zipPath) { throw "Zip already exists: $zipPath" }
    Compress-Archive -LiteralPath $OutDir -DestinationPath $zipPath -CompressionLevel Optimal
    "Zip: $zipPath ({0:N1} MB)" -f ((Get-Item -LiteralPath $zipPath).Length / 1MB)
}

Write-Host ""
Write-Host "Done. Copy the folder to the target PC and run setup.ps1 there."
