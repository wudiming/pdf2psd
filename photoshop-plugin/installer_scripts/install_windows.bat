@echo off
chcp 65001 >nul
echo ===================================================
echo   PDF2PSD CEP 插件自动安装脚本 (Windows)
echo ===================================================
echo.

set DEST="%APPDATA%\Adobe\CEP\extensions\com.wudiming.pdf2psd"

echo [步骤 1/2] 复制插件文件到系统目录...
if not exist %DEST% goto DoCopy
echo   发现旧版本，正在清理...
rmdir /s /q %DEST%

:DoCopy
mkdir %DEST%
xcopy /E /I /H /Y "%~dp0cep\*" %DEST% >nul
if errorlevel 1 goto CopyFailed

echo   ✅ 复制完成！
echo.

echo [步骤 2/2] 写入注册表以允许加载未签名插件...
reg add "HKCU\Software\Adobe\CSXS.9" /v PlayerDebugMode /t REG_SZ /d "1" /f >nul 2>&1
reg add "HKCU\Software\Adobe\CSXS.10" /v PlayerDebugMode /t REG_SZ /d "1" /f >nul 2>&1
reg add "HKCU\Software\Adobe\CSXS.11" /v PlayerDebugMode /t REG_SZ /d "1" /f >nul 2>&1
reg add "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_SZ /d "1" /f >nul 2>&1
reg add "HKCU\Software\Adobe\CSXS.13" /v PlayerDebugMode /t REG_SZ /d "1" /f >nul 2>&1
reg add "HKCU\Software\Adobe\CSXS.14" /v PlayerDebugMode /t REG_SZ /d "1" /f >nul 2>&1
reg add "HKCU\Software\Adobe\CSXS.15" /v PlayerDebugMode /t REG_SZ /d "1" /f >nul 2>&1
echo   ✅ 注册表修改完成！
echo.
echo ===================================================
echo 🎉 安装成功！
echo 请完全退出并重新打开 Photoshop。
echo 在菜单 【窗口】 -^> 【扩展功能(旧版)】 -^> 【PDF -^> PSD 图层导入】 中打开面板。
echo ===================================================
echo.
pause
exit /b

:CopyFailed
echo.
echo   ❌ 复制文件失败！
echo   💡 可能是权限不足，请尝试右键点击此脚本，选择【以管理员身份运行】。
echo.
pause
exit /b
