from app.data.mock_docs import MOCK_DOCS
from app.services.corpus import chunk_document
from app.services.hybrid_retrieval import LocalHybridIndex


def test_chunk_document_preserves_source_mapping():
    chunks = chunk_document(MOCK_DOCS[0], chunk_size=80)
    assert chunks
    assert all(item["document_id"] == "doc-001" for item in chunks)
    assert all(item["page"] == 12 for item in chunks)
    assert len({item["id"] for item in chunks}) == len(chunks)


def test_local_hybrid_index_is_deterministic_and_explainable():
    index = LocalHybridIndex(MOCK_DOCS)
    first = index.search("PITCH_COMM_LOST", top_k=2)
    second = index.search("PITCH_COMM_LOST", top_k=2)
    assert [item.document["id"] for item in first] == [item.document["id"] for item in second]
    assert first[0].document["id"] == "doc-001"
    assert first[0].channel == "bm25+hashed_embedding"
