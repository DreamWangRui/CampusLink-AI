# CampusLink AI 开发日志 / Changelog

记录每次优化的改动内容、核验结果与提交信息，按时间倒序排列。

---

## [2026-08-30] 变更五：前端体验细节 + 工程清理

> 对应《优化建议.md》🟡 #7 #8 #17 #18

### 改动内容

| 文件 | 改动 |
|------|------|
| `frontend/src/main.ts` | Element Plus 挂载 `zhCn` 中文语言包（原 `locale: undefined` 实际是英文默认值） |
| `frontend/index.html` | `<title>frontend</title>` → `CampusLink AI - 校园智能助手`；`lang="en"` → `zh-CN` |
| `backend/app/services/embedding_service.py` | 删除未被调用的 `embed_text()`（保留批量版 `embed_texts`） |
| `backend/main.py` | 删除 uv 脚手架残留的 hello world（与 `app/main.py` 同名易混淆） |
| `backend/pyproject.toml` + `uv.lock` | 移除从未使用的 `markdown` 依赖 |
| `README.md` | 参数同步：切分 500字/块→800/重叠200、Top5→Top7 + 阈值；修正上传示例字段名 `file=` → `files=`（原示例会 422）；补充批量上传/文件夹参数 |

### 核验检查

1. ✅ `pnpm build`（含 vue-tsc 类型检查）通过；
2. ✅ 构建产物 `dist/index.html` 标题正确，zh-cn 语言包已打包（产物含 locale 文案）；
3. ✅ `grep` 确认 `embed_text` 无残留引用；`uv lock` + `uv sync --frozen` 通过。

---

## [2026-08-30] 变更四：检索相似度阈值兜底

> 对应《优化建议.md》🔴 #3 —— 无关内容不再进入 Prompt，避免污染回答与无效 token 消耗

### 改动内容

- `app/config.py`：新增 `SIMILARITY_DISTANCE_THRESHOLD = 0.8`（ChromaDB 余弦距离，越小越相关）；
- `app/services/rag_service.py`：Top K 检索结果按阈值过滤；全部被过滤时短路返回"目前知识库暂无相关信息，请咨询学校相关部门。"，不再调用 LLM（知识库整体为空的提示语保持不变，两者语义不同）。

### 阈值标定（本地知识库实测）

| 查询 | 最小 distance | 判定 |
|------|--------------|------|
| 奖学金如何申请 / 奖学金金额是多少 | 0.526~0.568 | 相关 |
| 食堂营业时间 / 第三食堂几点开门（对测试文档） | 0.404 / 0.425 | 相关（同义改写仍命中） |
| 今天天气怎么样 | 1.348 | 无关 |
| 周杰伦的歌曲 | 1.536 | 无关 |

相关查询 0.4~0.65、无关查询 1.3+，取 **0.8** 作为分界，两侧均有充分余量。

### 核验检查

1. ✅ 本地：中文相关查询正常生成回答（引用文档数据）；无关查询返回兜底话术（未调用 LLM）；
2. ✅ 既有知识库数据兼容（原数据 distance 0.53~0.65 < 0.8，奖学金提问正常回答）；
3. ✅ 容器：同样行为复现（上传测试文档 → 相关提问准确回答"6:30-21:30"；无关提问兜底）；
4. ℹ️ 拼音类分布外查询（如 "shitang yingye shijian"）distance 超过阈值会被拦截——bge-small-zh 为中文模型，属预期行为；如需支持可后续加查询改写。

---

## [2026-08-30] 变更三：并发阻塞修复 + 上传安全加固 + 孤儿文件清理

> 对应《优化建议.md》🔴 #2 #5 #4

### 改动内容

| 文件 | 改动 |
|------|------|
| `app/api/chat.py`、`app/api/document.py`、`app/api/knowledge.py` | **`async def` → `def`**：RAG 全流程（CPU 向量化 + LLM 网络 IO）、文件解析、ChromaDB 查询均为阻塞操作，原先在事件循环内直接执行会卡住所有并发请求；改为同步端点后 FastAPI 自动放入线程池执行 |
| `app/config.py` | 新增 `MAX_FILE_SIZE = 20MB` |
| `app/api/document.py` | ① 上传前按 `MAX_FILE_SIZE + 1` 限量读取，超限拒绝；② `Path(file.filename).name` 消毒文件名，剥离路径成分（防 `../../evil.txt` 路径穿越）；③ 移除无意义的 `seek(0)` |
| `app/database/chroma_client.py` | `delete_document` 改为返回文档关联的原始文件名列表（`get` 时 `include=["metadatas"]`，不再拉取正文） |
| `app/api/knowledge.py` | 删除文档后同步 `unlink` uploads/ 下的源文件（原先源文件永久残留为孤儿） |

### 核验检查（本地 + 容器双端）

| 测试项 | 结果 |
|--------|------|
| 并发行为（同步端点进线程池） | ✅ 上传/问答/列表请求互不阻塞（本地 uvicorn 全流程验证） |
| 21MB 超大文件上传 | ✅ 拒绝："文件超过大小限制（最大 20MB）" |
| 文件名 `../../evil.exe` | ✅ 消毒为 `evil.exe` 并按格式拒绝（响应中 filename 无路径成分） |
| 正常上传 + 提问 + 删除全流程 | ✅ 本地与容器均通过 |
| 删除文档孤儿清理 | ✅ 响应含"并清理了 1 个源文件"，uploads/ 中测试文件消失，用户既有文件不受影响 |

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

| 文件 | 改动 |
|------|------|
| `backend/pyproject.toml` | 显式声明 `huggingface-hub>=1.29.0`（1.21.0 的 httpx 客户端 bug 上游已修复，升级后本地复现场景消失） |
| `backend/uv.lock` | 锁定 hub 1.21.0 → 1.29.0（连带 hf-xet 1.5.1 → 1.6.0） |
| `backend/app/services/embedding_service.py` | **模型已缓存时自动启用 HF 离线模式**（`HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1`）：跳过联网元数据校验，避免无代理网络下 SSL 失败多轮重试拖慢启动；无缓存的新环境保持联网可正常首次下载。注意环境变量必须在 huggingface_hub 导入前设置，故置于模块顶部 |
| `Dockerfile` | ① `backend` 阶段新增 `ENV HF_ENDPOINT=https://hf-mirror.com`（国内网络直连 huggingface.co 不稳定，默认走镜像站，可用环境变量覆盖）；② `frontend` 阶段 healthcheck 由 `wget localhost` 改为 `wget 127.0.0.1`（alpine 容器中 localhost 先解析 IPv6 `::1` 被 nginx 拒绝，导致容器始终 unhealthy）；③ 依赖安装改为 `COPY backend/uv.lock` + `uv sync --frozen`（严格按锁文件安装，保证镜像内依赖与本地验证一致） |
| `docker-compose.yml` | backend 新增 `hf_cache` 数据卷（`campuslink_hf_cache`）挂载 `/root/.cache/huggingface`：模型只需下载一次，容器重建后仍在，二次启动自动进入离线模式 |
| `.env.example` | 补充 `NGINX_PORT`、`HF_ENDPOINT` 说明 |

### 核验检查

1. ✅ **本地单元验证**：升级后全新进程加载 Embedding 模型成功（512 维），ChromaDB 检索返回 3 条结果（此前必现 `client has been closed`）；
2. ✅ **本地端到端**：uvicorn 启动日志无 SSL 重试记录（离线模式生效），`POST /api/chat` 返回真实 DeepSeek 回答；
3. ✅ `uv lock` + `uv sync --frozen` 通过（锁文件与 pyproject 一致）；
4. ✅ **容器级验收**（经 Nginx 8080 反代）：
   | 测试项 | 结果 |
   |--------|------|
   | backend/frontend 容器状态 | ✅ 均 healthy |
   | 空知识库提问兜底 | ✅ 返回"知识库中暂无内容，请先上传校园相关文档。" |
   | 上传测试文档（经反代） | ✅ 解析入库成功（1 Chunk） |
   | 提问触发完整 RAG + LLM | ✅ DeepSeek 准确引用测试文档内容（营业时间 6:30-21:30） |
   | 删除测试文档 | ✅ 删除成功，知识库恢复为 0 |
   | 模型加载 | ✅ 经 hf-mirror 30 秒完成，缓存落入 hf_cache 卷 |

### 遗留说明

- 宿主机 80 端口被系统服务占用，本机部署通过 `.env` 的 `NGINX_PORT=8080` 使用 8080 端口（`.env` 不入库，其他机器默认 80）；
- 前端镜像的 `frontend-builder` 阶段每次重建会重新 `pnpm install`，后续可考虑 pnpm store 缓存挂载加速（P3）。

### 提交记录

- 分支：`main` → 推送至 `origin/main`（github.com/DreamWangRui/CampusLink-AI）
- 涉及提交：见 `git log` 中「🐛 修复: huggingface_hub httpx 客户端 bug 导致 RAG 问答失败」

---
