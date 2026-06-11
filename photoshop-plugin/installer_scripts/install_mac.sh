#!/bin/bash
echo "==================================================="
echo "  PDF2PSD CEP 插件自动安装脚本 (macOS)"
echo "==================================================="
echo ""

DEST="$HOME/Library/Application Support/Adobe/CEP/extensions/com.wudiming.pdf2psd"

echo "[步骤 1/2] 复制插件文件到系统目录..."
if [ -d "$DEST" ]; then
    echo "  发现旧版本，正在清理..."
    rm -rf "$DEST"
fi

mkdir -p "$DEST"
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

cp -R "$DIR/cep/"* "$DEST/"
if [ $? -ne 0 ]; then
    echo "  ❌ 复制文件失败！权限可能不足。"
    exit 1
fi
echo "  ✅ 复制完成！"
echo ""

echo "[步骤 2/2] 写入 plist 以允许加载未签名插件..."
defaults write com.adobe.CSXS.9 PlayerDebugMode 1
defaults write com.adobe.CSXS.10 PlayerDebugMode 1
defaults write com.adobe.CSXS.11 PlayerDebugMode 1
defaults write com.adobe.CSXS.12 PlayerDebugMode 1
defaults write com.adobe.CSXS.13 PlayerDebugMode 1
defaults write com.adobe.CSXS.14 PlayerDebugMode 1
defaults write com.adobe.CSXS.15 PlayerDebugMode 1
echo "  ✅ plist 修改完成！"
echo ""

echo "==================================================="
echo "🎉 安装成功！"
echo "请完全退出并重新打开 Photoshop。"
echo "在菜单 【窗口】 -> 【扩展功能(旧版)】 -> 【PDF -> PSD 图层导入】 中打开面板。"
echo "==================================================="
echo ""
