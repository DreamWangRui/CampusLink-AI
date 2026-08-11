# ============================================================
# CampusLink AI - Docker 多阶段构建
# 前端构建 → 后端环境 → 统一运行
# ============================================================

# ==================== 阶段 1: 前端构建 ====================
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

# 安装 pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# 复制前端依赖文件
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# 安装前端依赖
RUN pnpm install --frozen-lockfile

# 复制前端源码
COPY frontend/ ./

# 构建前端静态文件
RUN pnpm run build

# ==================== 阶段 2: 后端运行环境 ====================
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv --no-cache-dir

# 复制后端依赖文件
COPY backend/pyproject.toml backend/.python-version ./

# 安装 Python 依赖
RUN uv sync --no-dev

# 复制后端源码
COPY backend/ ./

# 复制前端构建产物（从阶段1）
COPY --from=frontend-builder /app/frontend/dist/ ./frontend/dist/

# 创建数据目录
RUN mkdir -p /app/uploads /app/chroma_db

# 复制环境变量文件（如果不存在则跳过，Docker Compose 会通过 environment 注入）

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动 FastAPI 服务
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
