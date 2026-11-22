from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.models import *
from app.domain import (
    costs,
    recommend,
    validate_basket,
    forecast_values,
    inventory,
    matching,
)
from app.imports import post_transaction, commit_import
from app.schemas import PurchaseLine
from app.db import now
import pytest


def url(ids, path):
    return f"/api/v1/businesses/{ids['business']}{path}"


def test_auth_tenant_csrf_and_permissions(setup):
    client, factory, ids = setup
    assert client.get(f"/api/v1/businesses/{ids['other']}/products").status_code == 404
    csrf = client.headers.pop("x-csrf-token")
    assert client.post(url(ids, "/baskets"), json={"budget": 1000}).status_code == 403
    client.headers["x-csrf-token"] = csrf
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "review@test.local", "password": "review-test-password"},
    )
    client.headers["x-csrf-token"] = r.json()["csrf"]
    assert client.post(url(ids, "/baskets"), json={"budget": 1000}).status_code == 403
    assert client.get(url(ids, "/products")).status_code == 200


def test_real_owner_requires_mfa(setup):
    client, factory, ids = setup
    with factory() as db:
        db.get(Business, ids["business"]).demo = False
        db.commit()
    assert client.post(url(ids, "/baskets"), json={"budget": 1000}).status_code == 403
    r = client.post("/api/v1/auth/mfa/setup")
    assert r.status_code == 200
    import pyotp

    code = pyotp.TOTP(r.json()["secret"]).now()
    assert (
        client.post("/api/v1/auth/mfa/verify", json={"code": code}).status_code == 200
    )
    assert client.post(url(ids, "/baskets"), json={"budget": 1000}).status_code == 201


def test_decimal_cost_pack_and_budget(setup):
    _, factory, ids = setup
    with factory() as db:
        b = db.get(Business, ids["business"])
        q = db.get(Quote, ids["quote"])
        assert costs(q, Decimal(24), True) == (Decimal(21), Decimal(22))
        assert costs(q, Decimal(24), False) == (Decimal(22), Decimal(22))
        lines, snapshot = recommend(db, b, Decimal(1100))
        assert len(lines) == 1 and Decimal(lines[0]["qty"]) == 48
        assert Decimal(lines[0]["cash_spend"]) == 1056
        assert validate_basket(db, b, [dict(lines[0], qty="25")], Decimal(1100))[2]
        assert validate_basket(db, b, [dict(lines[0], qty="60")], Decimal(1100))[2] == [
            "Cash budget exceeded"
        ]


def test_supplier_minimum_and_cover(setup):
    _, factory, ids = setup
    with factory() as db:
        b = db.get(Business, ids["business"])
        s = db.get(Supplier, ids["supplier"])
        s.minimum_order = 5000
        db.flush()
        lines, snapshot = recommend(db, b, Decimal(2000))
        assert not lines
        assert any("minimum" in e["reason"] for e in snapshot["excluded"])
        db.get(Product, ids["product"]).storage_limit = 20
        s.minimum_order = 0
        db.flush()
        assert not recommend(db, b, Decimal(2000))[0]


def test_invoice_verify_duplicate_and_optimistic_lock(setup):
    client, factory, ids = setup
    with factory() as db:
        d = Document(
            business_id=ids["business"],
            name="invoice.json",
            sha256="hash1",
            mime="application/json",
            path="no-file",
            status="review",
            extracted={},
            versions=[],
        )
        d2 = Document(
            business_id=ids["business"],
            name="same.pdf",
            sha256="hash2",
            mime="application/pdf",
            path="no-file",
            status="review",
            extracted={},
            versions=[],
        )
        db.add_all([d, d2])
        db.commit()
        did, did2 = d.id, d2.id
    body = {
        "version": 1,
        "supplier_id": ids["supplier"],
        "invoice_no": "INV-1",
        "date": date.today().isoformat(),
        "total": "252",
        "lines": [
            {
                "product_id": ids["product"],
                "qty": 1,
                "factor": 12,
                "rate": 240,
                "tax_pct": 5,
            }
        ],
    }
    assert (
        client.post(url(ids, f"/documents/{did}/verify"), json=body).status_code == 200
    )
    assert (
        client.post(url(ids, f"/documents/{did}/verify"), json=body).status_code == 409
    )
    assert (
        client.post(url(ids, f"/documents/{did2}/verify"), json=body).status_code == 200
    )
    with factory() as db:
        assert len(db.scalars(select(Transaction)).all()) == 1
        assert (
            inventory(db, db.get(Business, ids["business"]))[0]["on_hand"] == "24.0000"
        )
        assert len(db.scalars(select(Line)).all()) == 1


def test_bad_invoice_does_not_change_stock(setup):
    client, factory, ids = setup
    with factory() as db:
        d = Document(
            business_id=ids["business"],
            name="x.json",
            sha256="x",
            mime="application/json",
            path="x",
            status="review",
        )
        db.add(d)
        db.commit()
        did = d.id
    response = client.post(
        url(ids, f"/documents/{did}/verify"),
        json={
            "version": 1,
            "supplier_id": ids["supplier"],
            "invoice_no": "I",
            "date": date.today().isoformat(),
            "total": 99,
            "lines": [{"product_id": ids["product"], "qty": 1, "rate": 10}],
        },
    )
    assert response.status_code == 422
    with factory() as db:
        assert db.get(Document, did).status == "review"


def test_zoho_mirror_never_double_posts_stock(setup):
    _, factory, ids = setup
    with factory() as db:
        b = db.get(Business, ids["business"])
        b.mode = "zoho"
        db.flush()
        post_transaction(
            db,
            b,
            source="document",
            source_key="abc",
            kind="purchase",
            invoice_no="Z1",
            occurred=date.today(),
            supplier_id=ids["supplier"],
            total=100,
            lines=[PurchaseLine(product_id=ids["product"], qty=5, rate=20)],
            raw={},
            actor="test",
        )
        db.commit()
        assert len(db.scalars(select(Movement)).all()) == 1
        assert Decimal(inventory(db, b)[0]["on_hand"]) == 12
        b.mode = "standalone"
        db.flush()
        post_transaction(
            db,
            b,
            source="zoho",
            source_key="bill:Z2",
            kind="purchase",
            invoice_no="Z2",
            occurred=date.today(),
            supplier_id=ids["supplier"],
            total=100,
            lines=[PurchaseLine(product_id=ids["product"], qty=5, rate=20)],
            raw={},
            actor="test",
        )
        db.commit()
        assert len(db.scalars(select(Movement)).all()) == 1


def test_basket_concurrency_confirmation_and_stale_stock(setup):
    client, factory, ids = setup
    b = client.post(url(ids, "/baskets"), json={"budget": 2000}).json()
    bid = b["id"]
    assert (
        client.post(
            url(ids, f"/baskets/{bid}/approve"),
            json={"version": 1, "action": "approve"},
        ).status_code
        == 422
    )
    line = b["lines"][0]
    edit = {
        "version": 1,
        "lines": [
            {"quote_id": line["quote_id"], "qty": line["qty"], "price_confirmed": True}
        ],
    }
    assert client.put(url(ids, f"/baskets/{bid}"), json=edit).status_code == 200
    assert client.put(url(ids, f"/baskets/{bid}"), json=edit).status_code == 409
    with factory() as db:
        for s in db.scalars(select(Stock)):
            s.at = now() - timedelta(days=2)
        for m in db.scalars(select(Movement)):
            m.at = now() - timedelta(days=2)
        db.commit()
    assert (
        client.post(
            url(ids, f"/baskets/{bid}/approve"),
            json={"version": 2, "action": "approve"},
        ).status_code
        == 422
    )


def test_movement_reversal_and_returns(setup):
    client, factory, ids = setup
    with factory() as db:
        mid = db.scalar(select(Movement)).id
    body = {"product_id": ids["product"], "qty": 15, "reason": "Correct opening count"}
    assert (
        client.post(url(ids, f"/movements/{mid}/reverse"), json=body).status_code == 200
    )
    assert (
        client.post(url(ids, f"/movements/{mid}/reverse"), json=body).status_code == 409
    )
    with factory() as db:
        b = db.get(Business, ids["business"])
        for kind in ["sale", "purchase", "customer_return", "supplier_return"]:
            post_transaction(
                db,
                b,
                source="test",
                source_key=kind,
                kind=kind,
                invoice_no=kind,
                occurred=date.today(),
                supplier_id=ids["supplier"],
                total=40,
                lines=[PurchaseLine(product_id=ids["product"], qty=2, rate=20)],
                raw={},
                actor="test",
            )
        db.commit()
        assert Decimal(inventory(db, b)[0]["on_hand"]) == 15


def test_atomic_import_and_idempotency(setup):
    client, factory, ids = setup
    with factory() as db:
        job = Job(
            business_id=ids["business"],
            kind="import",
            status="preview",
            payload={
                "import_kind": "products",
                "rows": [
                    {"sku": "NEW", "name": "New product"},
                    {"sku": "", "name": "Bad product"},
                ],
            },
        )
        db.add(job)
        db.commit()
        jid = job.id
    mapping = {"mapping": {"sku": "sku", "name": "name"}}
    assert (
        client.post(url(ids, f"/imports/{jid}/commit"), json=mapping).status_code == 422
    )
    with factory() as db:
        assert not db.scalar(select(Product).where(Product.sku == "NEW"))
        job = db.get(Job, jid)
        job.payload = {
            "import_kind": "products",
            "rows": [{"sku": "NEW", "name": "New product"}],
        }
        db.commit()
    assert (
        client.post(url(ids, f"/imports/{jid}/commit"), json=mapping).status_code == 200
    )
    assert (
        client.post(url(ids, f"/imports/{jid}/commit"), json=mapping).status_code == 200
    )
    with factory() as db:
        assert len(db.scalars(select(Product)).all()) == 2


def test_malicious_and_cross_tenant_uploads(setup, monkeypatch):
    client, _, ids = setup
    monkeypatch.setattr(
        "app.main.scan_file",
        lambda content: (_ for _ in ()).throw(
            ValueError("Upload rejected by malware scanner")
        ),
    )
    r = client.post(
        url(ids, "/documents"),
        files={"file": ("x.pdf", b"%PDF-EICAR", "application/pdf")},
    )
    assert r.status_code == 503
    assert client.get(url(ids, "/documents")).json() == []
    assert (
        client.post(
            "/api/v1/businesses/" + ids["other"] + "/documents",
            files={"file": ("x.json", b"{}", "application/json")},
        ).status_code
        == 404
    )


def test_forecasting_sparse_and_no_future_leakage(setup):
    _, factory, ids = setup
    assert forecast_values([0, 0, 4, 0, 0, 4], "croston_sba") == pytest.approx(
        1.26666667
    )
    from app.domain import forecasts

    with factory() as db:
        b = db.get(Business, ids["business"])
        p = db.get(Product, ids["product"])
        p.manual_demand = None
        db.flush()
        assert forecasts(db, b)[0]["eligible"] is False
        for day in range(60, 0, -1):
            t = Transaction(
                business_id=b.id,
                source="test",
                source_key=str(day),
                kind="sale",
                invoice_no=str(day),
                date=date.today() - timedelta(days=day),
                total=20,
                raw={},
            )
            db.add(t)
            db.flush()
            db.add(
                Line(
                    business_id=b.id,
                    transaction_id=t.id,
                    product_id=p.id,
                    qty=1,
                    unit_cost=20,
                    cash_unit=20,
                    discount=0,
                    raw={},
                )
            )
        db.flush()
        before = forecasts(db, b)[0]
        t = Transaction(
            business_id=b.id,
            source="test",
            source_key="future",
            kind="sale",
            invoice_no="future",
            date=date.today() + timedelta(days=1),
            total=1,
            raw={},
        )
        db.add(t)
        db.flush()
        db.add(
            Line(
                business_id=b.id,
                transaction_id=t.id,
                product_id=p.id,
                qty=99999,
                unit_cost=1,
                cash_unit=1,
                discount=0,
                raw={},
            )
        )
        db.flush()
        after = forecasts(db, b)[0]
        assert before == after and after["daily_demand"] == "1.0"


def test_privacy_export_excludes_credentials(setup):
    client, factory, ids = setup
    with factory() as db:
        db.add(
            Integration(business_id=ids["business"], refresh_token="sensitive-secret")
        )
        db.commit()
    r = client.get(url(ids, "/export"))
    assert r.status_code == 200
    assert "sensitive-secret" not in r.text and "password" not in r.text


def test_foreign_quote_and_mapping_rejected(setup):
    client, factory, ids = setup
    with factory() as db:
        p = Product(business_id=ids["other"], sku="FOREIGN", name="Other")
        db.add(p)
        db.commit()
        pid = p.id
    assert (
        client.post(
            url(ids, "/quotes"),
            json={"product_id": pid, "supplier_id": ids["supplier"], "unit_cost": 1},
        ).status_code
        == 404
    )
    assert (
        client.post(
            url(ids, "/aliases"), json={"product_id": pid, "text": "wrong"}
        ).status_code
        == 404
    )


def test_mode_switch_requires_all_reconciled_openings(setup):
    client, _, ids = setup
    assert (
        client.post(
            url(ids, "/inventory/authority"),
            json={
                "version": 1,
                "mode": "zoho",
                "reason": "Migration",
                "opening": [
                    {"product_id": ids["product"], "qty": 12, "reason": "Reconciled"}
                ],
            },
        ).status_code
        == 409
    )


def test_verified_invoice_correction_preserves_evidence_and_reverses_stock(setup):
    client, factory, ids = setup
    with factory() as db:
        d = Document(
            business_id=ids["business"],
            name="correct.json",
            sha256="correct",
            mime="application/json",
            path="none",
            status="review",
            versions=[],
        )
        db.add(d)
        db.commit()
        did = d.id
    body = {
        "version": 1,
        "supplier_id": ids["supplier"],
        "invoice_no": "COR-1",
        "date": date.today().isoformat(),
        "total": 40,
        "lines": [{"product_id": ids["product"], "qty": 2, "rate": 20}],
    }
    assert (
        client.post(url(ids, f"/documents/{did}/verify"), json=body).status_code == 200
    )
    body.update(
        version=2,
        total=60,
        lines=[{"product_id": ids["product"], "qty": 3, "rate": 20}],
    )
    assert (
        client.post(url(ids, f"/documents/{did}/correct"), json=body).status_code == 200
    )
    with factory() as db:
        assert (
            Decimal(inventory(db, db.get(Business, ids["business"]))[0]["on_hand"])
            == 15
        )
        transactions = db.scalars(select(Transaction)).all()
        assert len(transactions) == 2 and sum(t.active for t in transactions) == 1
        assert len(db.scalars(select(Line)).all()) == 2
        assert len(db.get(Document, did).versions) == 2


def test_mfa_enrollment_does_not_upgrade_other_sessions(setup):
    client, factory, ids = setup
    earlier_cookie = client.cookies.get("procure_session")
    earlier_csrf = client.headers["x-csrf-token"]
    other = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@test.local", "password": "correct-test-password"},
    )
    old_cookie = client.cookies.get("procure_session")
    old_csrf = other.json()["csrf"]
    client.headers["x-csrf-token"] = old_csrf
    setup_response = client.post("/api/v1/auth/mfa/setup")
    import pyotp

    code = pyotp.TOTP(setup_response.json()["secret"]).now()
    assert (
        client.post("/api/v1/auth/mfa/verify", json={"code": code}).status_code == 200
    )
    with factory() as db:
        db.get(Business, ids["business"]).demo = False
        earlier = db.scalar(
            select(Session).where(
                Session.user_id == ids["owner"], Session.csrf != old_csrf
            )
        )
        # The earlier login's session is still unverified after a different session enrolls.
        assert not earlier.mfa_verified
        db.commit()
    client.cookies.set(
        "procure_session", earlier_cookie, domain="testserver.local", path="/"
    )
    client.headers["x-csrf-token"] = earlier_csrf
    assert client.post(url(ids, "/baskets"), json={"budget": 1000}).status_code == 403
