from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import AfterValidator
from typing_extensions import Annotated

def _strip_non_empty(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty")
    return stripped

NonEmptyStr = Annotated[str, AfterValidator(_strip_non_empty)]

class EvidenceRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    modality: Literal["text", "ocr", "image", "diagram", "table", "slide"]
    text: str = ""
    caption: str = ""
    page: int = Field(ge=1)
    source: str
    bbox: tuple[float, float, float, float] | None = None
    parent_id: str | None = None
    score: float = 0.0

class MultimodalDocument(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: NonEmptyStr
    title: NonEmptyStr
    model: str = "unknown"
    system: str = "unknown"
    component: str = "unknown"
    fault_domain: str = "unknown"
    alarm_code: str = ""
    doc_type: str = "unknown"
    doc_type_code: str = "unknown"
    content_type: Literal["text", "diagram", "slide", "image", "ocr"] = "text"
    content: str = ""
    ocr_text: str = ""
    visual_caption: str = ""
    source: NonEmptyStr
    page: int = Field(ge=1)
    symptoms: list[str] = Field(default_factory=list)
    causes: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    spare_parts: list[str] = Field(default_factory=list)
    safety_level: Literal["low", "medium", "high"] = "low"
    regions: list[EvidenceRegion] = Field(default_factory=list)
    vector_ids: list[str] = Field(default_factory=list)
    multimodal_refs: list[str] = Field(default_factory=list)

class DocumentModel(MultimodalDocument):
    pass

class ChatRequest(BaseModel):
    session_id: str = Field(default="default")
    query: NonEmptyStr

class RetrieveRequest(BaseModel):
    query: NonEmptyStr
    top_k: int = Field(default=5, ge=1, le=10)
    filters: dict[str, str | list[str]] = Field(default_factory=dict)
    distance_threshold: float | None = Field(default=None, ge=0.0, le=2.0)

class ChatResumeRequest(BaseModel):
    confirmed: bool

class TicketRequest(BaseModel):
    query: NonEmptyStr
    component: str | None = None

class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    query: str
    answer: str
    intent: dict[str, Any]
    intent_analysis: dict[str, Any]
    diagnosis_result: dict[str, Any]
    confidence: float = 0.0
    risk_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    safety_notice: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_trace: dict[str, Any] = Field(default_factory=dict)
    ticket_summary: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    memory_summary: str = ""
    llm_used: bool = False

class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str

class MetricsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    service_status: str
    pipeline_status: str
    context_precision: float
    context_recall: float
    faithfulness: float
    response_relevancy: float
    session_id: str

class ConversationItem(BaseModel):
    id: str
    title: str
    meta: str | dict[str, Any]

class ConversationsResponse(BaseModel):
    items: list[ConversationItem]

class DocsCatalogResponse(BaseModel):
    count: int
    items: list[DocumentModel]

class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    title: str
    component: str
    doc_type: str
    content_type: str
    source: str
    page: int
    score: float
    trace: dict[str, Any]
    ocr_text: str = ""
    visual_caption: str = ""
    symptoms: list[str] = Field(default_factory=list)
    causes: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    safety_level: str = "low"
    regions: list[EvidenceRegion] = Field(default_factory=list)
    matched_modalities: list[str] = Field(default_factory=list)
    multimodal_refs: list[str] = Field(default_factory=list)

class RetrieveResponse(BaseModel):
    query: str
    top_k: int
    results: list[RetrievalResult]

class IngestionResponse(BaseModel):
    filename: str
    status: str
    document_count: int
    page_count: int
    chunk_count: int
    provider_mode: str
    region_count: int = 0
    image_count: int = 0
    ocr_status: list[str] = Field(default_factory=list)
    vision_status: list[str] = Field(default_factory=list)
    embedding_status: str = ""
    error: str = ""

class EvaluationResponse(BaseModel):
    dataset_version: str
    sample_count: int
    metrics: dict[str, float]
    baseline: dict[str, float]
    metrics_kind: str
    metrics_note: str
    provider_status: str = "offline_fallback"
    fallback_reason: str = ""

class TicketReference(BaseModel):
    title: str
    source: str
    page: int

class TicketResponse(BaseModel):
    summary: str
    status: Literal["ok", "insufficient_evidence"]
    reference: TicketReference | None = None