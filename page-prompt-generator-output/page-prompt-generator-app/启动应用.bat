@echo off
chcp 65001 >nul
cls
echo ========================================
echo    页面提示词生成器 v1.0.0
echo    Page Prompt Generator
echo ========================================
echo.
echo 正在启动应用...
echo.

cd /d "%~dp0"

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo 找到 Python，正在启动服务器...
    echo.
    echo 服务器地址：
    echo http://localhost:8766
    echo.
    echo 浏览器会自动打开，如果没有请手动访问上面的地址
    echo.
    echo 按 Ctrl+C 可停止服务器
    echo ========================================
    echo.
    timeout /t 2 >nul
    start http://localhost:8766
    python -m http.server 8766
    goto :end
)

:: 检查 Python3
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo 找到 Python3，正在启动服务器...
    echo.
    echo 服务器地址：
    echo http://localhost:8766
    echo.
    echo 浏览器会自动打开，如果没有请手动访问上面的地址
    echo.
    echo 按 Ctrl+C 可停止服务器
    echo ========================================
    echo.
    timeout /t 2 >nul
    start http://localhost:8766
    python3 -m http.server 8766
    goto :end
)

:: 都没找到
echo ========================================
echo 未找到 Python
echo ========================================
echo.
echo 这个应用需要 Python 来运行本地服务器。
echo.
echo 或者你可以：
echo 1. 直接打开 index-standalone.html（部分浏览器支持）
echo 2. 安装 Python：https://www.python.org/downloads/
echo    安装时勾选 "Add Python to PATH"
echo.

:end
pause
