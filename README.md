# 🎓 CampusLink AI - 校园智能助手

基于 **RAG（Retrieval-Augmented Generation，检索增强生成）** 的校园智能问答系统。

解决新生入学期间大量重复咨询问题，用户通过自然语言提问，系统自动从校园知识库中检索相关内容，结合 DeepSeek 大模型生成准确回答。

## ✨ 核心功能

- 📚 **文档导入** — 上传校园知识文档（PDF / DOCX / TXT / Markdown），自动解析入库
- 🔍 **语义检索** — 基于 BAAI/bge-small-zh-v1.5 向量模型，精准匹配知识库内容
- 🤖 **AI 问答** — 调用 DeepSeek 大模型，结合检索到的知识生成准确回答
- 💬 **聊天界面** — 直观的对话式交互，支持 Markdown 渲染
- 🗂️ **知识库管理** — 查看已导入文档、删除过期内容

## 🏗️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3 + TypeScript + Vite + Element Plus + Pinia + Axios |
| **后端** | FastAPI + Python 3.11+ + Uvicorn + Pydantic |
| **AI 模型** | DeepSeek (`deepseek-chat`) |
| **向量数据库** | ChromaDB（PersistentClient 本地持久化） |
| **Embedding** | BAAI/bge-small-zh-v1.5（本地运行，512 维） |
| **包管理** | uv（Python） + pnpm（前端） |

## 📁 项目结构

```
CampusLinkAI/
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── views/              # 页面组件
│   │   │   ├── ChatView.vue    # 聊天问答页
│   │   │   └── KnowledgeView.vue  # 知识库管理页
│   │   ├── api/                # API 封装层
│   │   ├── store/              # Pinia 状态管理
│   │   ├── router/             # 路由配置
│   │   └── types/              # TypeScript 类型
│   └── vite.config.ts
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/                # RESTful API 路由
│   │   │   ├── chat.py         # 聊天接口
│   │   │   ├── document.py     # 文档上传接口
│   │   │   └── knowledge.py    # 知识库管理接口
│   │   ├── services/           # 核心服务层
│   │   │   ├── embedding_service.py   # 向量化
│   │   │   ├── llm_service.py         # LLM 调用
│   │   │   ├── rag_service.py         # RAG 编排层
│   │   │   ├── document_service.py    # 文档解析
│   │   │   └── splitter_service.py    # 文本切分
│   │   ├── database/           # ChromaDB 客户端
│   │   ├── models/             # Pydantic 数据模型
│   │   └── main.py             # 应用入口
│   └── pyproject.toml
├── uploads/                    # 上传文件存储
├── chroma_db/                  # 向量数据持久化
├── .env                        # 环境变量配置
├── start.sh / start.bat        # 一键启动脚本
├── Dockerfile                  # Docker 镜像构建
├── docker-compose.yml          # Docker Compose 部署
└── README.md
```

## 🚀 快速开始

### 环境要求

- **Python** 3.11+
- **Node.js** 18+
- **pnpm**（前端包管理）
- **uv**（Python 包管理）

### 1. 克隆项目

```bash
cd CampusLinkAI
```

### 2. 配置 API Key

编辑 `.env` 文件，填入你的 DeepSeek API Key：

```env
DEEPSEEK_API_KEY=your_actual_api_key
```

> 获取 API Key: [https://platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)

### 3. 启动服务

#### 方式一：一键启动（推荐）

**Windows:**
```bash
start.bat
```

**Linux / macOS:**
```bash
chmod +x start.sh
./start.sh
```

#### 方式二：手动启动

**后端:**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**前端:**

```bash
cd frontend
pnpm install
pnpm dev
```

### 4. 访问应用

- **前端页面**: [http://localhost:5173](http://localhost:5173)
- **API 文档（Swagger）**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **健康检查**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

## 🐳 Docker 部署

```bash
# 1. 配置环境变量（Compose 会自动读取根目录 .env）
#    编辑 .env，填入真实的 API Key
#    （可选）在 .env 中添加 NGINX_PORT=8080 修改前端访问端口

# 2. 构建并启动
docker compose up -d

# 3. 查看日志
docker compose logs -f

# 4. 停止
docker compose down
```

### 容器架构

| 服务 | 说明 | 访问地址 |
|------|------|----------|
| **frontend** (Nginx) | 托管前端静态文件 + 反向代理 `/api` | `http://localhost`（主入口） |
| **backend** (FastAPI) | RAG 问答后端 | `http://localhost:8000`（调试用，Swagger 文档） |

浏览器访问 `http://localhost` 即可使用完整应用（UI 与 API 同源，无需跨域）；后端 8000 端口保留用于直接调试 API，如不需要可删除 `docker-compose.yml` 中 backend 的 `ports` 配置。

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | 发送问题，获取 AI 回答 |
| `POST` | `/api/document/upload` | 批量上传文档并导入知识库（支持文件夹分类） |
| `GET` | `/api/knowledge/list` | 获取知识库文档列表 |
| `GET` | `/api/knowledge/folders` | 获取所有文件夹/分类列表 |
| `PUT` | `/api/knowledge/move` | 移动文档到其他文件夹（新名称自动创建） |
| `DELETE` | `/api/knowledge/delete` | 删除指定文档 |
| `GET` | `/api/health` | 健康检查 |

### 示例

**问答:**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "校园卡丢了怎么办？"}'
```

**文档上传（支持批量与分类）:**

```bash
curl -X POST http://localhost:8000/api/document/upload \
  -F "files=@campus_guide.pdf" \
  -F "folder=校园指南"
```

## 🔄 业务流程

### 文档导入
```
上传文件(≤20MB) → 解析文本 → 文本切分(800字/块，重叠200) → Embedding 向量化 → ChromaDB 存储
```

### 智能问答
```
用户提问 → Embedding 向量化 → 语义检索(Top7) → 相似度阈值过滤(distance ≤ 0.8) → 构造 Prompt → DeepSeek → 返回答案
```

> 阈值标定依据：相关查询余弦距离实测约 0.5~0.65，无关查询约 1.3+；全部片段被过滤时直接返回"暂无相关信息"，不再调用 LLM。

## 🗺️ 版本路线

- ✅ **V1（当前）** — RAG 基础问答 + 文档上传管理
- 🔜 **V2** — 对话历史 + 会话管理 + 多知识库
- 🔜 **V3** — Agent + 校历/食堂/地图查询
- 🔜 **V4** — MCP + Tool Calling 全功能校园助手

## 📝 开发说明

- 后端使用 **uv** 管理 Python 依赖，运行 `uv sync` 安装
- 前端使用 **pnpm** 管理依赖，运行 `pnpm install` 安装
- 所有代码包含**中文注释**，便于理解和维护
- Embedding 模型在首次运行时自动下载，请确保网络连接正常

## 📄 许可证

MIT License
