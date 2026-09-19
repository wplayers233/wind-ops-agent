# 架构真源（@architecture.md）

> 内部真源：任何编码任务开始前必读；每个 major feature / milestone 后回写本文件。
> 外部用户文档是根目录 `README.md`（功能特性、快速开始），不要把用户侧内容写进这里。

## 1. 系统概览

面向风电设备运维的多模态 RAG 工作台，前后端分离的小型 monorepo：

- `apps/backend/`：FastAPI 服务（Python），承载全部业务语义。
- `apps/frontend/`：React + TypeScript + Vite 单页 UI（`src/App.tsx`），只消费后端 API。
- `build.ps1`：根质量门 = 后端门禁（`apps/backend/scripts/build.py`：AST 语法检查 → 全量 pytest → 可选在线冒烟）+ 前端生产构建（`tsc --noEmit && vite build`）。
- `docker-compose.yml`：本地 Redis / Milvus / 应用服务编排。

## 2. Owner Map（唯一 owner）

| 概念 | 唯一 Owner | 说明 |
| --- | --- | --- |
| HTTP 端点与协议映射 | `app/main.py` | 仅做协议映射：`/health` `/metrics` `/conversations` `/docs` `/chat` `/chat/{session_id}/resume` `/retrieve` `/ingest` `/evaluation` `/ticket`；禁止私造业务语义 |
| API 合同（请求/响应） | `app/schemas.py` | 所有端点入参出参的 Pydantic 模型 |
| 领域模型 | `app/models.py` | |
| Agent 与状态 | `app/services/agent.py`（`WindOpsAgent`）+ `app/services/agent_state.py`（`WindOpsState`） | |
| 编排流程 | `app/services/graph.py` | LangGraph `build_graph`：意图 → 检索 → 安全 → 诊断 → 答案 → 记忆写回 |
| 意图识别 | `app/services/intent_router.py` | 规则驱动，规则数据在 `app/data/intent_rules.json` |
| 混合检索 | `app/services/hybrid_retrieval.py` | BM25 + dense 并行召回、RRF 融合、BGE 重排（`LocalHybridIndex`、`BGEReranker`） |
| 检索服务入口 | `app/services/retriever.py` | |
| 检索工具封装 | `app/services/tools.py` | 面向 graph 节点的 retrieve / safety / diagnosis / ticket 工具函数 |
| 向量存储（本地实现） | `app/services/vector_store.py` | `MultimodalVectorStore` |
| 存储后端抽象 | `app/services/storage.py` | `MemoryBackend` / `VectorBackend` 协议 + InMemory / Redis / Milvus 实现 |
| 安全门 | `app/services/safety.py` | `assess_safety`：高风险操作中断等待用户确认 |
| 诊断 | `app/services/diagnosis.py` | |
| 答案组装 | `app/services/answer_planner.py` | |
| 会话与记忆 | `app/services/conversations.py` + `app/services/memory.py` | 短期记忆（历史/摘要/上下文）；长期记忆异步写回与召回 |
| Provider 协议与降级实现 | `app/services/providers.py` | OCR / Vision / Embedding / Reranker 协议 + Mock 实现 |
| LLM 接入 | `app/services/llm_client.py` + `app/services/model_factory.py` | OpenAI-compatible |
| 多模态提取 | `app/services/ocr.py` + `app/services/vision.py` | PDF / PPTX / 图像解析 |
| 语料管理 | `app/services/corpus.py` | |
| 评估 | `app/services/evaluator.py` + `app/services/ragas_adapter.py` | 黄金集 `app/data/evaluation/golden_path.jsonl`；Ragas 优先，未配置时离线 fallback |
| 指标 | `app/services/metrics.py` | `/metrics` 数据源（`get_system_metrics`） |
| 实验/耗时度量 | `app/services/experiment.py` | `TaskMeasurement` |
| 用户界面 | `apps/frontend/src/App.tsx` | 单文件 React 应用；只消费 API 结构化状态 |

**禁止成为 owner 的层**：`app/main.py`（HTTP 映射）、`apps/frontend/src/*`（UI）、`apps/backend/scripts/`、`docker-compose.yml`。它们只做接线、展示和基础设施，不得拥有业务语义、状态机或用户可见结论。

## 3. 核心数据流

1. **入库**：`POST /ingest` → `corpus` → `ocr` / `vision` 提取（未配置外部服务时用本地/Mock 实现）→ `vector_store` / `corpus` 持久化。
2. **问答**：`POST /chat` → `intent_router` → `retriever`（`hybrid_retrieval`：BM25 + dense + RRF，可选重排）→ `safety` 评估（高风险则中断，`POST /chat/{session_id}/resume` 确认后恢复）→ `diagnosis` → `answer_planner` → 带可追溯引用的答案 → `memory` 写回。
3. **评估**：`GET /evaluation` → `evaluator`（Ragas 优先；未配置时返回版本化黄金集的离线评估并说明原因）。

## 4. 降级策略（产品边界的一部分）

外部依赖全部是可选 adapter，缺失时显式降级而不是失败：

| 依赖 | 已配置 | 未配置 |
| --- | --- | --- |
| Redis / Milvus | `storage.py` 远程 backend | 会话隔离的 InMemory backend |
| OCR / Vision / Embedding / Reranker | `providers.py` 真实 provider | `providers.py` Mock / 规则实现 |
| Ragas | `ragas_adapter.py` | `evaluator.py` 离线黄金集评估 |
| LLM | `llm_client.py`（OpenAI-compatible） | 规则/模板回答 |

provider 状态与降级原因必须在证据和响应中可观测，禁止伪健康状态。

## 5. 测试布局

- `tests/unit/services/`：快速隔离单元测试（agent、graph、intent_router、retriever、safety、memory、diagnosis、answer_planner、productization）。
- `tests/integration/api/`：API 合同（test_api、test_contracts、test_documents、test_graph_api、test_productization_api）。
- `tests/integration/e2e/`：`test_quality_gate_e2e.py` 端到端质量门。
- `pytest.ini`：`pythonpath = .`，`testpaths = tests`，`test_*.py`。

## 6. 验收命令

- 根目录：`./build.ps1`（PowerShell）；`./build.ps1 -SmokeOnline` 需要后端已运行在 `127.0.0.1:8000`。
- `apps/backend/`：`python -m pytest`；`python scripts/build.py`。
- `apps/frontend/`：`npm run check`（= `tsc --noEmit && vite build`）。
- 本地栈：`docker compose up --build`。

## 7. 边界（non-goal）

本地可复现 demo。不做：生产部署、多租户、云运维、真实设备接入、高并发与横向扩展。外部服务缺失时显式降级是产品承诺，不得为了"看起来完整"伪造数据。
