# pdf2psd 🗂️ → 🎨

> 全栈式终极解决方案：将多页 PDF 转换为单个 PSD 文件，每页自动成为独立图层。

本工具套件提供了**三种**独立的运行方式，满足各种不同的工作流需求。不管你是想要独立的桌面客户端，还是嵌入在 Photoshop 里的自动化面板，这里都有最佳答案。

---

## ✨ 核心套件

### 1. 独立桌面端 (Windows GUI)
无需安装 Photoshop！纯 Python 实现，自带现代暗黑风格 GUI 和自研的 PSD 二进制写入引擎。
- **免 PS 环境**：直接把多页 PDF 塞进去，吐出包含 PackBits RLE 高效压缩图层数据的标准 PSD。
- **开箱即用**：[下载 Release 中的 EXE 版本](https://github.com/wudiming/pdf2psd/releases)，双击即可使用。

### 2. Photoshop CEP 扩展面板 (强烈推荐)
如果你习惯在 Photoshop 里工作，这是最极致的体验。完美嵌入 PS 侧边栏，支持 PS CC 2015 到最新的 2026+。
- **全自动探测**：自动识别 PDF 总页数。
- **100% 完美无损**：调用 PS 内部渲染引擎，完美保留所有矢量清晰度、CMYK/RGB 色彩以及极致的透明通道。
- **安装与使用**：请查看 [photoshop-plugin/README.md](photoshop-plugin/README.md)。

### 3. Photoshop JSX 独立脚本
如果你用的是极其古老的 Photoshop (如 CS6)，或者追求 0 配置、免安装的极简主义，可以直接运行这个独立脚本。
- **零配置**：直接通过菜单“文件 → 脚本 → 浏览”即可运行。
- **安装与使用**：请查看 [photoshop-plugin/README.md](photoshop-plugin/README.md)。

---

## 🚀 源码运行桌面端 (开发者)

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行工具

```bash
python app.py
```

### 3. 打包 EXE

```bash
pyinstaller --noconfirm --onedir --windowed --add-data "venv/Lib/site-packages/customtkinter;customtkinter/" app.py
```

---

## 🗂️ 项目结构

```
pdf2psd/
├── app.py          # 桌面端 GUI 入口
├── converter.py    # PDF 渲染与转换流程
├── psd_writer.py   # PSD 二进制格式极速写入器（自研）
├── photoshop-plugin/
│   ├── cep/        # CEP 扩展面板源码
│   └── jsx/        # 独立 JSX 脚本源码
├── requirements.txt
└── README.md
```

---

## 📄 License

MIT
