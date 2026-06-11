# Photoshop 插件说明

本目录包含两种 Photoshop 插件形式，功能完全相同：**将多页 PDF 完美导入为 Photoshop 图层**。

---

## 📁 目录结构

```
photoshop-plugin/
├── cep/                   ← CEP 扩展面板（推荐，支持 PS CC 2015 - 2026+）
│   ├── index.html
│   ├── CSXS/
│   ├── js/
│   ├── jsx/
│   └── 注册表添加_解决插件不显示问题(以管理员运行).bat
└── jsx/                   ← 独立 ExtendScript 脚本（兼容所有 PS 版本）
    └── pdf_to_layers.jsx
```

---

## 方案一：CEP 扩展面板（🌟 强烈推荐）

### ✅ 优点
- **完美融合**：现代化的暗色 UI 界面，像官方功能一样嵌入在侧边栏。
- **全自动探测**：选入 PDF 后自动使用指数倍增与二分法精准探测 PDF 总页数。
- **无损画质**：调用 PS 原生内核，100% 完美保留 CMYK/RGB 色彩、矢量细节与透明通道。
- **跨版本兼容**：向下兼容至 Photoshop CC 2015，向上兼容至最新的 2026+。

### 📦 安装方法

**Windows 系统：**
对于下载了 `PDF2PSD-CEP-Plugin.zip` 的用户，解压后会看到几个脚本：
- **方案 A（自动）**：右键点击 `install_windows.bat`，选择 **“以管理员身份运行”**。脚本会自动将插件复制到正确位置，并修改注册表。
- **方案 B（全手动）**：双击运行 `enable_debug_mode.reg` 导入注册表（这是必须的，否则面板不显示），然后将 `cep` 文件夹复制到 `C:\Program Files (x86)\Common Files\Adobe\CEP\extensions` 或 `%APPDATA%\Adobe\CEP\extensions` 目录下。

安装后重启 Photoshop，在菜单栏点击：**窗口 (Window) → 扩展功能 (Extensions) → PDF → PSD 图层导入**。

**macOS 系统：**
对于下载了 `PDF2PSD-CEP-Plugin.zip` 的用户，解压后打开终端（Terminal），将 `install_mac.sh` 拖入终端执行，或者手动执行：
1. 将 `cep` 文件夹复制到 `/Library/Application Support/Adobe/CEP/extensions/`。
2. 打开终端，运行命令开启开发者模式（对应你的 PS 版本）：
   ```bash
   defaults write com.adobe.CSXS.11 PlayerDebugMode 1
   ```
   *(注：数字 11 对应 PS 2022，如果不确定版本，可以运行脚本自动全覆盖写入)*

### 🎮 使用方式
1. 打开面板，点击“选择 PDF 文件”。
2. 插件会自动探测出总页数（如有需要可手动修改）。
3. 设置渲染分辨率（DPI）以及图层命名偏好。
4. 点击“开始导入”，享受全自动的高速转换！

---

## 方案二：独立 ExtendScript 脚本（.jsx）

### ✅ 优点
- **终极兼容**：甚至可以运行在十几年前的 Photoshop CS5 / CS6 上。
- **免安装**：零配置，直接运行。

### 📦 安装与运行

**方法 A — 永久安装（推荐）**

将 `jsx/pdf_to_layers.jsx` 拷贝到 Photoshop 的 Scripts 目录：

| 系统 | 路径 |
|------|------|
| Windows | `C:\Program Files\Adobe\Adobe Photoshop 20XX\Presets\Scripts\` |
| macOS | `/Applications/Adobe Photoshop 20XX/Presets/Scripts/` |

重启 Photoshop 后，在菜单 **文件 → 脚本** 中找到 `pdf_to_layers`。

**方法 B — 临时运行**

在 Photoshop 顶部菜单点击：**文件 → 脚本 → 浏览** → 选择你的 `pdf_to_layers.jsx` 文件即可直接运行。

### 🎮 使用方式
1. 运行脚本后，会弹出一个非常干净的原生对话框。
2. 点击「选择文件」定位到 PDF。
3. 如果未自动探测出页数，请手动输入。
4. 选择渲染 DPI，点击「开始导入」。
