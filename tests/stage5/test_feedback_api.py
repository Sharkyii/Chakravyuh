import pytest
from web.api import analyze, submit_feedback, FEEDBACK_STORE, DYNAMIC_METRICS, _SESSION_GRAPHS
from stage5.config.settings import MODELS_DIR

# stage5/models/*.pkl are gitignored and aren't trained in CI.
requires_trained_models = pytest.mark.skipif(
    not (MODELS_DIR / "fraud_model.pkl").exists(),
    reason="trained model artifacts not present (not generated in CI)",
)


class MockRequest:
    def __init__(self, data: dict):
        self._data = data

    async def json(self):
        return self._data


@pytest.mark.anyio
async def test_feedback_api_agreement():
    # Clear feedback store
    FEEDBACK_STORE.clear()

    # Reset metrics
    DYNAMIC_METRICS["PR-AUC"] = 0.9866

    # Submit legitimate feedback where score implies legitimate
    req = MockRequest({"txn_id": "test-txn-123", "actual_label": "legitimate", "risk_score": 25.0})

    data = await submit_feedback(req)

    assert data["status"] == "success"
    assert data["feedback_count"] == 1
    assert data["metrics"]["PR-AUC"] > 0.9866
    assert len(FEEDBACK_STORE) == 1


@pytest.mark.anyio
async def test_feedback_api_disagreement():
    # Clear feedback store
    FEEDBACK_STORE.clear()

    # Reset metrics
    DYNAMIC_METRICS["PR-AUC"] = 0.9866

    # Submit legitimate feedback where score implies fraud
    req = MockRequest({"txn_id": "test-txn-123", "actual_label": "legitimate", "risk_score": 85.0})

    data = await submit_feedback(req)

    assert data["status"] == "success"
    assert data["metrics"]["PR-AUC"] < 0.9866


@pytest.mark.anyio
async def test_feedback_api_invalid_request():
    from fastapi import HTTPException

    req = MockRequest({"txn_id": "test-txn-123"})
    with pytest.raises(HTTPException) as exc_info:
        await submit_feedback(req)
    assert exc_info.value.status_code == 400


@requires_trained_models
@pytest.mark.anyio
async def test_analyze_injects_graph():
    # Clear session transactions
    _SESSION_GRAPHS.clear()

    # Submit mock transaction
    mock_txn = {
        "amount": 12500.0,
        "edge_count": 4.0,
        "pin_attempts": 1,
        "beneficiary_added_ago_s": 86400 * 2,
        "payer_id": "payer-abc",
        "payee_id": "payee-xyz",
        "rail": "upi_p2p",
        "txn_id": "TXN_001",
    }

    req = MockRequest({"transaction": mock_txn})

    data = await analyze(req)
    assert "network_graph" in data
    graph = data["network_graph"]
    assert len(graph["nodes"]) >= 2
    assert len(graph["edges"]) >= 1

    # Verify node details with session suffixes
    payer_node = next(n for n in graph["nodes"] if n["id"] == "payer_TXN_001")
    assert payer_node["label"] == "Payer (TXN_001)"

    payee_node = next(n for n in graph["nodes"] if n["id"] == "payee_TXN_001")
    assert payee_node["label"] == "Payee (TXN_001)"


class MockRequestWithHeaders(MockRequest):
    def __init__(self, data: dict, headers: dict):
        super().__init__(data)
        self.headers = headers


@requires_trained_models
@pytest.mark.anyio
async def test_analyze_session_isolation():
    _SESSION_GRAPHS.clear()

    mock_txn = {
        "amount": 12500.0,
        "edge_count": 1.0,
        "pin_attempts": 1,
        "rail": "upi_p2p",
    }

    req1 = MockRequestWithHeaders({"transaction": mock_txn}, {"x-session-id": "sess1"})
    req2 = MockRequestWithHeaders({"transaction": mock_txn}, {"x-session-id": "sess2"})

    data1 = await analyze(req1)
    data2 = await analyze(req2)

    nodes1 = data1["network_graph"]["nodes"]
    nodes2 = data2["network_graph"]["nodes"]

    # Each should have only 2 nodes (payer and payee) from one transaction
    # Without isolation, the second request would return graph data for both transactions (4+ nodes)
    assert len(nodes1) == 2
    assert len(nodes2) == 2
