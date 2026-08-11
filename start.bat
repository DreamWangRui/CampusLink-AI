@echo off
REM ============================================================
REM CampusLink AI 一键启动脚本（Windows）
REM ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ==========================================
echo   CampusLink AI - 校园智能助手
echo   启动中...
echo ==========================================

REM 获取脚本所在目录
cd /d "%~dp0"

REM ==================== 检查环境 ====================
echo.
echo [1/4] 检查运行环境...

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: 未找到 python，请安装 Python 3.11+
    pause
    exit /b 1
)

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: 未找到 node，请安装 Node.js 18+
    pause
    exit /b 1
)

where pnpm >nul 2>nul
if %errorlevel% neq 0 (
    echo 提示: 正在安装 pnpm...
    call npm install -g pnpm
)

where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo 提示: 正在安装 uv...
    call pip install uv
)

echo √ 环境检查完成

REM ==================== 配置环境变量 ====================
echo.
echo [2/4] 配置环境变量...

REM 检查 API Key 是否已配置
findstr /c:"your_api_key_here" .env >nul 2>nul
if %errorlevel% equ 0 (
    echo ⚠ 警告: 请先在 .env 文件中设置有效的 DEEPSEEK_API_KEY
    echo   获取地址: https://platform.deepseek.com/api_keys
)

REM ==================== 启动后端 ====================
echo.
echo [3/4] 启动后端服务...

cd /d "%~dp0backend"

REM 安装依赖（如果 .venv 不存在）
if not exist ".venv\" (
    echo 正在安装后端依赖...
    call uv sync
)

REM 启动 FastAPI 服务
echo 启动 FastAPI 服务 ^(端口 8000^)...
start "CampusLink-Backend" cmd /c "cd /d %~dp0backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo √ 后端服务已启动

REM ==================== 启动前端 ====================
echo.
echo [4/4] 启动前端服务...

cd /d "%~dp0frontend"

REM 安装依赖（如果 node_modules 不存在）
if not exist "node_modules\" (
    echo 正在安装前端依赖...
    call pnpm install
)

REM 启动 Vite 开发服务器
echo 启动 Vite 开发服务器 ^(端口 5173^)...
start "CampusLink-Frontend" cmd /c "cd /d %~dp0frontend && pnpm dev"
echo √ 前端服务已启动

REM ==================== 启动完成 ====================
echo.
echo ==========================================
echo   CampusLink AI 启动完成！
echo.
echo   前端地址: http://localhost:5173
echo   API 文档: http://localhost:8000/docs
echo.
echo   关闭此窗口不会停止服务。
echo   请在新打开的窗口中按 Ctrl+C 停止服务。
echo ==========================================

pause
endlocal
