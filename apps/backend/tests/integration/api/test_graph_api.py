from fastapi.testclient import TestClient

from app.main import app


def test_resume_endpoint_continues_graph_after_safety_confirmation():
    client = TestClient(app)
    pending = client.post('/chat', json={'session_id': 'api-graph-risk', 'query': '2.5MW 变桨系统通讯中断，报 PITCH_COMM_LOST，怎么排查？'}).json()
    assert pending['status'] == 'awaiting_confirmation'
    resumed = client.post('/chat/api-graph-risk/resume', json={'confirmed': True})
    assert resumed.status_code == 200
    body = resumed.json()
    assert body['status'] == 'completed'
    assert body['evidence']
    assert body['diagnosis_result']['citations']


def test_resume_unknown_session_returns_404():
    client = TestClient(app)
    response = client.post('/chat/no-such-session/resume', json={'confirmed': True})
    assert response.status_code == 404


def test_resume_finished_session_returns_404():
    client = TestClient(app)
    finished = client.post('/chat', json={'session_id': 'api-graph-lowrisk', 'query': '齿轮箱油温高怎么办？'}).json()
    # Any terminal state (completed / needs_clarification) leaves no pending interrupt to resume.
    assert finished['status'] in {'completed', 'needs_clarification'}
    response = client.post('/chat/api-graph-lowrisk/resume', json={'confirmed': True})
    assert response.status_code == 404
