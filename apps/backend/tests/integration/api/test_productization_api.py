import io

from fastapi.testclient import TestClient

from app.main import app
from app.services.experiment import TaskMeasurement, summarize_measurements
from app.services.providers import HashEmbeddingProvider, MockOCRProvider


def test_ingest_text_file_returns_chunk_report():
    response = TestClient(app).post('/ingest', files={'file': ('sample.txt', b'gearbox oil temperature high', 'text/plain')})
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ready'
    assert body['chunk_count'] >= 1


def test_ingest_unsupported_file_is_explicit():
    response = TestClient(app).post('/ingest', files={'file': ('sample.zip', b'bad', 'application/zip')})
    assert response.status_code == 200
    assert response.json()['status'] == 'failed'


def test_provider_contracts_return_mode_and_latency():
    ocr = MockOCRProvider().parse_page(b'page')
    embedding = HashEmbeddingProvider().embed(['变桨通讯中断'])
    assert ocr.status == 'mock'
    assert embedding.status == 'ok'
    assert embedding.payload['vectors']
    assert embedding.provider == 'hash_embedding'


def test_experiment_summary_separates_baseline_and_system():
    result = summarize_measurements([
        TaskMeasurement('1', 'baseline', 42, True, True),
        TaskMeasurement('2', 'system', 11, True, False),
    ])
    assert result['experiment_kind'] == 'internal_simulation'
    assert result['groups']['baseline']['mean_resolution_minutes'] == 42
    assert result['groups']['system']['self_service_rate'] == 1.0
