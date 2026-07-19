from app.services.agent import WindOpsAgent
from app.services.graph import GraphRunner


def test_graph_greeting_uses_supervisor_and_ends_without_evidence():
    result = WindOpsAgent().chat('graph-health', '系统在吗')
    assert result['intent']['name'] == 'health_check'
    assert result['evidence'] == []
    assert result['status'] == 'completed'
    assert 'WindRAG' in result['answer']


def test_graph_high_risk_interrupts_and_resumes():
    agent = WindOpsAgent()
    pending = agent.chat('graph-risk', '2.5MW 变桨系统通讯中断，报 PITCH_COMM_LOST，怎么排查？')
    assert pending['status'] == 'awaiting_confirmation'
    assert pending['risk_level'] == 'high'
    assert pending['follow_up_questions']

    completed = agent.resume('graph-risk', True)
    assert completed['status'] == 'completed'
    assert completed['evidence']
    assert completed['diagnosis_result']['citations']
    assert completed['risk_level'] == 'high'
    assert completed['llm_used'] is False


def test_graph_unknown_query_requests_clarification_without_fake_citation():
    result = WindOpsAgent().chat('graph-unknown', 'what should I do')
    assert result['status'] == 'needs_clarification'
    assert result['evidence'] == []
    assert result['diagnosis_result']['citations'] == []

