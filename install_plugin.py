"""
PDF2PSD UXP Plugin Installer
Copies the UXP plugin to the system's Adobe UXP PluginsExternal directory.
"""
import os
import sys
import shutil
from pathlib import Path
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    print("=" * 50)
    print("  PDF2PSD Photoshop 插件一键安装程序")
    print("=" * 50)
    print()

    # PyInstaller extracts bundled files to sys._MEIPASS
    if not getattr(sys, 'frozen', False):
        print("❌ 错误：请使用打包后的 .exe 或 .app 运行此程序。")
        input("\n按回车键退出...")
        return
        
    bundle_dir = Path(sys._MEIPASS) / "plugin_data"
    
    if os.name == 'nt':
        # Windows: %APPDATA%\Adobe\UXP\Plugins\External\PDF2PSD
        dest = Path(os.environ.get('APPDATA', '')) / "Adobe" / "UXP" / "Plugins" / "External" / "PDF2PSD"
    else:
        # macOS: ~/Library/Application Support/Adobe/UXP/Plugins/External/PDF2PSD
        dest = Path.home() / "Library" / "Application Support" / "Adobe" / "UXP" / "Plugins" / "External" / "PDF2PSD"
        
    print(f"目标安装路径:\n{dest}\n")
    
    try:
        if dest.exists():
            print("发现旧版本，正在清理...")
            shutil.rmtree(dest)
            
        print("正在复制文件...")
        # Create parent directories if they don't exist
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle_dir, dest)
        
        print("\n✅ 安装成功！")
        print("请重启 Photoshop，在顶部菜单栏找到：")
        print("【增效工具 (Plugins)】 -> 【PDF2PSD】")
        print("\n(注意：无需开启开发者模式，直接可用)")
        
    except Exception as e:
        print(f"\n❌ 安装失败: {e}")
        if os.name == 'nt' and not is_admin():
            print("提示：可能需要右键选择「以管理员身份运行」。")
        
    print()
    input("按回车键退出...")

if __name__ == "__main__":
    main()
