from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select, func
from app.models import *
from app.db import today


def root(ids):
    return f"/api/v1/businesses/{ids['business']}"


def ops(ids, path):
    return root(ids) + "/workspace" + path


def make_order(client, ids, qty=24):
    r = client.post(
        ops(ids, "/orders"),
        json={
            "supplier_id": ids["supplier"],
            "expected": str(today() + timedelta(days=3)),
            "source_key": uuid4().hex,
            "lines": [{"quote_id": ids["quote"], "qty": qty}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def act_order(client, ids, order, action, expected=200):
    current = client.get(ops(ids, "/orders/" + order["id"])).json()
    r = client.post(
        ops(ids, "/orders/" + order["id"] + "/transition"),
        json={
            "version": current["version"],
            "action": action,
            "reason": "Test decision",
        },
    )
    assert r.status_code == expected, r.text
    return client.get(ops(ids, "/orders/" + order["id"])).json()


def placed(client, ids):
    o = make_order(client, ids)
    for action in ("submit", "approve", "ordered"):
        o = act_order(client, ids, o, action)
    return o


def receive(client, ids, o, qty, key=None):
    current = client.get(ops(ids, "/orders/" + o["id"])).json()
    payload = {
        "version": current["version"],
        "idempotency_key": key or uuid4().hex,
        "lines": [
            {"order_line_id": current["lines"][0]["id"], "accepted": qty, "rejected": 0}
        ],
    }
    response = client.post(ops(ids, "/orders/" + o["id"] + "/receive"), json=payload)
    assert response.status_code == 201, response.text
    return payload, response.json()


def invoice(client, factory, ids, qty=24, order_id=None):
    with factory() as db:
        d = Document(
            business_id=ids["business"],
            name="ops.json",
            sha256=uuid4().hex,
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
        "invoice_no": "B-" + uuid4().hex[:8],
        "date": str(today()),
        "total": str(Decimal(qty) * 22),
        "lines": [
            {
                "product_id": ids["product"],
                "qty": qty,
                "rate": 20,
                "tax_pct": 5,
                "freight": qty,
            }
        ],
        "order_id": order_id,
    }
    r = client.post(root(ids) + f"/documents/{did}/verify", json=body)
    assert r.status_code == 200, r.text
    return r.json()["transaction_id"]


def available(client, ids):
    r = client.get(ops(ids, "/inventory"))
    assert r.status_code == 200, r.text
    return Decimal(r.json()[0]["available"])


def test_partial_receiving_order_states_and_idempotency(setup):
    c, f, ids = setup
    o = placed(c, ids)
    assert Decimal(o["total"]) == 528
    payload, receipt = receive(c, ids, o, 12)
    assert available(c, ids) == 24
    assert (
        c.post(ops(ids, "/orders/" + o["id"] + "/receive"), json=payload).status_code
        == 201
    )
    assert available(c, ids) == 24
    current = c.get(ops(ids, "/orders/" + o["id"])).json()
    assert current["status"] == "partially_received"
    receive(c, ids, current, 12)
    assert available(c, ids) == 36
    assert c.get(ops(ids, "/orders/" + o["id"])).json()["status"] == "received"
    assert (
        c.post(
            ops(ids, "/orders/" + o["id"] + "/receive"),
            json=payload
            | {"lines": [{"order_line_id": o["lines"][0]["id"], "accepted": 1}]},
        ).status_code
        == 409
    )


def test_invoice_first_matching_does_not_double_stock(setup):
    c, f, ids = setup
    o = placed(c, ids)
    tx = invoice(c, f, ids)
    assert available(c, ids) == 36
    assert (
        c.post(
            ops(ids, "/orders/" + o["id"] + "/invoices"), json={"transaction_id": tx}
        ).status_code
        == 200
    )
    receive(c, ids, o, 12)
    receive(c, ids, o, 12)
    assert available(c, ids) == 36


def test_receipt_first_matching_reconciles_legacy_invoice_stock(setup):
    c, f, ids = setup
    o = placed(c, ids)
    receive(c, ids, o, 24)
    tx = invoice(c, f, ids)
    assert available(c, ids) == 60
    assert (
        c.post(
            ops(ids, "/orders/" + o["id"] + "/invoices"), json={"transaction_id": tx}
        ).status_code
        == 200
    )
    assert available(c, ids) == 36
    assert (
        c.post(
            ops(ids, "/orders/" + o["id"] + "/invoices"), json={"transaction_id": tx}
        ).status_code
        == 200
    )
    assert available(c, ids) == 36


def test_order_linked_invoice_never_posts_receipt_stock(setup):
    c, f, ids = setup
    o = placed(c, ids)
    invoice(c, f, ids, order_id=o["id"])
    assert available(c, ids) == 12
    receive(c, ids, o, 24)
    assert available(c, ids) == 36


def test_returns_credits_and_partial_payments(setup):
    c, f, ids = setup
    o = placed(c, ids)
    invoice(c, f, ids, order_id=o["id"])
    receive(c, ids, o, 24)
    current = c.get(ops(ids, "/orders/" + o["id"])).json()
    r = c.post(
        ops(ids, "/orders/" + o["id"] + "/returns"),
        json={
            "version": current["version"],
            "idempotency_key": uuid4().hex,
            "lines": [{"order_line_id": current["lines"][0]["id"], "accepted": 4}],
        },
    )
    assert r.status_code == 201, r.text
    assert available(c, ids) == 32
    payable = c.get(ops(ids, "/payables")).json()["items"][0]
    payment = {
        "version": payable["version"],
        "amount": 100,
        "date": str(today()),
        "method": "upi",
        "reference": "external-receipt",
        "idempotency_key": uuid4().hex,
    }
    assert (
        c.post(
            ops(ids, "/payables/" + payable["id"] + "/payments"), json=payment
        ).status_code
        == 201
    )
    assert (
        c.post(
            ops(ids, "/payables/" + payable["id"] + "/payments"), json=payment
        ).status_code
        == 200
    )
    payable = c.get(ops(ids, "/payables/" + payable["id"])).json()
    assert Decimal(payable["outstanding"]) == 428
    response = c.post(
        ops(ids, "/payables/" + payable["id"] + "/credits"),
        json={
            "version": payable["version"],
            "return_id": r.json()["id"],
            "amount": 88,
            "reference": "CN-TEST",
            "date": str(today()),
        },
    )
    assert response.status_code == 200, response.text
    payable = c.get(ops(ids, "/payables/" + payable["id"])).json()
    assert Decimal(payable["outstanding"]) == 340
    assert (
        c.post(
            ops(ids, "/payables/" + payable["id"] + "/payments"),
            json=payment
            | {
                "version": payable["version"],
                "amount": 1000,
                "idempotency_key": uuid4().hex,
            },
        ).status_code
        == 422
    )


def test_branch_isolation_and_receiver_permissions(setup):
    c, f, ids = setup
    b = c.post(
        ops(ids, "/branches"), json={"name": "East Store", "code": "EAST"}
    ).json()
    assert "id" in b, b
    c.headers["x-branch-id"] = b["id"]
    assert available(c, ids) == 0
    r = c.post(
        root(ids) + "/inventory",
        json={
            "product_id": ids["product"],
            "qty": 100,
            "kind": "opening",
            "reason": "East opening",
        },
    )
    assert r.status_code == 200, r.text
    assert available(c, ids) == 100
    c.headers.pop("x-branch-id")
    assert available(c, ids) == 12
    staff = c.post(
        ops(ids, "/staff"),
        json={
            "email": "receiver@test.local",
            "password": "receiving-test-123",
            "branch_id": b["id"],
            "role": "receiving",
        },
    )
    assert staff.status_code == 200, staff.text
    login = c.post(
        "/api/v1/auth/login",
        json={"email": "receiver@test.local", "password": "receiving-test-123"},
    )
    c.headers["x-csrf-token"] = login.json()["csrf"]
    assert available(c, ids) == 100
    with f() as db:
        main = db.scalar(select(Branch).where(Branch.code == "MAIN")).id
    c.headers["x-branch-id"] = main
    assert c.get(ops(ids, "/inventory")).status_code == 404
    c.headers["x-branch-id"] = b["id"]
    assert (
        c.post(
            ops(ids, "/orders"),
            json={
                "supplier_id": ids["supplier"],
                "expected": str(today()),
                "source_key": uuid4().hex,
                "lines": [{"quote_id": ids["quote"], "qty": 24}],
            },
        ).status_code
        == 403
    )


def test_manager_limits_and_budget_reservation(setup):
    c, f, ids = setup
    branches = c.get(ops(ids, "/branches")).json()
    b = branches[0]
    assert (
        c.put(
            ops(ids, "/branches/" + b["id"]),
            json={
                "name": b["name"],
                "code": b["code"],
                "budget": 600,
                "manager_limit": 100,
                "version": b["version"],
            },
        ).status_code
        == 200
    )
    assert (
        c.post(
            ops(ids, "/staff"),
            json={
                "email": "manager@test.local",
                "password": "manager-password-123",
                "branch_id": b["id"],
                "role": "manager",
            },
        ).status_code
        == 200
    )
    o = make_order(c, ids)
    o = act_order(c, ids, o, "submit")
    login = c.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.local", "password": "manager-password-123"},
    )
    c.headers["x-csrf-token"] = login.json()["csrf"]
    act_order(c, ids, o, "approve", 403)
    login = c.post(
        "/api/v1/auth/login",
        json={"email": "owner@test.local", "password": "correct-test-password"},
    )
    c.headers["x-csrf-token"] = login.json()["csrf"]
    act_order(c, ids, o, "approve")
    second = make_order(c, ids)
    act_order(c, ids, second, "submit")
    act_order(c, ids, second, "approve", 409)
    assert Decimal(c.get(ops(ids, "/branches")).json()[0]["committed"]) == 528


def test_edit_approved_order_releases_budget_and_requires_reapproval(setup):
    c, f, ids = setup
    o = make_order(c, ids)
    act_order(c, ids, o, "submit")
    o = act_order(c, ids, o, "approve")
    payload = {
        "supplier_id": ids["supplier"],
        "expected": str(today()),
        "source_key": o["source_key"],
        "version": o["version"],
        "lines": [{"quote_id": ids["quote"], "qty": 36}],
    }
    r = c.put(ops(ids, "/orders/" + o["id"]), json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "awaiting_approval"
    assert Decimal(c.get(ops(ids, "/branches")).json()[0]["committed"]) == 0
    act_order(c, ids, r.json(), "approve")
    assert Decimal(c.get(ops(ids, "/branches")).json()[0]["committed"]) == 792


def test_transfers_conserve_stock_and_cannot_cancel_dispatch(setup):
    c, f, ids = setup
    destination = c.post(
        ops(ids, "/branches"), json={"name": "North", "code": "NORTH"}
    ).json()
    t = c.post(
        ops(ids, "/transfers"),
        json={
            "destination_id": destination["id"],
            "lines": [{"product_id": ids["product"], "qty": 6}],
        },
    ).json()
    for action in ("approve", "ordered"):
        r = c.post(
            ops(ids, "/transfers/" + t["id"] + "/transition"),
            json={"version": t["version"], "action": action},
        )
        assert r.status_code == 200, r.text
        t = c.get(ops(ids, "/transfers/" + t["id"])).json()
    assert available(c, ids) == 6
    assert (
        c.post(
            ops(ids, "/transfers/" + t["id"] + "/transition"),
            json={"version": t["version"], "action": "cancel"},
        ).status_code
        == 409
    )
    c.headers["x-branch-id"] = destination["id"]
    r = c.post(
        ops(ids, "/transfers/" + t["id"] + "/receive"),
        json={
            "version": t["version"],
            "idempotency_key": uuid4().hex,
            "lines": [{"product_id": ids["product"], "qty": 4}],
        },
    )
    assert r.status_code == 200, r.text
    assert available(c, ids) == 4
    t = c.get(ops(ids, "/transfers/" + t["id"])).json()
    assert t["status"] == "partially_received"
    r = c.post(
        ops(ids, "/transfers/" + t["id"] + "/receive"),
        json={
            "version": t["version"],
            "idempotency_key": uuid4().hex,
            "lines": [{"product_id": ids["product"], "qty": 2}],
        },
    )
    assert r.status_code == 200, r.text
    assert available(c, ids) == 6
    c.headers.pop("x-branch-id")
    assert available(c, ids) == 6


def test_notifications_deduplicate_and_report_matches_invoices(setup):
    c, f, ids = setup
    invoice(c, f, ids)
    a = c.get(ops(ids, "/notifications"))
    b = c.get(ops(ids, "/notifications"))
    assert a.status_code == b.status_code == 200
    assert len(a.json()) == len(b.json())
    r = c.get(ops(ids, "/reports")).json()
    assert Decimal(r["purchase_total"]) == 528
    assert Decimal(r["outstanding"]) == 528


def test_rfq_response_award_and_quote_constraints(setup):
    c, f, ids = setup
    r = c.post(
        ops(ids, "/rfqs"),
        json={
            "title": "Weekly replenishment",
            "deadline": str(today() + timedelta(days=3)),
            "supplier_ids": [ids["supplier"]],
            "lines": [{"product_id": ids["product"], "qty": 24}],
        },
    )
    assert r.status_code == 201, r.text
    rfq = r.json()
    assert (
        c.post(
            ops(ids, "/rfqs/" + rfq["id"] + "/responses"),
            json={"version": 1, "quote_ids": [ids["quote"]]},
        ).status_code
        == 200
    )
    assert (
        c.post(
            ops(ids, "/rfqs/" + rfq["id"] + "/award"),
            json={"version": 2, "quote_ids": [ids["quote"]]},
        ).status_code
        == 200
    )
    assert c.get(ops(ids, "/rfqs/" + rfq["id"])).json()["status"] == "awarded"
