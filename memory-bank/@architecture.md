# 架构真源（@architecture.md）

> 内部真源：任何编码任务开始前必读；每个 major feature / milestone 后回写本文件。
> 外部用户文档是根目录 `README.md`（功能特性、快速开始），不要把用户侧内容写进这里。

## 1. 系统概览

面向风电设备运维的多模态 RAG 工作台，前后端分离的小型 monorepo：

- `apps/backend/`：FastAPI 服务（Python），承载全部业务语义。
- `apps/frontend/`：React + TypeScript + Vite 单页 UI，只消费后端 API（已模块化：`src/api.ts` 统一请求、`src/components/`、`src/pages/`、`src/types.ts` 共享类型、`src/format.ts` 格式化，`App.tsx` 只做装配）。
- `build.ps1`：根质量门 = 后端门禁（`apps/backend/scripts/build.py`：AST 语法检查 → 全量 pytest → 可选在线冒烟）+ 前端生产构建（`tsc --noEmit && vite build`）。
- `docker-compose.yml`：本地 Redis / Milvus / 应用服务编排。

## 2. Owner Map（唯一 owner）

| 概念 | 唯一 Owner | 说明 |
| --- | --- | --- |
| HTTP 端点与协议映射 | `app/main.py` | 仅做协议映射：`/health` `/metrics` `/conversations` `/docs` `/chat` `/chat/{session_id}/resume` `/retrieve` `/ingest` `/evaluation` `/ticket`；禁止私造业务语义 |
| API 合同（请求/响应） | `app/schemas.py` | 所有端点入参出参的 Pydantic 模型 |
| 领域模型 | `app/models.py` | |
| Agent 与状态 | `app/services/agent.py`（`WindOpsAgent`）+ `app/services/agent_state.py`（`WindOpsState`） | |
| 编排流程 | `app/services/graph.py` | LangGraph `build_graph`：意图 → 检索 → 安全 → 诊断 → 答案 → 记忆写回；`resume` 前置校验，无待确认中断时抛 `ResumeNotAvailableError`（API 层映射 404） |
| 意图识别 | `app/services/intent_router.py` | 规则驱动，规则数据在 `app/data/intent_rules.json` |
| 混合检索 | `app/services/hybrid_retrieval.py` | BM25 + dense 并行召回、RRF 融合、BGE 重排（`LocalHybridIndex`、`BGEReranker`） |
| 检索服务入口 | `app/services/retriever.py` | 文档集唯一写入入口 `replace_docs` / `append_docs`（RLock 保护；`append_docs` 按 id 去重并返回 warnings） |
| 检索工具封装 | `app/services/tools.py` | 面向 graph 节点的 retrieve / safety / diagnosis / ticket 工具函数 |
| 向量存储（本地实现） | `app/services/vector_store.py` | `MultimodalVectorStore` |
| 存储后端抽象 | `app/services/storage.py` | `MemoryBackend` / `VectorBackend` 协议 + InMemory / Redis / Milvus 实现 |
| 安全门 | `app/services/safety.py` | `assess_safety`：消费**全部**证据（任一 `safety_level == high` 即高危，不只 top-1）；高危中断等待用户确认 |
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
| 用户界面 | `apps/frontend/src/*` | 模块化 React 应用（`api.ts` 请求层 + `types.ts` 类型 + `format.ts` 格式化 + `components/` + `pages/`）；`App.tsx` 是前端唯一状态 owner，页面/组件经 props 消费状态与回调；只消费 API 结构化状态 |

**禁止成为 owner 的层**：`app/main.py`（HTTP 映射）、`apps/frontend/src/*`（UI）、`apps/backend/scripts/`、`docker-compose.yml`。它们只做接线、展示和基础设施，不得拥有业务语义、状态机或用户可见结论。

## 3. 核心数据流

1. **入库**：`POST /ingest`（≤ 20MB，超限显式失败；解析与 provider 调用在`run_in_threadpool` 中执行，不阻塞事件循环）→ `corpus` → `ocr` / `vision` 提取（未配置外部服务时用本地/Mock 实现）→ `retriever.append_docs` 按 id 去重合并并重建索引。
2. **问答**：`POST /chat` → `intent_router` → `retriever`（`hybrid_retrieval`：BM25 + dense + RRF，可选重排）→ `safety` 评估（高风险则中断，`POST /chat/{session_id}/resume` 确认后恢复；对未知/已结束会话返回 404）→ `diagnosis` → `answer_planner` → 带可追溯引用的答案 → `memory` 写回。
3. **评估**：`GET /evaluation` → `evaluator`（Ragas 优先；未配置时返回版本化黄金集的离线评估并说明原因）。

## 4. 降级策略（产品边界的一部分）

外部依赖全部是可选 adapter，缺失时显式降级而不是失败：

| 依赖 | 已配置 | 未配置 |
| --- | --- | --- |
| Redis / Milvus | `storage.py` 远程 backend | 会话隔离的 InMemory backend |
| OCR / Vision / Embedding / Reranker | `providers.py` 真实 provider | `providers.py` Mock / 规则实现 |
| Ragas | `ragas_adapter.py` | `evaluator.py` 离线黄金集评估 |
| LLM | `llm_client.py`（OpenAI-compatible） | 规则/模板回答 |

provider 状态与降级原因必须在证据和响应中可观测，禁止伪健康状态。远程记忆写失败不再静默：`memory.py` 记录并记录日志，`persist_error` / `persist_status`（`ready` / `queued` / `error`）随记忆状态返回。

## 5. 测试布局

- `tests/unit/services/`：快速隔离单元测试（agent、graph、intent_router、retriever、safety、memory、diagnosis、answer_planner、productization）。
- `tests/integration/api/`：API 合同（test_api、test_contracts、test_documents、test_frontend_route（SPA 路径穿越防护）、test_graph_api（含 resume 404 回归）、test_productization_api（含 ingest 去重/超限回归））。
- `tests/integration/e2e/`：`test_quality_gate_e2e.py` 端到端质量门。
- `pytest.ini`：`pythonpath = .`，`testpaths = tests`，`test_*.py`。

## 6. 验收命令

- 根目录：`./build.ps1`（PowerShell）；`./build.ps1 -SmokeOnline` 需要后端已运行在 `127.0.0.1:8000`。
- `apps/backend/`：`python -m pytest`；`python scripts/build.py`。
- `apps/frontend/`：`npm run check`（= `tsc --noEmit && vite build`）。
- 本地栈：`docker compose up --build`。

## 7. 边界（non-goal）

本地可复现 demo。不做：生产部署、多租户、云运维、真实设备接入、高并发与横向扩展。外部服务缺失时显式降级是产品承诺，不得为了"看起来完整"伪造数据。

## 8. 变更记录

- 2026-09-20 入库解析失败结构化降级：
  - `/ingest` 边界（`app/main.py`）把任意解析器异常（pypdf `PdfReadError`、python-pptx 包错误等非 ValueError/RuntimeError 族）映射为 HTTP 200 + `status: "failed"` + `error` 字段，损坏/空文件不再返回 500；回归测试见 `tests/integration/api/test_productization_api.py`（corrupt/empty PDF、corrupt PPTX 三用例）。
  - 前端 `src/api.ts`：非 2xx 错误优先展示响应体 JSON 的 `detail` 字段，不再把原始 JSON 透传给用户。
  - `docker-compose.yml`：backend 的死配置 `MILVUS_ENABLED`（代码从未读取）替换为真实开关 `MEMORY_REMOTE_ENABLED`，Docker 部署中远程记忆真正生效；backend 增加 `/health` healthcheck，frontend 依赖改为 `service_healthy`，与 redis/milvus 既有模式对齐。
  - 前端视觉主题切换为 Claude 风格暖色调（仅 `src/styles.css`，组件结构不动）：米白底 `#faf9f5`、赤陶强调色 `#c96442`（原蓝色 `--blue/--blue-soft` 更名 `--accent/--accent-soft`）、衬线标题（Source Serif 4 + Noto Serif SC）、暖沙用户气泡、铜色品牌锚点与纯色主按钮、暖色滚动条/选区；语义色（红/黄/绿风险）保持不变。
- 2026-09-19 安全与正确性加固（commit `6263e99` / `2ccab9e` / `72d0ce8`）：
  - SPA 兜底路由 `resolve` + `is_relative_to` 防路径穿越；dist 未构建时 404 而非 500。
  - `resume` 增加会话守卫（`ResumeNotAvailableError` → 404），不再对未知/已结束会话 500。
  - `WindOpsAgent.auto_confirm_high_risk` 改为显式参数；传入 `llm_client` 不再隐式关闭高危确认门。
  - 安全门消费全部证据，不再只看 top-1。
  - `/ingest`：20MB 上限、`run_in_threadpool` 执行、`append_docs` 加锁去重；`IngestionResponse` 新增 `warnings` 字段。
  - 记忆持久化：写失败记录 `persist_error` 并输出 warning 日志；executor 持有独立快照消除竞态。
  - docker-compose：redis/etcd/minio/milvus 持久卷、redis/milvus 端口收敛到 127.0.0.1、milvus healthcheck；`VITE_API_BASE` 通过 frontend build args 进入构建（Dockerfile `ARG/ENV`），backend 处的死配置删除；新增 `apps/frontend/.dockerignore`；vite 死 proxy 移除、preview 端口改为 4173。
  - `requirements.txt` 显式声明 `httpx`。
