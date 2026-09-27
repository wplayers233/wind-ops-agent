from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import (
    ChatRequest,
    ChatResponse,
    ChatResumeRequest,
    ConversationsResponse,
    DocsCatalogResponse,
    DocumentModel,
    EvaluationResponse,
    HealthResponse,
    IngestionResponse,
    MetricsResponse,
    RetrieveRequest,
    RetrieveResponse,
    TicketRequest,
    TicketResponse,
)
from app.services.agent import agent
from app.services.conversations import CONVERSATIONS
from app.services.corpus import build_ingestion_report, parse_binary
from app.services.evaluator import evaluate_dataset
from app.services.graph import ResumeNotAvailableError
from app.services.metrics import get_system_metrics
from app.services.retriever import retriever

app = FastAPI(title="Wind Ops Agent", version="0.5.0", docs_url="/api-docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = Path(__file__).resolve().parents[3]
FRONTEND_DIST = ROOT_DIR / "apps" / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


def _conversation_item(item: dict) -> dict:
    meta = item.get("meta")
    return {"id": item["id"], "title": item["title"], "meta": meta if isinstance(meta, dict) else {"label": str(meta or "")}}


def _retrieve_item(item) -> dict:
    doc = item.doc
    return {
        "id": doc["id"],
        "title": doc["title"],
        "component": doc["component"],
        "doc_type": doc["doc_type"],
        "content_type": doc["content_type"],
        "source": doc["source"],
        "page": doc["page"],
        "score": round(item.score, 2),
        "trace": item.trace,
        "ocr_text": doc["ocr_text"],
        "visual_caption": doc["visual_caption"],
        "symptoms": doc["symptoms"],
        "causes": doc["causes"],
        "steps": doc["steps"],
        "safety_level": doc.get("safety_level", "low"),
        "regions": doc.get("regions", []),
        "matched_modalities": item.trace.get("matched_modalities", []),
        "multimodal_refs": doc.get("multimodal_refs", []),
    }


def _ingestion_payload(filename: str, status: str, report: dict, error: str = "", warnings: list[str] | None = None) -> dict:
    payload = {
        "filename": filename,
        "status": status,
        "document_count": report.get("document_count", 0),
        "page_count": report.get("page_count", 0),
        "chunk_count": report.get("chunk_count", 0),
        "provider_mode": report.get("provider_mode", "unavailable"),
        "region_count": report.get("region_count", 0),
        "image_count": report.get("image_count", 0),
        "ocr_status": report.get("ocr_status", []),
        "vision_status": report.get("vision_status", []),
        "embedding_status": report.get("embedding_status", ""),
        "warnings": warnings or [],
    }
    if error:
        payload["error"] = error
    return payload


@app.get("/health", response_model=HealthResponse)
def health() -> dict:
    return {"status": "ok", "service": "wind-ops-agent", "version": app.version}


@app.get("/metrics", response_model=MetricsResponse)
def metrics() -> dict:
    return get_system_metrics()


@app.get("/conversations", response_model=ConversationsResponse)
def conversations() -> dict:
    return {"items": [_conversation_item(item) for item in CONVERSATIONS]}


@app.get("/docs", response_model=DocsCatalogResponse)
def docs_catalog() -> dict:
    return {"count": len(retriever.docs), "items": retriever.docs}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> dict:
    return agent.chat(payload.session_id, payload.query)


@app.post("/chat/{session_id}/resume", response_model=ChatResponse)
def resume_chat(session_id: str, payload: ChatResumeRequest) -> dict:
    try:
        return agent.resume(session_id, payload.confirmed)
    except ResumeNotAvailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(payload: RetrieveRequest) -> dict:
    return {"query": payload.query, "top_k": payload.top_k, "results": [_retrieve_item(item) for item in retriever.retrieve(payload.query, payload.top_k, filters=payload.filters, distance_threshold=payload.distance_threshold)]}


MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _process_ingestion(data: bytes, filename: str, suffix: str) -> dict:
    documents = (
        [{"id": Path(filename).stem, "title": filename, "content": data.decode("utf-8", errors="replace"), "source": filename, "page": 1, "content_type": "text"}]
        if suffix in {".txt", ".md"}
        else parse_binary(data, filename, suffix)
    )
    report = build_ingestion_report(documents, provider_mode="auto")
    validated: list[DocumentModel] = []
    warnings: list[str] = []
    for document in documents:
        item = {"id": document.get("id") or f"{Path(filename).stem}-1", "title": document.get("title") or filename, "source": document.get("source", filename), "page": document.get("page", 1), **document}
        try:
            validated.append(DocumentModel.model_validate(item))
        except Exception as exc:
            warnings.append(f"skip:{item.get('id', 'unknown')}:{exc}")
    normalized = [doc.model_dump() for doc in validated]
    added, duplicate_warnings = retriever.append_docs(normalized)
    warnings.extend(duplicate_warnings)
    return _ingestion_payload(filename, report["status"], report, warnings=warnings)


@app.post("/ingest", response_model=IngestionResponse)
async def ingest(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "upload.bin"
    suffix = Path(filename).suffix.lower()
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return _ingestion_payload(filename, "failed", {}, f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit")
    try:
        # PDF rendering and remote OCR/visions calls are CPU/IO heavy; keep them off the event loop.
        return await run_in_threadpool(_process_ingestion, data, filename, suffix)
    except Exception as exc:
        # Parser libraries raise their own exception families (pypdf, python-pptx, ...).
        # The ingest boundary maps every parse failure to the structured failed contract.
        return _ingestion_payload(filename, "failed", {}, str(exc))


@app.get("/evaluation", response_model=EvaluationResponse)
def evaluation() -> dict:
    return evaluate_dataset(retriever)


@app.post("/ticket", response_model=TicketResponse)
def ticket(payload: TicketRequest) -> dict:
    docs = retriever.retrieve(payload.query, 1)
    if payload.component:
        docs = [item for item in docs if item.doc.get("component") == payload.component]
    if not docs or docs[0].score < 8:
        return {"summary": "知识库证据不足，无法生成工单摘要。", "status": "insufficient_evidence", "reference": None}
    doc = docs[0].doc
    return {"summary": f"故障现象：{payload.query}；初判部件：{payload.component or doc['component']}；处理依据：{doc['title']}（{doc['source']} 第{doc['page']}页）。", "status": "ok", "reference": {"title": doc["title"], "source": doc["source"], "page": doc["page"]}}


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_app(full_path: str) -> FileResponse:
    dist_root = FRONTEND_DIST.resolve()
    requested_file = (FRONTEND_DIST / full_path).resolve()
    if full_path and requested_file.is_file() and requested_file.is_relative_to(dist_root):
        return FileResponse(requested_file)
    index_file = dist_root / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="frontend build not found")


