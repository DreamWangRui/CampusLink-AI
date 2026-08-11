#!/bin/bash
# ============================================================
# CampusLink AI 一键启动脚本（Linux / macOS）
# ============================================================
set -e

echo "=========================================="
echo "  CampusLink AI - 校园智能助手"
echo "  启动中..."
echo "=========================================="

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ==================== 检查环境 ====================
echo ""
echo "[1/4] 检查运行环境..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请安装 Python 3.11+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "错误: 未找到 node，请安装 Node.js 18+"
    exit 1
fi

# 检查 pnpm
if ! command -v pnpm &> /dev/null; then
    echo "提示: 正在安装 pnpm..."
    npm install -g pnpm
fi

# 检查 uv
if ! command -v uv &> /dev/null; then
    echo "提示: 正在安装 uv..."
    pip install uv
fi

echo "✓ 环境检查完成"

# ==================== 配置环境变量 ====================
echo ""
echo "[2/4] 配置环境变量..."

# 如果 .env 文件存在且 DEEPSEEK_API_KEY 未设置，则加载
if [ -f ".env" ]; then
    # 检查是否已设置 API Key
    source .env 2>/dev/null || true
    if [ "$DEEPSEEK_API_KEY" = "your_api_key_here" ] || [ -z "$DEEPSEEK_API_KEY" ]; then
        echo "⚠ 警告: 请先在 .env 文件中设置有效的 DEEPSEEK_API_KEY"
        echo "  获取地址: https://platform.deepseek.com/api_keys"
    fi
fi

# ==================== 启动后端 ====================
echo ""
echo "[3/4] 启动后端服务..."

cd "$SCRIPT_DIR/backend"
# 安装依赖（如果 .venv 不存在）
if [ ! -d ".venv" ]; then
    echo "正在安装后端依赖..."
    uv sync
fi

# 后台启动 FastAPI 服务
echo "启动 FastAPI 服务 (端口 8000)..."
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "✓ 后端服务已启动 (PID: $BACKEND_PID)"

# ==================== 启动前端 ====================
echo ""
echo "[4/4] 启动前端服务..."

cd "$SCRIPT_DIR/frontend"
# 安装依赖（如果 node_modules 不存在）
if [ ! -d "node_modules" ]; then
    echo "正在安装前端依赖..."
    pnpm install
fi

# 启动 Vite 开发服务器
echo "启动 Vite 开发服务器 (端口 5173)..."
pnpm dev &
FRONTEND_PID=$!
echo "✓ 前端服务已启动 (PID: $FRONTEND_PID)"

# ==================== 启动完成 ====================
echo ""
echo "=========================================="
echo "  CampusLink AI 启动完成！"
echo ""
echo "  前端地址: http://localhost:5173"
echo "  API 文档: http://localhost:8000/docs"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "=========================================="

# 捕获退出信号，清理后台进程
cleanup() {
    echo ""
    echo "正在停止服务..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo "所有服务已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 等待后台进程
wait
