"""
PDF2PSD Plugin Installer
Installs the CEP panel (Legacy Extension) into Photoshop.
Works with PS CC 2020 through PS 2026 on Windows and macOS.
No Adobe signing required.
"""
import os
import sys
import shutil
import platform
from pathlib import Path

IS_WINDOWS = (os.name == 'nt')

# ── Registry helper (Windows only) ────────────────────────────────────────────
def _set_player_debug_mode():
    """Set PlayerDebugMode=1 for all known CSXS versions (enables unsigned CEP)."""
    if not IS_WINDOWS:
        return
    try:
        import winreg
        versions = ["CSXS.9", "CSXS.10", "CSXS.11", "CSXS.12"]
        for ver in versions:
            key_path = rf"Software\Adobe\{ver}"
            try:
                key = winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(key, "PlayerDebugMode", 0, winreg.REG_SZ, "1")
                winreg.CloseKey(key)
                print(f"  ✔ 注册表: HKCU\\{key_path}\\PlayerDebugMode = 1")
            except Exception as e:
                print(f"  ⚠ 无法写入 {key_path}: {e}")
    except ImportError:
        print("  ⚠ 无法导入 winreg 模块（非 Windows 环境）")


def _set_player_debug_mode_mac():
    """Write PlayerDebugMode plist on macOS."""
    import subprocess
    versions = ["CSXS.9", "CSXS.10", "CSXS.11", "CSXS.12"]
    for ver in versions:
        domain = f"com.adobe.{ver}"
        try:
            subprocess.run(
                ["defaults", "write", domain, "PlayerDebugMode", "1"],
                check=True, capture_output=True
            )
            print(f"  ✔ plist: {domain} PlayerDebugMode = 1")
        except Exception as e:
            print(f"  ⚠ 无法写入 {domain}: {e}")


# ── Detect installed PS versions ───────────────────────────────────────────────
def _detect_ps_versions():
    """
    Scan UXP PluginsStorage directory to find installed PS versions.
    Returns a list of version strings, e.g. ['26', '27']
    """
    versions = []
    if IS_WINDOWS:
        base = Path(os.environ.get('APPDATA', '')) / "Adobe" / "UXP" / "PluginsStorage" / "PHSP"
    else:
        base = Path.home() / "Library" / "Application Support" / "Adobe" / "UXP" / "PluginsStorage" / "PHSP"

    if base.exists():
        for d in base.iterdir():
            if d.is_dir() and d.name.isdigit():
                versions.append(d.name)

    return sorted(versions)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("   PDF2PSD  ·  Photoshop 插件一键安装程序")
    print("=" * 55)
    print()

    # PyInstaller bundles files to sys._MEIPASS
    if getattr(sys, 'frozen', False):
        cep_src = Path(sys._MEIPASS) / "cep_data"
    else:
        # 当作为普通 py 脚本运行时，查找同级的 cep 目录，或源码结构的 photoshop-plugin/cep
        cep_src = Path(__file__).parent / "cep"
        if not cep_src.exists():
            cep_src = Path(__file__).parent / "photoshop-plugin" / "cep"

    if not cep_src.exists():
        print(f"❌ 错误：找不到内置插件数据目录 {cep_src}")
        input("\n按回车键退出...")
        return

    # ── 1. Detect installed PS versions ───────────────────────────────────────
    ps_versions = _detect_ps_versions()
    if ps_versions:
        print(f"检测到已安装的 Photoshop 版本：{', '.join(ps_versions)}")
        print()
    else:
        print("⚠ 未检测到 Photoshop 版本信息，将尝试通用路径安装。")
        print()

    # ── 2. Set registry / plist for unsigned CEP loading ─────────────────────
    print("【步骤 1/3】设置 Photoshop 允许加载未签名插件…")
    if IS_WINDOWS:
        _set_player_debug_mode()
    else:
        _set_player_debug_mode_mac()
    print()

    # ── 3. Install CEP plugin ─────────────────────────────────────────────────
    print("【步骤 2/3】安装 CEP 插件文件…")

    if IS_WINDOWS:
        cep_ext_dir = Path(os.environ.get('APPDATA', '')) / "Adobe" / "CEP" / "extensions"
    else:
        cep_ext_dir = Path.home() / "Library" / "Application Support" / "Adobe" / "CEP" / "extensions"

    dest = cep_ext_dir / "com.wudiming.pdf2psd"
    print(f"  目标路径: {dest}")

    try:
        if dest.exists():
            print("  → 发现旧版本，正在清理…")
            shutil.rmtree(dest)

        dest.mkdir(parents=True, exist_ok=True)

        for item in cep_src.iterdir():
            src_item = cep_src / item.name
            dst_item = dest / item.name
            if src_item.is_dir():
                shutil.copytree(src_item, dst_item)
            else:
                shutil.copy2(src_item, dst_item)

        if not (dest / "CSXS" / "manifest.xml").exists():
            raise FileNotFoundError("manifest.xml 未成功写入，杀毒软件可能阻止了写入。")

        print("  ✅ CEP 插件安装成功！")

    except PermissionError:
        print("  ❌ 权限不足！")
        if IS_WINDOWS:
            print("  💡 请右键此程序 → 以管理员身份运行，然后重试。")
        input("\n按回车键退出...")
        return
    except Exception as e:
        print(f"  ❌ 安装失败: {e}")
        input("\n按回车键退出...")
        return

    print()
    print("【步骤 3/3】验证安装…")
    checks = [
        dest / "CSXS" / "manifest.xml",
        dest / "index.html",
        dest / "jsx" / "bridge.jsx",
        dest / "js"  / "CSInterface.js",
    ]
    all_ok = True
    for f in checks:
        if f.exists():
            print(f"  ✔ {f.relative_to(dest)}")
        else:
            print(f"  ✘ 缺失: {f.relative_to(dest)}")
            all_ok = False

    print()
    if all_ok:
        print("=" * 55)
        print("  🎉 安装成功！")
        print("=" * 55)
        print()
        print("下一步操作：")
        print()
        print("  1. 完全退出 Photoshop（包括任务栏托盘）")
        print("  2. 重新打开 Photoshop")
        print("  3. 点击菜单：【窗口】→【扩展(旧版)】→【PDF → PSD】")
        print()
        print("  注：如果「扩展(旧版)」菜单下没有此项，")
        print("  请检查杀毒软件是否拦截了注册表修改，")
        print("  然后再次运行本安装程序。")
    else:
        print("⚠ 部分文件缺失，安装可能不完整，请重试。")

    print()
    input("按回车键退出...")


if __name__ == "__main__":
    main()
