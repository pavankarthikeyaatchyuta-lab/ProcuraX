from decimal import Decimal
from app.models import Business, Product, Supplier, Stock, Transaction, UnmetDemandRequest
from app.domain import (
    profit_leak_analysis,
    local_demand_analysis,
    ai_assistant_query,
    unified_decision_summary,
)


def test_zero_data_domain_safety(setup):
    client, factory, ids = setup
    with factory() as db:
        # Create an isolated brand new business with 0 products, 0 sales, 0 demand
        b = Business(name="Pristine Empty Store")
        db.add(b)
        db.commit()
        db.refresh(b)

        # 1. Profit leak analysis on empty store
        leaks = profit_leak_analysis(db, b)
        assert leaks["total_monthly_leakage_rupees"] == "0.00"
        assert leaks["leaks"] == []

        # 2. Local demand analysis on empty store
        demand = local_demand_analysis(db, b)
        assert demand["unmet_requests_count"] == 0
        assert demand["opportunities"] == []
        assert "insufficient" in demand["local_network"]["cross_shop_network_status"].lower()

        # 3. AI assistant on empty store
        answer = ai_assistant_query(db, b, "What is selling the fastest?", "en")
        assert len(answer["response"]) > 0

        # 4. Decision engine on empty store
        decision = unified_decision_summary(db, b, Decimal("10000"))
        assert decision["recommended_lines_count"] == 0
        assert decision["running_low_count"] == 0


def test_clean_slate_reset_api(setup):
    client, factory, ids = setup
    business_id = ids["business"]

    # First add a customer demand request
    resp = client.post(
        f"/api/v1/businesses/{business_id}/local-demand/requests",
        json={
            "product_name": "Temporary Test Item",
            "request_count": 5,
            "category": "Snacks",
            "status": "logged",
        },
    )
    assert resp.status_code == 201

    # Call reset data endpoint
    reset_resp = client.post(
        f"/api/v1/businesses/{business_id}/reset-data",
        params={"wipe_catalog": False},
    )
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "success"

    # Verify demand requests were purged
    with factory() as db:
        unmet = db.query(UnmetDemandRequest).filter(UnmetDemandRequest.business_id == business_id).all()
        assert len(unmet) == 0


def test_websocket_connection_and_handshake(setup):
    client, factory, ids = setup
    business_id = ids["business"]

    with client.websocket_connect(f"/api/v1/ws/{business_id}") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "SYSTEM_STATUS"
        assert data["title"] == "Real-Time Connected"

        # Send ping
        websocket.send_text("ping")
        pong = websocket.receive_text()
        assert pong == "pong"
