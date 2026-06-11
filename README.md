# pdf2psd 🗂️ → 🎨

> 将多页 PDF 转换为单个 PSD 文件，每页自动成为独立图层。

---

## ✨ 功能特性

- **无需 Photoshop** — 纯 Python 实现，自带 PSD 二进制写入器
- **多页 → 多图层** — 每页 PDF 转为 PSD 中的命名图层（第 1 页、第 2 页…）
- **可调 DPI** — 支持 72 / 96 / 150 / 200 / 300 DPI，平衡质量与文件大小
- **现代 GUI** — 暗色主题，自定义输出目录，实时进度显示
- **跨平台** — Windows / macOS / Linux（需要 Python 3.10+）

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行工具

```bash
python app.py
```

---

## 📦 依赖说明

| 库 | 用途 |
|---|---|
| `pymupdf` | PDF 渲染（每页→位图） |
| `customtkinter` | 现代暗色 GUI |
| `Pillow` | 图像处理 |

> `psd_writer.py` 为内置自研模块，无需额外安装。

---

## 🗂️ 项目结构

```
pdf2psd/
├── app.py          # GUI 入口
├── converter.py    # PDF 渲染与转换流程
├── psd_writer.py   # PSD 二进制格式写入器（自研）
├── requirements.txt
└── README.md
```

---

## 🔧 技术细节

- PSD 格式基于 Adobe 官方规范（版本 1）
- 图层数据使用 PackBits RLE 压缩
- 合并预览层自动合成，Photoshop 可直接识别图层

---

## 📄 License

MIT
