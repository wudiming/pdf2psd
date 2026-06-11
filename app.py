"""
PDF → PSD Converter - Main GUI Application
Modern dark-theme desktop tool built with customtkinter.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import sys
from pathlib import Path

# Attempt to import converter; show friendly error if deps missing
try:
    from converter import convert_pdf_to_psd, get_pdf_info
    DEPS_OK = True
    DEPS_ERROR = ""
except ImportError as e:
    DEPS_OK = False
    DEPS_ERROR = str(e)


# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT       = "#4A9EFF"
ACCENT_HOVER = "#3A8EEF"
BG_CARD      = "#1E2130"
BG_MAIN      = "#151722"
TEXT_MUTED   = "#8891A5"
SUCCESS      = "#4CAF88"
ERROR_COL    = "#FF5C72"


# ── Widgets ───────────────────────────────────────────────────────────────────

class DropZone(ctk.CTkFrame):
    """Clickable PDF drop/select zone."""

    def __init__(self, master, on_file_selected, **kwargs):
        super().__init__(master, **kwargs)
        self.on_file_selected = on_file_selected

        self.configure(
            corner_radius=14,
            border_width=2,
            border_color=("#3A4560", "#3A4560"),
            fg_color=BG_CARD,
            cursor="hand2",
        )

        self._icon = ctk.CTkLabel(
            self, text="📂", font=ctk.CTkFont(size=42)
        )
        self._icon.pack(pady=(24, 4))

        self._title = ctk.CTkLabel(
            self,
            text="点击选择 PDF 文件",
            font=ctk.CTkFont(family="Microsoft YaHei", size=15, weight="bold"),
        )
        self._title.pack()

        self._sub = ctk.CTkLabel(
            self,
            text="支持多页 PDF，每页转为独立图层",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color=TEXT_MUTED,
        )
        self._sub.pack(pady=(2, 24))

        # Bind click everywhere in the zone
        for widget in (self, self._icon, self._title, self._sub):
            widget.bind("<Button-1>", self._on_click)

    def _on_click(self, _event=None):
        path = filedialog.askopenfilename(
            title="选择 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
        )
        if path:
            self.on_file_selected(path)

    def set_file(self, filename: str, info: str):
        self._icon.configure(text="✅")
        self._title.configure(text=filename, text_color=ACCENT)
        self._sub.configure(text=info, text_color=TEXT_MUTED)
        self.configure(border_color=ACCENT)

    def reset(self):
        self._icon.configure(text="📂")
        self._title.configure(text="点击选择 PDF 文件", text_color="white")
        self._sub.configure(text="支持多页 PDF，每页转为独立图层")
        self.configure(border_color=("#3A4560", "#3A4560"))


class StatusBar(ctk.CTkFrame):
    """Progress + status message widget."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, **kwargs)

        self._label = ctk.CTkLabel(
            self,
            text="请先选择 PDF 文件",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self._label.pack(padx=16, pady=(12, 6), anchor="w")

        self._bar = ctk.CTkProgressBar(self, height=6, corner_radius=3)
        self._bar.pack(fill="x", padx=16, pady=(0, 12))
        self._bar.set(0)

    def update(self, message: str, progress: float = -1,
               color: str | None = None):
        self._label.configure(
            text=message,
            text_color=color or TEXT_MUTED,
        )
        if progress >= 0:
            self._bar.set(progress)

    def reset(self):
        self._label.configure(text="请先选择 PDF 文件", text_color=TEXT_MUTED)
        self._bar.set(0)


# ── Main Application ──────────────────────────────────────────────────────────

class PDF2PSDApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("PDF → PSD 转换工具")
        self.geometry("560x800")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        # State
        self._pdf_path: str | None = None
        self._output_dir: str | None = None
        self._converting = False
        self._detected_pages: int = 0

        self._build_ui()

        if not DEPS_OK:
            self.after(300, self._show_dep_error)

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ─ Header ─────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(24, 4))

        ctk.CTkLabel(
            hdr,
            text="PDF",
            font=ctk.CTkFont(family="Microsoft YaHei", size=28, weight="bold"),
            text_color=ACCENT,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr,
            text=" → PSD 转换工具",
            font=ctk.CTkFont(family="Microsoft YaHei", size=28, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            self,
            text="每页 PDF 将成为 PSD 中的独立图层，无需 Photoshop",
            font=ctk.CTkFont(family="Microsoft YaHei", size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=24, pady=(0, 16))

        # ─ Drop Zone ──────────────────────────────────────────────────────────
        self._drop_zone = DropZone(
            self,
            on_file_selected=self._on_pdf_selected,
            height=150,
        )
        self._drop_zone.pack(fill="x", padx=24, pady=(0, 12))

        # ─ Page Count ─────────────────────────────────────────────────
        self._page_card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        self._page_card.pack(fill="x", padx=24, pady=(0, 12))

        page_row = ctk.CTkFrame(self._page_card, fg_color="transparent")
        page_row.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            page_row,
            text="📄 总页数：",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
        ).pack(side="left")

        self._page_entry = ctk.CTkEntry(
            page_row,
            width=70,
            height=30,
            font=ctk.CTkFont(size=13),
            justify="center",
            placeholder_text="1",
        )
        self._page_entry.pack(side="left", padx=(10, 0))

        self._detect_btn = ctk.CTkButton(
            page_row,
            text="🔍 重新识别",
            width=100,
            height=30,
            corner_radius=8,
            fg_color="#2A3450",
            hover_color="#3A4560",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            command=self._detect_pages,
        )
        self._detect_btn.pack(side="right")

        self._detect_status = ctk.CTkLabel(
            self._page_card,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self._detect_status.pack(fill="x", padx=16, pady=(0, 12), anchor="w")

        # ─ Output Directory ───────────────────────────────────────────────────
        out_card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        out_card.pack(fill="x", padx=24, pady=(0, 12))

        out_top = ctk.CTkFrame(out_card, fg_color="transparent")
        out_top.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            out_top,
            text="输出目录",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            out_top,
            text="浏览…",
            width=72,
            height=28,
            corner_radius=8,
            fg_color="#2A3450",
            hover_color="#3A4560",
            command=self._select_output_dir,
        ).pack(side="right")

        self._out_label = ctk.CTkLabel(
            out_card,
            text="与 PDF 相同目录（默认）",
            font=ctk.CTkFont(family="Microsoft YaHei", size=11),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self._out_label.pack(fill="x", padx=16, pady=(0, 12), anchor="w")

        # ─ DPI ────────────────────────────────────────────────────────────────
        dpi_card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        dpi_card.pack(fill="x", padx=24, pady=(0, 12))

        dpi_top = ctk.CTkFrame(dpi_card, fg_color="transparent")
        dpi_top.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            dpi_top,
            text="渲染分辨率",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
        ).pack(side="left")

        self._dpi_label = ctk.CTkLabel(
            dpi_top,
            text="150 DPI",
            font=ctk.CTkFont(family="Microsoft YaHei", size=13, weight="bold"),
            text_color=ACCENT,
        )
        self._dpi_label.pack(side="right")

        self._dpi_slider = ctk.CTkSlider(
            dpi_card,
            from_=72,
            to=300,
            number_of_steps=9,
            command=self._on_dpi_change,
            button_color=ACCENT,
            button_hover_color=ACCENT_HOVER,
            progress_color=ACCENT,
        )
        self._dpi_slider.set(150)
        self._dpi_slider.pack(fill="x", padx=16, pady=(0, 4))

        dpi_hints = ctk.CTkFrame(dpi_card, fg_color="transparent")
        dpi_hints.pack(fill="x", padx=16, pady=(0, 12))

        presets = [
            ("72\n屏幕", 72),
            ("150\n标准", 150),
            ("200\n高清", 200),
            ("300\n印刷", 300),
        ]
        for label, val in presets:
            btn = ctk.CTkButton(
                dpi_hints,
                text=label,
                width=80,
                height=42,
                corner_radius=6,
                fg_color="#2A3450",
                hover_color="#3A4560",
                font=ctk.CTkFont(size=11),
                command=lambda v=val: self._set_dpi(v),
            )
            btn.pack(side="left", padx=(0, 6), expand=True, fill="x")

        # ─ Status ─────────────────────────────────────────────────────────────
        self._status = StatusBar(self)
        self._status.pack(fill="x", padx=24, pady=(0, 12))

        # ─ Convert Button ─────────────────────────────────────────────────────
        self._btn = ctk.CTkButton(
            self,
            text="开始转换",
            height=52,
            corner_radius=14,
            font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            state="disabled",
            command=self._start_conversion,
        )
        self._btn.pack(fill="x", padx=24, pady=(0, 8))

        # ─ Footer ─────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="基于 PyMuPDF · 纯 Python 实现 · 无需 Photoshop",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
        ).pack(pady=(4, 16))

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_pdf_selected(self, path: str):
        self._pdf_path = path
        filename = os.path.basename(path)
        size_mb = os.path.getsize(path) / (1024 * 1024)

        try:
            info = get_pdf_info(path)
            pages = info['page_count']
            self._detected_pages = pages
            info_text = f"{pages} 页  ·  {size_mb:.1f} MB"
            # 自动填入页数
            self._page_entry.delete(0, "end")
            self._page_entry.insert(0, str(pages))
            self._detect_status.configure(
                text=f"✅ 自动识别到 {pages} 页", text_color=SUCCESS
            )
        except Exception:
            info_text = f"{size_mb:.1f} MB"
            self._detect_status.configure(text="⚠ 无法自动识别，请手动输入页数", text_color=ERROR_COL)

        self._drop_zone.set_file(filename, info_text)
        self._status.update("文件已选择，点击『开始转换』", 0)
        self._btn.configure(state="normal")

    def _detect_pages(self):
        """Re-detect page count for current PDF."""
        if not self._pdf_path:
            return
        self._detect_btn.configure(state="disabled", text="识别中…")
        self._detect_status.configure(text="正在识别页数…", text_color=TEXT_MUTED)

        def _run():
            try:
                info = get_pdf_info(self._pdf_path)
                pages = info['page_count']
                def _update():
                    self._detected_pages = pages
                    self._page_entry.delete(0, "end")
                    self._page_entry.insert(0, str(pages))
                    self._detect_status.configure(
                        text=f"✅ 识别到 {pages} 页", text_color=SUCCESS
                    )
                    self._detect_btn.configure(state="normal", text="🔍 重新识别")
                self.after(0, _update)
            except Exception as e:
                def _err():
                    self._detect_status.configure(text=f"⚠ 识别失败：{e}", text_color=ERROR_COL)
                    self._detect_btn.configure(state="normal", text="🔍 重新识别")
                self.after(0, _err)

        threading.Thread(target=_run, daemon=True).start()

    def _select_output_dir(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self._output_dir = path
            self._out_label.configure(
                text=path, text_color=("white", "white")
            )

    def _on_dpi_change(self, value):
        self._dpi_label.configure(text=f"{int(value)} DPI")

    def _set_dpi(self, value: int):
        self._dpi_slider.set(value)
        self._dpi_label.configure(text=f"{value} DPI")

    # ── Conversion ────────────────────────────────────────────────────────────

    def _start_conversion(self):
        if not self._pdf_path or self._converting:
            return

        if not DEPS_OK:
            self._show_dep_error()
            return

        self._converting = True
        self._btn.configure(state="disabled", text="转换中…")
        self._status.update("准备中…", 0)

        dpi = int(self._dpi_slider.get())
        # Use manually set page count (allows partial conversion)
        try:
            total_pages = int(self._page_entry.get())
            if total_pages < 1:
                raise ValueError
        except (ValueError, AttributeError):
            total_pages = None  # converter will use all pages

        stem = Path(self._pdf_path).stem
        out_dir = self._output_dir or str(Path(self._pdf_path).parent)
        output_path = os.path.join(out_dir, f"{stem}.psd")

        def _cb(current, total, msg):
            progress = current / total if total > 0 else 0
            self.after(0, self._status.update, msg, progress)

        def _run():
            try:
                convert_pdf_to_psd(
                    self._pdf_path,
                    output_path,
                    dpi=dpi,
                    compression=1,  # RLE
                    total_pages=total_pages,
                    progress_callback=_cb,
                )
                self.after(0, self._on_done, output_path)
            except Exception as exc:
                self.after(0, self._on_error, str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _on_done(self, output_path: str):
        self._converting = False
        self._status.update("✅  转换完成！", 1.0, color=SUCCESS)
        self._btn.configure(state="normal", text="开始转换")

        if messagebox.askyesno(
            "完成",
            f"PSD 文件已保存至：\n{output_path}\n\n是否打开所在文件夹？",
        ):
            os.startfile(os.path.dirname(output_path))

    def _on_error(self, msg: str):
        self._converting = False
        self._status.update(f"❌  转换失败", 0, color=ERROR_COL)
        self._btn.configure(state="normal", text="开始转换")
        messagebox.showerror("转换失败", f"错误信息：\n{msg}")

    def _show_dep_error(self):
        messagebox.showerror(
            "缺少依赖",
            f"请先安装依赖库：\n\n  pip install -r requirements.txt\n\n{DEPS_ERROR}",
        )


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = PDF2PSDApp()
    app.mainloop()
