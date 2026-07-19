# Wind Ops Agent

`Python` `FastAPI` `LangGraph` `React` `TypeScript` `Vite` `Docker`

一个面向风电设备运维的多模态 RAG 工作台。系统将报警码、设备现象、PDF/PPT 资料和图解证据组织为可追溯的诊断结果，支持混合检索、安全确认、会话记忆和质量评估。

> 项目以可复现的本地 Demo 为目标。未配置 OCR、视觉、embedding、重排或向量数据库时，服务会明确降级到离线实现，而不是因外部依赖缺失而中断。

## 功能特性

### 多模态知识入库

- 支持导入 `.txt`、`.md`、`.pdf`、`.pptx`、`.png`、`.jpg` 和 `.jpeg`。
- PDF 提取页级文本；安装 PyMuPDF 后会同时渲染页面图像。PPTX 提取文本、图片和表格区域。
- 可通过 OpenAI-compatible 接口连接 dots.OCR 与 Qwen3-VL，提取 OCR 文本、图像描述、实体、关系和设备结构；未配置时使用本地 fallback。

### 混合检索与可解释证据

- BM25 稀疏召回与 dense 向量召回并行执行，通过 RRF 融合候选。
- 支持 `model`、`system`、`component`、`fault_domain`、`alarm_code`、`doc_type` 等元数据过滤。
- 可选 BGE Cross-Encoder 重排；未启用时保留稳定的 BM25 + dense + RRF 路径。
- 每条证据返回 BM25/dense 排名、RRF 分数、距离、过滤命中、模态和 provider 状态。

### 运维 Agent 与安全流程

- LangGraph 编排意图识别、检索、风险评估、诊断、工单摘要、答案生成和记忆写回。
- 高风险操作会中断流程，等待用户确认停机、断电和挂牌条件后再继续。
- 输出候选原因、排查步骤、工具/备件建议、风险提示和可追溯引用。

### 上下文与评估

- 短期会话记忆包含历史、摘要和上下文；长期记忆支持异步写入、语义/全文混合召回和距离阈值。
- 配置 Redis/Milvus 后使用远程 backend；不可用时使用会话隔离的内存 fallback。
- `/evaluation` 优先运行 Ragas 的 Context Precision、Context Recall、Faithfulness、Response Relevancy；默认返回版本化黄金集的离线 fallback，并说明原因。

## 快速开始

### 1. 克隆并安装依赖

```bash
git clone <your-repository-url>
cd wind-ops-agent
```

后端：

```powershell
cd apps/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

前端：

```powershell
cd ../frontend
npm install
```

### 2. 配置外部服务（可选）

模板位于 `apps/backend/.env.example`。本地启动时，请将需要的环境变量设置到 shell 或你的进程管理器；不要提交 `.env` 与任何 API Key。

最小离线运行不需要任何密钥。若需要生成式回答，可设置：

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
$env:OPENAI_MODEL = "gpt-4o-mini"
```

### 3. 启动服务

终端一，启动后端：

```powershell
cd apps/backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

终端二，启动前端：

```powershell
cd apps/frontend
npm run dev
```

打开 [http://localhost:5173](http://localhost:5173)。后端 OpenAPI 文档位于 [http://127.0.0.1:8000/api-docs](http://127.0.0.1:8000/api-docs)。

### Docker Compose

```powershell
docker compose up --build
```

该方式启动后端、前端、Redis、Milvus、etcd 和 MinIO。浏览器访问 [http://localhost:5173](http://localhost:5173)。

## 架构

```text
User Query / Uploaded Document
            |
            v
      FastAPI API Layer
            |
            +---------------------------+
            |                           |
            v                           v
      LangGraph Agent               Ingestion Pipeline
            |                           |
            v                           v
 supervisor -> retrieval -> safety  PDF/PPT/Image parsing
            |             |              |
            |             v              v
            |       confirmation gate  OCR / Qwen3-VL enrichment
            v                           |
 diagnosis -> ticket -> answer          v
            |                     embedding + document index
            v
      memory_write
            |
            v
 Redis short memory / Milvus long memory

Retrieval: BM25 + Dense Vector -> Metadata Filter -> RRF -> Optional BGE Reranker
Evaluation: Versioned Golden Dataset -> Ragas when enabled -> Offline fallback
```

## 项目结构

```text
wind-ops-agent/
├── apps/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── data/             # Mock 文档、意图规则、黄金评估集
│   │   │   ├── services/         # Agent、检索、解析、记忆、评估和 provider
│   │   │   ├── main.py           # FastAPI 入口与路由
│   │   │   └── schemas.py        # Pydantic API 契约
│   │   ├── scripts/              # 依赖检查与后端质量门禁
│   │   ├── tests/                # unit / integration / e2e 测试
│   │   ├── .env.example          # 外部服务配置模板
│   │   └── requirements.txt
│   └── frontend/
│       ├── src/                  # React 工作台、样式和入口
│       ├── package.json
│       └── vite.config.ts
├── memory-bank/                  # 架构、设计、实施计划与进度记录
├── docker-compose.yml
├── build.ps1                     # 全仓质量门禁
└── README.md
```

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | 服务健康状态。 |
| `GET` | `/metrics` | Demo 运行指标。 |
| `GET` | `/conversations` | 会话目录。 |
| `GET` | `/docs` | 当前知识库文档目录。 |
| `POST` | `/chat` | 运行 Agent 问答流程。 |
| `POST` | `/chat/{session_id}/resume` | 确认高风险条件后恢复流程。 |
| `POST` | `/retrieve` | 混合检索，支持 filters 与 distance threshold。 |
| `POST` | `/ingest` | 导入文本、PDF、PPTX 或图片资料。 |
| `POST` | `/ticket` | 根据证据生成工单摘要。 |
| `GET` | `/evaluation` | 返回 Ragas 或离线 fallback 评估。 |

示例检索：

```bash
curl -X POST http://127.0.0.1:8000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"齿轮箱油温高","top_k":3,"filters":{"component":"齿轮箱"},"distance_threshold":1.0}'
```

## 环境变量

### 核心聊天模型

| Variable | Description |
| --- | --- |
| `OPENAI_API_KEY` / `LLM_API_KEY` | OpenAI-compatible 聊天 API Key。 |
| `OPENAI_BASE_URL` | 聊天 API 地址，默认 OpenAI。 |
| `OPENAI_MODEL` | 聊天模型，默认 `gpt-4o-mini`。 |

### 多模态与检索

| Variable | Description |
| --- | --- |
| `OCR_BASE_URL` / `OCR_API_KEY` / `OCR_MODEL` | dots.OCR-compatible 服务。 |
| `VISION_BASE_URL` / `VISION_API_KEY` / `VISION_MODEL` | Qwen3-VL-compatible 服务。 |
| `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` | 统一 embedding 服务。 |
| `BGE_RERANKER_MODEL` | 可选本地 Cross-Encoder 模型名称；需额外安装 `sentence-transformers`。 |
| `EMBEDDING_FALLBACK_DIMENSIONS` | 离线哈希 embedding 维度，默认 `64`。 |
| `VITE_API_BASE` | 前端请求的后端地址，默认 `http://127.0.0.1:8000`。 |

### 记忆与评估

| Variable | Description |
| --- | --- |
| `REDIS_URL` / `MILVUS_URI` | 远程记忆 backend 地址。 |
| `MEMORY_REMOTE_ENABLED` | 设为 `true` 后启用 Redis/Milvus。 |
| `MEMORY_DISTANCE_THRESHOLD` | 长期记忆距离阈值，默认 `0.65`。 |
| `RAGAS_ENABLED` | 设为 `true` 后尝试真实 Ragas；失败会自动降级。 |

## 构建与测试

全仓质量门禁：

```powershell
.\build.ps1
```

运行在线健康检查：

```powershell
.\build.ps1 -SmokeOnline
```

单独执行：

```powershell
cd apps/backend
python scripts/build.py

cd ../frontend
npm run check
```

测试覆盖包含 API 契约、Agent 流程、意图路由、混合检索、记忆隔离、文档入库、安全确认和黄金路径端到端场景。

## GitHub 提交边界

提交源码、测试、文档、Docker 配置、`.env.example`、`package-lock.json` 和版本化评估集。不要提交 `.env`、`.venv`、`node_modules`、`dist`、`__pycache__` 或 `.pytest_cache`；根目录 `.gitignore` 已覆盖这些本地产物。

```bash
git add .
git commit -m "feat: wind ops rag demo"
git branch -M main
git remote add origin <your-github-repository-url>
git push -u origin main
```

## 当前边界

- 本仓库不包含 API Key、外部模型权重或生产 Redis/Milvus 数据。
- 外部 OCR、视觉、embedding、BGE 与 Ragas 的真实精度取决于你配置的服务和数据集。
- 项目定位为可演示、可测试、可扩展的工程原型，不是生产风场控制系统。
