import httpx
from decimal import Decimal
from app.models import Integration, OrderAttempt, Basket
from app.integrations import Zoho, create_drafts
from app.security import encrypt
from app.models import Business, Supplier, Product, Quote
from app.models import Stock
from app.models import Document
from app.integrations import publish_extraction
from app.db import now
from sqlalchemy import select


def test_pagination_token_refresh_and_throttle(monkeypatch):
    monkeypatch.setenv("ZOHO_CLIENT_ID", "test")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "test")
    counts = {"refresh": 0, "get": 0}

    def handler(request):
        if "oauth/v2/token" in str(request.url):
            counts["refresh"] += 1
            return httpx.Response(
                200, json={"access_token": f"token-{counts['refresh']}"}
            )
        counts["get"] += 1
        if counts["get"] == 1:
            return httpx.Response(401)
        if counts["get"] == 2:
            return httpx.Response(429, headers={"Retry-After": "0"})
        page = int(request.url.params.get("page", "1"))
        return httpx.Response(
            200,
            json={
                "code": 0,
                "items": [{"item_id": page}],
                "page_context": {"has_more_page": page == 1},
            },
        )

    integration = Integration(
        business_id="b",
        region="in",
        refresh_token=encrypt("refresh"),
        organization_id="123",
    )
    client = Zoho(integration, transport=httpx.MockTransport(handler))
    try:
        result = client.all("items")
        assert result == [{"item_id": 1}, {"item_id": 2}]
        assert counts["refresh"] == 2
    finally:
        client.close()


def test_ambiguous_write_reconciles_without_second_post(setup, monkeypatch):
    _, factory, ids = setup
    posts = []
    external = []

    class FakeZoho:
        def __init__(self, integration):
            pass

        def close(self):
            pass

        def all(self, resource, params=None):
            return external

        def call(self, method, path, params=None, body=None):
            posts.append(body)
            external.append(
                {
                    "purchaseorder_id": "external-1",
                    "reference_number": body["reference_number"],
                    "status": "draft",
                    "total": 480,
                }
            )
            raise httpx.ReadTimeout("Response lost")

    monkeypatch.setattr("app.integrations.Zoho", FakeZoho)
    with factory() as db:
        b = db.get(Business, ids["business"])
        db.get(Supplier, ids["supplier"]).source_id = "vendor-1"
        db.get(Product, ids["product"]).source_id = "item-1"
        q = db.get(Quote, ids["quote"])
        q.tax_pct = 0
        q.freight_unit = 0
        db.add(
            Integration(business_id=b.id, organization_id="123", refresh_token="unused")
        )
        basket = Basket(
            business_id=b.id,
            budget=2000,
            status="approved",
            lines=[
                {
                    "product_id": ids["product"],
                    "supplier_id": ids["supplier"],
                    "quote_id": ids["quote"],
                    "qty": "24",
                    "cash_spend": "480",
                }
            ],
        )
        db.add(basket)
        db.commit()
        create_drafts(db, b, basket)
        attempt = db.scalar(select(OrderAttempt))
        assert attempt.status == "unknown"
        create_drafts(db, b, basket)
        assert (
            len(posts) == 1
            and attempt.status == "created"
            and attempt.external_id == "external-1"
        )


def test_partial_supplier_failure_never_reposts_successful_draft(setup, monkeypatch):
    _, factory, ids = setup
    posts = []

    class PartialZoho:
        def __init__(self, integration):
            pass

        def close(self):
            pass

        def all(self, resource, params=None):
            return []

        def call(self, method, path, params=None, body=None):
            posts.append(body)
            if len(posts) == 2:
                raise httpx.ReadTimeout("Lost response")
            total = sum(l["quantity"] * l["rate"] for l in body["line_items"])
            return {
                "purchaseorder": {
                    "purchaseorder_id": "first-draft",
                    "status": "draft",
                    "total": total,
                }
            }

    monkeypatch.setattr("app.integrations.Zoho", PartialZoho)
    with factory() as db:
        b = db.get(Business, ids["business"])
        db.get(Supplier, ids["supplier"]).source_id = "first-vendor"
        db.get(Product, ids["product"]).source_id = "first-item"
        first_quote = db.get(Quote, ids["quote"])
        first_quote.tax_pct = 0
        first_quote.freight_unit = 0
        s = Supplier(
            business_id=b.id, name="Second", source_id="second-vendor", minimum_order=0
        )
        p = Product(
            business_id=b.id,
            sku="SECOND",
            name="Second product",
            source_id="second-item",
            sell_price=10,
            manual_demand=3,
        )
        db.add_all([s, p])
        db.flush()
        q = Quote(
            business_id=b.id,
            product_id=p.id,
            supplier_id=s.id,
            unit_cost=5,
            pack=12,
            multiple=12,
            moq=12,
            lead_days=3,
            tiers=[],
        )
        db.add(q)
        db.flush()
        db.add(
            Stock(
                business_id=b.id,
                product_id=p.id,
                on_hand=0,
                reserved=0,
                on_order=0,
                source="count",
            )
        )
        db.add(
            Integration(business_id=b.id, organization_id="123", refresh_token="unused")
        )
        basket = Basket(
            business_id=b.id,
            budget=2000,
            status="approved",
            lines=[
                {
                    "product_id": ids["product"],
                    "supplier_id": ids["supplier"],
                    "quote_id": ids["quote"],
                    "qty": "24",
                    "cash_spend": "480",
                },
                {
                    "product_id": p.id,
                    "supplier_id": s.id,
                    "quote_id": q.id,
                    "qty": "12",
                    "cash_spend": "60",
                },
            ],
        )
        db.add(basket)
        db.commit()
        create_drafts(db, b, basket)
        assert basket.status == "partial"
        attempts = db.scalars(select(OrderAttempt)).all()
        assert sorted(a.status for a in attempts) == ["created", "unknown"]
        create_drafts(db, b, basket)
        assert len(posts) == 2 and basket.status == "partial"


def test_late_ocr_cannot_overwrite_human_verified_document(setup):
    _, factory, ids = setup
    with factory() as db:
        document = Document(
            business_id=ids["business"],
            name="late.pdf",
            sha256="late",
            mime="application/pdf",
            path="none",
            status="queued",
            versions=[],
        )
        db.add(document)
        db.commit()
        did = document.id
    with factory() as stale_worker:
        stale = stale_worker.get(Document, did)
        with factory() as reviewer:
            reviewed = reviewer.get(Document, did)
            reviewed.status = "verified"
            reviewed.version = 2
            reviewed.extracted = {"human": "verified"}
            reviewer.commit()
        assert not publish_extraction(stale_worker, stale, {"machine": "late result"})
        stale_worker.commit()
    with factory() as db:
        reviewed = db.get(Document, did)
        assert (
            reviewed.status == "verified"
            and reviewed.version == 2
            and reviewed.extracted == {"human": "verified"}
        )
