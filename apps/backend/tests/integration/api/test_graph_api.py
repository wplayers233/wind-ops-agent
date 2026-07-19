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
