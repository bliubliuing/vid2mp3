# vid2mp3 — 视频批量转 MP3 工具

把一个目录下的 `.mp4` 视频批量提取音频，转换为 `.mp3`。适合给点读笔、MP3 播放器等设备准备音频材料。

## 功能

- 批量转换：一次处理整个视频目录
- 增量转换：输出目录已存在的 MP3 自动跳过，不重复转换
- 限量转换：可设置本次最多转换几个（0 = 不限）
- 后台转换：GUI 转换不卡界面，可随时取消
- 实时日志：显示 OK / SKIP / FAIL 状态

## 下载（Windows）

前往 [Releases](https://github.com/bliubliuing/vid2mp3/releases) 下载最新版本：

- `vid2mp3.exe` — 主程序
- `ffmpeg.exe` — 转码引擎

两个文件放在**同一个文件夹**，双击 exe 即可使用，无需安装 Python。

> 如果启动时提示找不到 ffmpeg，确认 `ffmpeg.exe` 和主程序在同一目录，或已加入系统 PATH。

## 使用方法（GUI）

1. 选择 **视频目录**（存放 mp4 的文件夹）
2. 选择 **输出目录**（MP3 保存位置）
3. 设置本次最多转换数量（0 = 全部）
4. 点击 **开始转换**，日志区实时显示进度

## 使用方法（命令行 / Linux / macOS）

需要系统已安装 `ffmpeg`。

```bash
# 转换全部（默认 ./videos -> ./mp3）
./convert.sh

# 只转 3 个
./convert.sh 3

# 指定目录
./convert.sh 0 /path/to/videos /path/to/mp3
```

Linux 图形界面：`python3 convert_gui_linux.py`（需要 GTK4 + libadwaita）。

## 从源码打包 Windows exe

在 Windows 上：

```bash
pip install PySide6 pyinstaller
pyinstaller --onefile --windowed --name vid2mp3 convert_gui_windows.py
```

或在 GitHub Actions 页面手动触发 `Build Windows EXE` 工作流；推送 `v*` 标签会自动构建并发布到 Releases。

## 项目结构

```
convert.sh                 命令行批量转换脚本
convert_gui_windows.py     Windows GUI（PySide6）
convert_gui_linux.py       Linux GUI（GTK4 + libadwaita）
.github/workflows/         云端打包发布流水线
```
