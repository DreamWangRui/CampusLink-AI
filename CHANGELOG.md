# CampusLink AI 开发日志 / Changelog

记录每次优化的改动内容、核验结果与提交信息，按时间倒序排列。

---

## [2026-08-30] 变更一：Docker 部署重构 —— Nginx 托管前端 + 反向代理 /api

> 对应《优化建议.md》🔴 P0 #1 —— 原 Dockerfile 将前端 dist 打进后端镜像但从未挂载，Docker 部署后无法访问 UI。

### 改动内容

| 文件 | 改动 |
|------|------|
| `docker/nginx.conf` | **新增**。Nginx 站点配置：托管前端静态产物（SPA History 模式回退到 index.html）、`/api/` 反向代理到 `backend:8000`（保留 /api 前缀）、Gzip 压缩、`/assets/` 长缓存、`/docs` 与 `/openapi.json` 透传（80 端口可访问 Swagger）、`/healthz` 轻量健康检查端点 |
| `Dockerfile` | **重构**为三个构建阶段：`frontend-builder`（pnpm 构建 Vue3）→ `backend`（Python 3.11 + uv 运行 FastAPI，不再打包前端产物）→ `frontend`（nginx:1.27-alpine + dist + nginx.conf）。compose 通过 `build.target` 分别选取 `backend` / `frontend` |
| `docker-compose.yml` | **重写**为双服务架构：`backend`（FastAPI，8000 端口保留用于调试）+ `frontend`（Nginx，宿主机端口默认 80、可用 `.env` 的 `NGINX_PORT` 修改）。`frontend` 依赖 `backend` 健康检查通过后启动（`depends_on: condition: service_healthy`），并新增前端容器 healthcheck |
| `.env.example` | 新增 `NGINX_PORT` 配置说明 |
| `README.md` | Docker 部署章节同步更新：新增"容器架构"表格（frontend/backend 职责与访问地址），修正原先误导性的 `cp .env .docker.env` 步骤（Compose 默认读取根目录 `.env`） |

### 架构变化

```
旧：浏览器 → 宿主机:8000 → FastAPI（仅 API，前端 dist 打包进镜像但无处服务 ❌）

新：浏览器 → Nginx(宿主机:80/8080) ─┬─ 静态文件（前端 SPA，/ 与 /knowledge 路由回退）
                                    └─ /api/* 反向代理 → FastAPI(容器内网:8000)
```

前端 UI 与 API 同源，不再有 CORS 问题；后端 8000 端口保留用于 Swagger 调试，可按需关闭对外暴露。

### 核验检查

1. ✅ `docker compose config` —— compose 文件语法有效；
2. ✅ `nginx -t` 语法校验 —— 首次在单容器中测试报 `host not found in upstream "backend"`，为预期现象（`backend` 主机名仅在 compose 网络内可解析）；随后创建临时 Docker 网络并注入 `backend` 网络别名模拟 compose 环境，校验通过：`syntax is ok / test is successful`；
3. ✅ `docker compose build` —— `campuslink_ai-backend` 与 `campuslink_ai-frontend` 两个镜像构建成功（后端 uv sync 安装 torch 等全部依赖，166s 完成）；
4. ✅ 冒烟测试 `docker compose up -d`（本机 80 端口被系统服务 PID 3328 占用，按设计回退：`.env` 写入 `NGINX_PORT=8080`）：
   | 测试项 | 结果 |
   |--------|------|
   | `GET http://localhost:8080/` 前端页面 | ✅ HTTP 200，text/html |
   | `GET http://localhost:8080/knowledge` SPA 路由回退 | ✅ HTTP 200，text/html |
   | `GET http://localhost:8080/api/health` 经 Nginx 反代 | ✅ 返回 `{"status":"ok",...}` |
   | `GET http://localhost:8080/docs` + `/openapi.json` 透传 | ✅ 均 HTTP 200 |
   | 容器 healthcheck | ✅ backend healthy；frontend healthcheck 通过 |
5. ⚠️ **核验中发现预存 bug（与本次改动无关）**：`POST /api/chat` 返回 `Cannot send a request, as the client has been closed. in query.`。排查结论：huggingface_hub 1.21.0（httpx 化版本）在模型文件元数据校验时其共享 httpx 客户端已被关闭，**本地全新进程（不涉及 ChromaDB、不涉及 Docker）同样复现**，属依赖层问题，非本次部署改动引入；临时验证 `HF_HUB_OFFLINE=1`（模型已缓存时跳过联网校验）可绕过。详见下一条变更。

### 提交记录

- 分支：`main` → 推送至 `origin/main`（github.com/DreamWangRui/CampusLink-AI）
- 涉及提交：见 `git log` 中「部署优化: Docker Compose 增加 Nginx 托管前端并反代 /api」

---

## [2026-08-30] 变更二：修复 huggingface_hub 客户端关闭导致 RAG 问答全链路失败（P0）

> 上一条核验中发现的预存 bug，阻塞聊天主功能，本地与 Docker 环境均受影响。

### 问题定位过程

1. 容器冒烟测试发现 `POST /api/chat` 报 `Cannot send a request, as the client has been closed. in query.`；
2. 完整堆栈显示异常抛自 `huggingface_hub/file_download.py → get_hf_file_metadata → httpx client.request`，即模型 tokenizer 加载时的 HuggingFace 元数据联网校验；
3. 对照实验：**全新 Python 进程、不初始化 ChromaDB、仅加载 Embedding 模型 → 同样失败** —— 排除本项目代码与 ChromaDB，锁定 `huggingface_hub 1.21.0` 的 httpx 客户端生命周期 bug；
4. 验证 `HF_HUB_OFFLINE=1` 后查询成功返回结果 —— 模型本地缓存完好，仅需跳过联网校验。

### 改动内容

（实施后填写）

### 核验检查

（实施后填写）

### 提交记录

（实施后填写）

---
