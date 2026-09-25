#!/usr/bin/env python3
"""视频转 MP3 工具 (Windows 版, PySide6)

把视频目录下的 mp4 提取音频转成 MP3，输出到音频目录。
已存在的 MP3 自动跳过；可限制本次转换数量；后台线程转换，可取消。

ffmpeg 查找顺序:
  1. 程序(exe)所在目录下的 ffmpeg.exe / ffmpeg
  2. 系统 PATH 中的 ffmpeg
找不到则弹窗提示。

PyInstaller 打包:
  pyinstaller --onefile --windowed --name vid2mp3 convert_gui_windows.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)


def find_ffmpeg() -> str | None:
    """优先用 exe 同目录的 ffmpeg，其次 PATH。"""
    base = Path(getattr(sys, "frozen", False) and sys.executable or __file__).parent
    for name in ("ffmpeg.exe", "ffmpeg"):
        cand = base / name
        if cand.is_file():
            return str(cand)
    return shutil.which("ffmpeg")


class ConvertWorker(QThread):
    """后台转换线程。log: 一行日志; progress: (完成数, 总数); finished_ok: 正常结束。"""

    log = Signal(str)
    finished_ok = Signal(int, int, int, int)  # done, skipped, failed, total_in_dst

    def __init__(self, ffmpeg, src, dst, limit, parent=None):
        super().__init__(parent)
        self.ffmpeg = ffmpeg
        self.src = Path(src)
        self.dst = Path(dst)
        self.limit = limit  # 0 = 全部
        self.cancelled = False

    def run(self):
        self.dst.mkdir(parents=True, exist_ok=True)
        files = sorted(self.src.glob("*.mp4"))
        if not files:
            self.log.emit("视频目录里没有找到 mp4 文件。\n")
            self.finished_ok.emit(0, 0, 0, len(list(self.dst.glob("*.mp3"))))
            return

        done = skipped = failed = 0
        for f in files:
            if self.cancelled:
                self.log.emit("已取消。\n")
                break
            out = self.dst / (f.stem + ".mp3")
            if out.exists():
                skipped += 1
                self.log.emit(f"SKIP(已存在): {out.name}\n")
                continue
            # list 传参，不走 shell，中文/空格路径安全
            r = subprocess.run(
                [self.ffmpeg, "-y", "-i", str(f), "-vn",
                 "-acodec", "libmp3lame", "-q:a", "2", str(out),
                 "-loglevel", "error"],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode == 0:
                done += 1
                self.log.emit(f"OK: {out.name}\n")
            else:
                failed += 1
                out.unlink(missing_ok=True)
                self.log.emit(f"FAIL: {f.name}  {r.stderr.strip()}\n")
            if self.limit and done >= self.limit:
                self.log.emit(f"已达到本次上限 {self.limit}，停止。\n")
                break

        total = len(list(self.dst.glob("*.mp3")))
        self.log.emit(f"完成。新转换 {done}，跳过 {skipped}，失败 {failed}，"
                      f"输出目录现有 MP3 共 {total} 个。\n")
        self.finished_ok.emit(done, skipped, failed, total)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频转 MP3")
        self.resize(760, 560)
        self.worker: ConvertWorker | None = None

        self.ffmpeg = find_ffmpeg()

        central = QWidget()
        root = QVBoxLayout(central)

        # ---- ffmpeg 状态 ----
        ff = QLabel(f"ffmpeg: {self.ffmpeg or '未找到！请把 ffmpeg.exe 放到本程序同目录'}")
        ff.setStyleSheet("color: green;" if self.ffmpeg else "color: red;")
        root.addWidget(ff)

        # ---- 目录选择 ----
        grp = QGroupBox("目录设置")
        form = QVBoxLayout(grp)

        row1 = QHBoxLayout()
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("选择视频目录 (mp4 来源)")
        b1 = QPushButton("浏览…")
        b1.clicked.connect(self.pick_src)
        row1.addWidget(QLabel("视频目录"))
        row1.addWidget(self.src_edit, 1)
        row1.addWidget(b1)
        form.addLayout(row1)

        row2 = QHBoxLayout()
        self.dst_edit = QLineEdit()
        self.dst_edit.setPlaceholderText("选择音频输出目录 (MP3 保存到)")
        b2 = QPushButton("浏览…")
        b2.clicked.connect(self.pick_dst)
        row2.addWidget(QLabel("输出目录"))
        row2.addWidget(self.dst_edit, 1)
        row2.addWidget(b2)
        form.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("本次最多转换 (0 = 全部)"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 999)
        self.limit_spin.setValue(0)
        row3.addWidget(self.limit_spin)
        row3.addStretch(1)
        form.addLayout(row3)

        root.addWidget(grp)

        # ---- 按钮 ----
        btns = QHBoxLayout()
        self.btn_start = QPushButton("开始转换")
        self.btn_start.setStyleSheet(
            "background:#0078d4;color:white;padding:6px 20px;font-weight:bold;")
        self.btn_start.clicked.connect(self.start)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel)
        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_cancel)
        btns.addStretch(1)
        root.addLayout(btns)

        # ---- 日志 ----
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, 1)

        self.setCentralWidget(central)

    # ---- 目录选择 ----
    def pick_src(self):
        d = QFileDialog.getExistingDirectory(self, "选择视频目录")
        if d:
            self.src_edit.setText(d)

    def pick_dst(self):
        d = QFileDialog.getExistingDirectory(self, "选择音频输出目录")
        if d:
            self.dst_edit.setText(d)

    # ---- 转换 ----
    def start(self):
        if not self.ffmpeg:
            QMessageBox.critical(self, "错误", "找不到 ffmpeg。\n"
                                 "请把 ffmpeg.exe 放到本程序同一目录后重试。")
            return
        src, dst = self.src_edit.text().strip(), self.dst_edit.text().strip()
        if not src or not dst:
            QMessageBox.warning(self, "提示", "请先选择视频目录和输出目录。")
            return
        self.log_append(f"=== 开始: {src} -> {dst} ===\n")
        self.set_running(True)
        self.worker = ConvertWorker(self.ffmpeg, src, dst, self.limit_spin.value())
        self.worker.log.connect(self.log_append)
        self.worker.finished_ok.connect(self.on_done)
        self.worker.start()

    def cancel(self):
        if self.worker:
            self.worker.cancelled = True
            self.log_append("取消中…等待当前文件结束。\n")

    def on_done(self, done, skipped, failed, total):
        self.set_running(False)
        if failed:
            QMessageBox.warning(self, "完成(有失败)",
                                f"新转换 {done}，失败 {failed}，请查看日志。")

    def set_running(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        for w in (self.src_edit, self.dst_edit, self.limit_spin):
            w.setEnabled(not running)

    def log_append(self, text: str):
        self.log_view.insertPlainText(text)
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum())


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
