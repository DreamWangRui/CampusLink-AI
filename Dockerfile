# ============================================================
# CampusLink AI - Docker 多阶段构建
# 阶段 1 frontend-builder: 构建 Vue3 前端静态产物
# 阶段 2 backend:         FastAPI 后端运行环境（target: backend）
# 阶段 3 frontend:        Nginx 托管前端 + 反代 /api（target: frontend）
#
# docker-compose.yml 通过 build.target 选取 backend / frontend 两个目标
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

# 构建前端静态文件（产物在 /app/frontend/dist）
RUN pnpm run build

# ==================== 阶段 2: 后端运行环境 ====================
FROM python:3.11-slim AS backend

WORKDIR /app

# 安装系统依赖（curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv --no-cache-dir

# 复制后端依赖文件（uv.lock 一并复制，保证镜像内依赖与本地验证的一致）
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./

# 安装 Python 依赖（--frozen 严格按 uv.lock 安装，禁止隐式重新解析）
RUN uv sync --frozen --no-dev

# 复制后端源码
COPY backend/ ./

# 创建数据目录（生产环境由 docker-compose 卷挂载覆盖）
RUN mkdir -p /app/uploads /app/chroma_db /app/data

# 数据目录基准：容器内代码在 /app/app/config.py，向上推导会错误得到 /，
# 显式指定为 /app 使 chroma_db / uploads 落在挂载卷上（持久化）
ENV APP_BASE_DIR=/app

# HuggingFace 镜像站默认值（国内网络直连 huggingface.co 不稳定），
# 可通过运行时环境变量 HF_ENDPOINT 覆盖
ENV HF_ENDPOINT=https://hf-mirror.com

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动 FastAPI 服务
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ==================== 阶段 3: Nginx 前端服务 ====================
FROM nginx:1.27-alpine AS frontend

# 复制自定义 Nginx 配置（托管 dist + 反代 /api）
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# 复制前端构建产物（来自阶段 1）
COPY --from=frontend-builder /app/frontend/dist/ /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
