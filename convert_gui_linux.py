#!/usr/bin/env python3
"""视频转 MP3 工具 (Linux 版, GTK4 + libadwaita)

把视频目录下的 mp4 提取音频转成 MP3，输出到音频目录。
已存在的 MP3 自动跳过。可限制本次转换数量。

运行: python3 convert_gui_linux.py
"""

import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

DEFAULT_SRC = ""
DEFAULT_DST = ""


class ConvertWorker(threading.Thread):
    """后台转换线程，逐个文件 ffmpeg 提取 MP3。"""

    def __init__(self, src, dst, limit, on_log, on_done):
        super().__init__(daemon=True)
        self.src = Path(src)
        self.dst = Path(dst)
        self.limit = limit  # 0 = 全部
        self.on_log = on_log
        self.on_done = on_done
        self.cancelled = False

    def run(self):
        self.dst.mkdir(parents=True, exist_ok=True)
        files = sorted(self.src.glob("*.mp4"))
        if not files:
            self.on_log("视频目录里没有找到 mp4 文件。\n")
            self.on_done()
            return

        done = skipped = failed = 0
        for f in files:
            if self.cancelled:
                self.on_log("已取消。\n")
                break
            out = self.dst / (f.stem + ".mp3")
            if out.exists():
                skipped += 1
                self.on_log(f"SKIP(已存在): {out.name}\n")
                continue
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", str(f), "-vn",
                 "-acodec", "libmp3lame", "-q:a", "2", str(out),
                 "-loglevel", "error"],
                capture_output=True, text=True)
            if r.returncode == 0:
                done += 1
                self.on_log(f"OK: {out.name}\n")
            else:
                failed += 1
                out.unlink(missing_ok=True)
                self.on_log(f"FAIL: {f.name}  {r.stderr.strip()}\n")
            if self.limit and done >= self.limit:
                self.on_log(f"已达到本次上限 {self.limit}，停止。\n")
                break

        total = len(list(self.dst.glob("*.mp3")))
        self.on_log(f"完成。新转换 {done}，跳过 {skipped}，失败 {failed}，"
                    f"输出目录现有 MP3 共 {total} 个。\n")
        self.on_done()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="视频转 MP3")
        self.set_default_size(720, 560)
        self.worker = None

        header = Adw.HeaderBar()

        # ---- 表单 ----
        grid = Gtk.Grid(column_spacing=10, row_spacing=10,
                        margin_top=14, margin_bottom=6,
                        margin_start=14, margin_end=14)

        def add_row(row, label, widget):
            grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)

        self.src_row = Adw.EntryRow(title="视频目录 (mp4 来源)")
        self.src_row.text = DEFAULT_SRC
        self.dst_row = Adw.EntryRow(title="音频输出目录 (MP3 保存到)")
        self.dst_row.text = DEFAULT_DST

        limit_box = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        adj = Gtk.Adjustment(lower=0, upper=999, value=0, step_increment=1)
        self.limit_spin = Gtk.SpinButton(adjustment=adj)
        self.limit_spin.set_tooltip_text("0 = 不限制，转换全部")
        limit_box.append(Gtk.Label(label="本次最多转换 (0=全部)"))
        limit_box.append(self.limit_spin)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(self.src_row)
        box.append(self.dst_row)
        box.append(limit_box)
        grid.attach(box, 0, 0, 2, 1)

        # ---- 按钮 ----
        btn_box = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER,
                          margin_top=10)
        self.btn_start = Gtk.Button(label="开始转换")
        self.btn_start.add_css_class("suggested-action")
        self.btn_start.connect("clicked", self.on_start)
        self.btn_cancel = Gtk.Button(label="取消")
        self.btn_cancel.set_sensitive(False)
        self.btn_cancel.connect("clicked", self.on_cancel)
        btn_box.append(self.btn_start)
        btn_box.append(self.btn_cancel)
        grid.attach(btn_box, 0, 1, 2, 1)

        # ---- 日志 ----
        self.log = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD,
                                monospace=True)
        self.log.set_margin_top(8)
        self.log.set_margin_bottom(8)
        scroll = Gtk.ScrolledWindow(child=self.log, vexpand=True)
        scroll.set_margin_start(14)
        scroll.set_margin_end(14)
        scroll.set_margin_bottom(14)
        scroll.add_css_class("card")

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.append(grid)
        page.append(scroll)
        self.set_content(page)

    # ---- helpers ----
    def append_log(self, text):
        def do():
            buf = self.log.get_buffer()
            buf.insert(buf.get_end_iter(), text)
            mark = buf.create_mark(None, buf.get_end_iter(), False)
            self.log.scroll_mark_onscreen(mark, 0.0)
        GLib.idle_add(do)

    def set_running(self, running):
        self.btn_start.set_sensitive(not running)
        self.btn_cancel.set_sensitive(running)
        for row in (self.src_row, self.dst_row, self.limit_spin):
            row.set_sensitive(not running)

    # ---- actions ----
    def on_start(self, _btn):
        src, dst = self.src_row.get_text().strip(), self.dst_row.get_text().strip()
        if not src or not dst:
            self.append_log("请填写视频目录和输出目录。\n")
            return
        self.append_log(f"=== 开始: {src} -> {dst} ===\n")
        self.set_running(True)
        self.worker = ConvertWorker(
            src, dst, int(self.limit_spin.get_value()),
            self.append_log, lambda: GLib.idle_add(self.set_running, False))
        self.worker.start()

    def on_cancel(self, _btn):
        if self.worker:
            self.worker.cancelled = True
            self.append_log("取消中…等待当前文件结束。\n")


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.stickerconvert")

    def do_activate(self):
        win = MainWindow(self)
        win.present()


if __name__ == "__main__":
    App().run(None)
