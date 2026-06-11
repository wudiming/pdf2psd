# Photoshop 插件说明

本目录包含两种 Photoshop 插件形式，功能相同：将多页 PDF 导入为 Photoshop 图层。

---

## 📁 目录结构

```
photoshop-plugin/
├── jsx/                   ← ExtendScript 脚本（所有 PS 版本）
│   └── pdf_to_layers.jsx
└── uxp/                   ← UXP 面板插件（PS 2021+）
    ├── manifest.json
    ├── index.html
    ├── index.js
    ├── styles.css
    └── lib/               ← 需要手动放入 PDF.js 文件
        ├── pdf.min.js
        └── pdf.worker.min.js
```

---

## 方案一：ExtendScript .jsx（推荐，兼容所有 PS 版本）

### ✅ 优点
- 适用于所有 Photoshop 版本（CS5 以上）
- 使用 PS 自带 PDF 渲染引擎，质量最佳
- 无需额外配置

### 📦 安装方法

**方法 A — 永久安装（推荐）**

将 `jsx/pdf_to_layers.jsx` 拷贝到 Photoshop 的 Scripts 目录：

| 系统 | 路径 |
|------|------|
| Windows | `C:\Program Files\Adobe\Adobe Photoshop 20XX\Presets\Scripts\` |
| macOS | `/Applications/Adobe Photoshop 20XX/Presets/Scripts/` |

重启 Photoshop 后，在菜单 **文件 → 脚本** 中找到 `pdf_to_layers`。

**方法 B — 临时运行**

菜单：**文件 → 脚本 → 浏览** → 选择 `pdf_to_layers.jsx`

### 🎮 使用方式
1. 运行脚本后会弹出设置对话框
2. 点击「浏览」选择 PDF 文件
3. 输入 PDF 总页数（在 PDF 阅读器中查看）
4. 选择 DPI，点击「开始转换」

> ⚠️ 需要提前知道 PDF 页数（在 macOS 预览/Adobe Reader 中查看）

---

## 方案二：UXP 插件（PS 2021+ 的现代面板插件）

### ✅ 优点
- 嵌入 Photoshop 面板，无需每次通过菜单运行
- 现代暗色 UI
- 实时进度显示
- 不需要输入页数，自动识别

### 📦 前置步骤：下载 PDF.js

UXP 插件依赖 PDF.js 渲染库，需要手动下载并放入 `uxp/lib/` 目录：

```bash
# 创建 lib 目录
mkdir photoshop-plugin/uxp/lib

# 从 CDN 下载（或访问 https://mozilla.github.io/pdf.js/getting_started/）
# 下载 pdfjs-dist，取其中：
#   build/pdf.min.js
#   build/pdf.worker.min.js
# 放入 uxp/lib/ 目录
```

或直接从 npm 获取：
```bash
cd photoshop-plugin/uxp
npm install pdfjs-dist
copy node_modules\pdfjs-dist\build\pdf.min.js lib\
copy node_modules\pdfjs-dist\build\pdf.worker.min.js lib\
```

### 📦 安装到 Photoshop

**方法 A — UXP Developer Tool（开发者模式）**

1. 安装 [Adobe UXP Developer Tool](https://developer.adobe.com/photoshop/uxp/2022/guides/devtool/)
2. 点击 `Add Plugin` → 选择 `uxp/manifest.json`
3. 点击 `Load` 加载插件

**方法 B — 打包分发**

使用 Adobe UXP Developer Tool 的 `Package` 功能，生成 `.ccx` 文件，双击即可安装。

### 🎮 使用方式
1. 在 PS 中打开插件面板：**插件 → PDF → PSD**
2. 点击面板中的文件区域选择 PDF
3. 调整 DPI
4. 点击「开始转换」，进度实时显示

---

## 对比

| | JSX 脚本 | UXP 插件 |
|---|---|---|
| PS 版本要求 | 所有版本 | PS 2021+ |
| 安装难度 | ⭐ 极简 | ⭐⭐⭐ |
| UI 体验 | 对话框 | 嵌入面板 |
| PDF 渲染 | PS 原生 | PDF.js |
| 需要输入页数 | ✅ 是 | ❌ 自动 |
| 运行方式 | 文件→脚本 | 插件面板 |
