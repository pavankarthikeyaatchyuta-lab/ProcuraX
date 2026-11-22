import pytest
from decimal import Decimal
from datetime import date, timedelta
from app.models import (
    Business,
    Product,
    Supplier,
    Quote,
    Transaction,
    Line,
    UnmetDemandRequest,
    LocalMarketSignal,
)
from app.domain import (
    profit_leak_analysis,
    local_demand_analysis,
    ai_assistant_query,
    unified_decision_summary,
)
from app.db import today

D = Decimal


def test_profit_leak_analysis(setup):
    client, factory, ids = setup
    with factory() as db:
        bid = ids["business"]
        b = db.get(Business, bid)
        p = db.get(Product, ids["product"])
        s = db.get(Supplier, ids["supplier"])

        # Add a cheaper competitor quote to trigger supplier_variance
        s2 = Supplier(business_id=bid, name="Cheaper Supplier", gstin="27AAACS1111A1Z1")
        db.add(s2)
        db.flush()

        q2 = Quote(
            business_id=bid,
            product_id=p.id,
            supplier_id=s2.id,
            unit_cost=D("20.00"),  # cheaper than original quote
            moq=D("10"),
        )
        db.add(q2)

        # Add purchases: older purchase at 20.00, recent purchase at 28.00
        t_old = Transaction(
            business_id=bid,
            source="local",
            source_key="TX-OLD-1",
            kind="purchase",
            supplier_id=s.id,
            date=today() - timedelta(days=20),
            total=D("200.00"),
            active=True,
        )
        t_new = Transaction(
            business_id=bid,
            source="local",
            source_key="TX-NEW-1",
            kind="purchase",
            supplier_id=s.id,
            date=today() - timedelta(days=2),
            total=D("280.00"),
            active=True,
        )
        db.add_all([t_old, t_new])
        db.flush()

        l_old = Line(
            business_id=bid,
            transaction_id=t_old.id,
            product_id=p.id,
            qty=D("10"),
            unit_cost=D("20.00"),
            cash_unit=D("20.00"),
        )
        l_new = Line(
            business_id=bid,
            transaction_id=t_new.id,
            product_id=p.id,
            qty=D("10"),
            unit_cost=D("28.00"),  # +40% cost hike
            cash_unit=D("28.00"),
        )
        db.add_all([l_old, l_new])

        # Selling price was kept at 24.00, below latest purchase cost of 28.00!
        p.sell_price = D("24.00")
        db.commit()

        analysis = profit_leak_analysis(db, b)
        assert "total_monthly_leakage_rupees" in analysis
        assert Decimal(analysis["total_monthly_leakage_rupees"]) > 0
        assert analysis["critical_negative_margin_count"] >= 1
        assert any(l["category"] == "below_cost" for l in analysis["leaks"])


def test_local_demand_analysis(setup):
    client, factory, ids = setup
    with factory() as db:
        bid = ids["business"]
        b = db.get(Business, bid)

        req = UnmetDemandRequest(
            business_id=bid,
            product_name="Almond Milk Sugar Free",
            brand="Raw Pressery",
            category="Dairy Alternatives",
            request_count=7,
            requested_qty=D("14"),
            estimated_sell_price=D("160.00"),
            customer_notes="Vegan customers asked repeatedly",
            status="logged",
        )
        sig = LocalMarketSignal(
            business_id=bid,
            title="Ramzan Roza Demand Surge",
            category="Dairy",
            signal_type="festival",
            source="Local Retailers Association",
            impact_multiplier=D("1.5"),
        )
        db.add_all([req, sig])
        db.commit()

        analysis = local_demand_analysis(db, b)
        assert analysis["unmet_requests_count"] >= 1
        assert len(analysis["opportunities"]) >= 1
        top_opp = analysis["opportunities"][0]
        assert top_opp["product_name"] == "Almond Milk Sugar Free"
        assert top_opp["opportunity_score"] > 50
        assert "local_network" in analysis
        assert (
            analysis["local_network"]["cross_shop_network_status"]
            == "Insufficient local cross-shop data"
        )


def test_ai_assistant_query_multilingual(setup):
    client, factory, ids = setup
    with factory() as db:
        b = db.get(Business, ids["business"])

        # 1. Price hike query in English
        res_en = ai_assistant_query(
            db, b, "Which products had a price increase this month?", language="en"
        )
        assert res_en["language"] == "en"
        assert "evidence" in res_en
        assert "citations" in res_en
        assert res_en["action_link"] == "/intelligence/profit-leaks"

        # 2. Lowest cost supplier in Telugu
        res_te = ai_assistant_query(
            db, b, "తక్కువ ధర ఏ సప్లయర్ ఇస్తున్నారు?", language="te"
        )
        assert res_te["language"] == "te"
        assert "సప్లయర్" in res_te["response"] or "ధర" in res_te["response"]
        assert res_te["action_link"] == "/intelligence/suppliers"

        # 3. Reorder query in Hindi
        res_hi = ai_assistant_query(
            db, b, "आज कौन से उत्पाद दोबारा आर्डर करने हैं?", language="hi"
        )
        assert res_hi["language"] == "hi"
        assert "आर्डर" in res_hi["response"] or "स्टॉक" in res_hi["response"]
        assert res_hi["action_link"] == "/purchasing/planner"


def test_api_endpoints(setup):
    client, factory, ids = setup
    bid = ids["business"]

    # Test GET profit-leaks
    r_leak = client.get(f"/api/v1/businesses/{bid}/profit-leaks")
    assert r_leak.status_code == 200
    assert "total_monthly_leakage_rupees" in r_leak.json()

    # Test GET local-demand
    r_dem = client.get(f"/api/v1/businesses/{bid}/local-demand")
    assert r_dem.status_code == 200
    assert "opportunities" in r_dem.json()

    # Test POST unmet demand request
    r_post_req = client.post(
        f"/api/v1/businesses/{bid}/local-demand/requests",
        json={
            "product_name": "Matcha Tea Powder 100g",
            "category": "Beverages",
            "request_count": 3,
            "requested_qty": "3",
            "estimated_sell_price": "450.00",
            "customer_notes": "Fitness studio members requested",
        },
    )
    assert r_post_req.status_code == 201
    assert r_post_req.json()["product_name"] == "Matcha Tea Powder 100g"

    # Test POST AI assistant ask
    r_ask = client.post(
        f"/api/v1/businesses/{bid}/assistant/ask",
        json={"query": "Which products should I reorder today?", "language": "en"},
    )
    assert r_ask.status_code == 200
    assert "response" in r_ask.json()
    assert len(r_ask.json()["citations"]) > 0

    # Test GET unified decision engine
    r_dec = client.get(f"/api/v1/businesses/{bid}/decision-engine?budget=20000")
    assert r_dec.status_code == 200
    assert "negotiation_insights" in r_dec.json()
