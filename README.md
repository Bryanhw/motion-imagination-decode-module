# 运动想象脑电数据准备与核验

这是四名大一学生学习左右手运动想象 EEG 的独立入门项目。当前阶段只准备和核验公开数据，**尚未训练 CSP＋LDA 模型**。

## 项目结构

```text
motion-imagery-eeg/
├─ data/                 本地 EDF 数据（Git 忽略，不提交）
├─ check_data.py        读取一份 EDF 并打印基础信息
├─ scripts/             保留后续数据获取与扩展脚本
├─ .gitignore            忽略数据、虚拟环境、缓存和模型文件
├─ requirements.txt      Python 依赖
└─ README.md             本说明
```

## 数据来源和任务含义

本项目使用 PhysioNet **EEG Motor Movement/Imagery Dataset，版本 1.0.0**，来源：[官方数据集页面](https://physionet.org/content/eegmmidb/1.0.0/)，文件直链位于 `https://physionet.org/files/eegmmidb/1.0.0/S001/`。

每名受试者的第 4、8、12 次运行均为想象左拳或右拳运动。S001R04、S001R08、S001R12 因此都包含左右手（拳）运动想象任务。EDF 注释中：

- `T0`：休息阶段开始；
- `T1`：单侧拳任务中的左拳运动/想象开始；
- `T2`：单侧拳任务中的右拳运动/想象开始。

本数据集每份记录含 64 个 EEG 通道，采样率为 160 Hz。请引用数据集及其原始论文：

> Schalk, G. (2009). *EEG Motor Movement/Imagery Dataset* (version 1.0.0). PhysioNet. https://doi.org/10.13026/C28G6P
>
> Schalk, G., McFarland, D. J., Hinterberger, T., Birbaumer, N., & Wolpaw, J. R. (2004). BCI2000: A General-Purpose Brain-Computer Interface (BCI) System. *IEEE Transactions on Biomedical Engineering*, 51(6), 1034–1043. https://doi.org/10.1109/TBME.2004.827072

数据许可为 Open Data Commons Attribution License v1.0。使用或分享数据时请遵守许可并保留归属信息。

## Windows 安装和运行

### 1. 安装 Python

安装 Python 3.10 或更新版本，建议从 [python.org](https://www.python.org/downloads/windows/) 下载。安装界面勾选 **Add python.exe to PATH**。打开新的 PowerShell，检查：

```powershell
py --version
```

如果 `py` 不可用，请重新安装 Python 并勾选加入 PATH；也可以在下方命令中把 `py` 换成 `python`。

### 2. 进入项目并创建虚拟环境

在 PowerShell 中运行（若项目放在别处，请调整路径）：

```powershell
cd "D:\CST AI\脑电运动想象\motion-imagery-eeg"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

激活成功后，命令行前面会出现 `(.venv)`。如果 PowerShell 阻止激活脚本，可在当前窗口运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

这只对当前 PowerShell 窗口生效。

### 3. 安装依赖

```powershell
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

### 4. 获取三份 EDF

脚本会尝试从 PhysioNet 下载指定的三个文件到 `data/`，不会遍历或下载整个数据集。它会对中断下载进行有限次数重试，并检查文件大小；发现先前留下的异常小文件时会重新获取：

```powershell
py scripts\download_data.py
```

如果网络不通或自动下载失败，可用浏览器逐个下载以下链接，并将文件保存到项目的 `data` 文件夹（文件名保持不变）：

- [S001R04.edf](https://physionet.org/files/eegmmidb/1.0.0/S001/S001R04.edf)
- [S001R08.edf](https://physionet.org/files/eegmmidb/1.0.0/S001/S001R08.edf)
- [S001R12.edf](https://physionet.org/files/eegmmidb/1.0.0/S001/S001R12.edf)

### 5. 运行核验脚本

```powershell
py scripts\check_data.py
```

脚本逐个报告文件是否存在且能被 MNE 读取、采样率、通道数和名称/顺序、时长，以及 `T0`、`T1`、`T2` 注释数量；最后比较三份记录的采样率和通道顺序。任何文件缺失、读取失败、左右手标记缺失或跨文件不一致都会给出错误提示并以非零状态结束。

### 6. 看懂输出

正常情况下，三份文件应能读取，采样率为 160 Hz，含 64 个 EEG 通道；每份记录中 `T1` 和 `T2` 都应大于零，三份记录的采样率和通道顺序应一致。`T0` 是休息标记。具体数量以脚本在本机真实读到的数据为准。

核验通过只表示数据文件和基本标记可用，**不代表已经完成信号处理、分类或模型训练**。

## 常见错误

- **找不到 `py` 或 `python`**：安装 Python 3 并勾选加入 PATH，重新打开 PowerShell。
- **无法激活 `.venv`**：按上文在当前窗口设置 `ExecutionPolicy Bypass`，再激活。
- **`No module named mne`**：确认虚拟环境已激活，再运行 `py -m pip install -r requirements.txt`。
- **EDF 缺失**：检查文件是否在项目的 `data` 文件夹，名字是否准确；自动下载不可用时按上方链接手动下载。
- **EDF 无法读取或标记缺失**：文件可能下载不完整或错误地保存了网页；重新下载对应 EDF 后再检查。
- **下载超时/证书错误**：检查网络连接、系统日期和校园网访问限制，之后重试或使用浏览器手动下载。

## 数据与 Git

`data/` 已加入 `.gitignore`。EDF 文件体积较大，只保留在各自电脑的本地数据目录，不要提交到 Git。虚拟环境、Python 缓存和常见模型文件也会被忽略。


## 入门练习：读取第一份脑电记录

PhysioNet 第 4 次运行（S001R04）是左右拳运动想象任务。EDF 注释中 `T0` 表示休息开始，`T1` 表示左拳想象开始，`T2` 表示右拳想象开始。

在项目根目录启用虚拟环境后，运行：

```powershell
python check_data.py
```

程序会用 MNE 读取 `data/S001R04.edf`，打印文件大小、采样率、EEG 通道数和前几个名称、记录时长，以及 T0/T1/T2 数量。文件缺失或读取失败时会显示错误提示。此练习只读数据和查看标记，不做滤波、事件定位、CSP/LDA 或游戏开发。


## 下一步：定位事件并截取片段

运行：

```powershell
.\.venv\Scripts\python.exe scripts\inspect_events.py
```

脚本用 MNE 的 `events_from_annotations` 把 EDF 注释转成事件采样点，只取 T1/T2，并在提示后第 1 至第 3 秒切片。这个 2 秒窗口只是**起步参数**，尚未比较其他窗口，也不是最佳设置。程序打印事件时间、左右手次数、X/y 形状和边界丢弃数，并把连续波形示意图保存到 `data/continuous_vs_epochs.png`（图和 EDF 都被 Git 忽略）。MNE 在 160 Hz 下每秒有 160 个采样点；脚本从 MNE 两端均含的 321 点中去掉最后一点，因此 2 秒窗口有 320 个样本点。本阶段不训练分类器。

## 预处理与按完整记录划分

在项目根目录的 PowerShell 运行：

```powershell
.\.venv\Scripts\python.exe scripts\preprocess.py
```

`scripts/preprocess.py` 的 `prepare_data()` 返回 `X_train, y_train, X_test, y_test, metadata`，可供下一阶段读取。R04、R08 的全部片段进入训练集；R12 的全部片段进入测试集。`y` 中 `0` 是 T1（左手想象），`1` 是 T2（右手想象）。这是**同一名受试者的初步划分**，不能据此声称方法能泛化到其他人。

连续脑电是一整段按时间排列的电压数据。因果带通滤波依时间顺序处理数据，保留起步设置的 8–30 Hz 成分；每份记录都从零状态开始，分块处理时将滤波状态传到下一块。8–30 Hz、4 阶 Butterworth 和提示后 `[1, 3)` 秒均为**起步参数**，未用 R12 标签挑选，也不是已验证的最优选择。脚本先滤整份连续记录，再按 T1/T2 提示位置截成固定长度的片段。

`X` 是“片段 × EEG 通道 × 时间点”的数字数组；`y` 是与各片段按顺序对应的左/右标签。训练集用于未来拟合模型，测试集留给未来评估；此阶段没有拟合模型。脚本会报告缺失值、极端幅度与平直通道，记录被排除的数量和原因，并核对三份记录的采样率、EEG 通道名称与顺序。图 `data/filter_comparison.png` 用同一 C3 电极的同一时间范围展示滤波前后电压，纵轴单位为微伏；图片被 Git 忽略。波形变化本身不代表分类性能提高。

脚本还用一小段连续信号比较一次性 `sosfilt` 与传递状态的分块 `sosfilt`，两者使用相同的零初始状态；这是为以后在线回放的数值一致性做准备。此阶段不训练 CSP 或 LDA，也不向游戏发送指令。
