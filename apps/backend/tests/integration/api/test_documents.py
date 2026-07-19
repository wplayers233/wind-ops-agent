from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.data.mock_docs import MOCK_DOCS
from app.main import app
from app.schemas import DocumentModel


REQUIRED_FIELDS = {
    "id",
    "title",
    "model",
    "system",
    "component",
    "fault_domain",
    "alarm_code",
    "doc_type",
    "doc_type_code",
    "content_type",
    "content",
    "ocr_text",
    "visual_caption",
    "source",
    "page",
    "symptoms",
    "causes",
    "steps",
    "tools",
    "spare_parts",
    "safety_level",
}
REQUIRED_SCENARIOS = {
    "communication_fault",
    "over_temperature",
    "overload",
    "over_voltage",
    "electrical_risk",
}
ALLOWED_CONTENT_TYPES = {"text", "diagram", "slide", "image"}
ALLOWED_SAFETY_LEVELS = {"low", "medium", "high"}


def test_all_documents_validate_with_document_model() -> None:
    for doc in MOCK_DOCS:
        validated = DocumentModel.model_validate(doc)
        assert validated.id == doc["id"]
        assert REQUIRED_FIELDS.issubset(validated.model_dump().keys())


def test_document_ids_are_unique_and_non_empty() -> None:
    ids = [DocumentModel.model_validate(doc).id for doc in MOCK_DOCS]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_risk_levels_and_content_types_are_allowed() -> None:
    for doc in MOCK_DOCS:
        validated = DocumentModel.model_validate(doc)
        assert validated.safety_level in ALLOWED_SAFETY_LEVELS
        assert validated.content_type in ALLOWED_CONTENT_TYPES


def test_required_domain_scenarios_are_covered() -> None:
    fault_domains = {DocumentModel.model_validate(doc).fault_domain for doc in MOCK_DOCS}
    assert REQUIRED_SCENARIOS.issubset(fault_domains)


def test_content_type_and_doc_type_coverage() -> None:
    validated_docs = [DocumentModel.model_validate(doc) for doc in MOCK_DOCS]
    assert len({doc.content_type for doc in validated_docs}) >= 3
    assert len({doc.doc_type_code for doc in validated_docs}) >= 3


def test_docs_endpoint_returns_count_and_complete_serialized_items() -> None:
    response = TestClient(app).get("/docs")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(MOCK_DOCS)
    assert body["count"] == len(body["items"])
    for item in body["items"]:
        assert REQUIRED_FIELDS.issubset(item.keys())
        assert item["source"]
        assert item["page"] >= 1
        assert item["ocr_text"] or item["visual_caption"]


def test_page_zero_fails_document_validation() -> None:
    doc = deepcopy(MOCK_DOCS[0])
    doc["page"] = 0
    with pytest.raises(ValidationError):
        DocumentModel.model_validate(doc)
