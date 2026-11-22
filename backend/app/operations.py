"""Purchasing, physical stock and supplier liabilities have separate lifecycles."""

from collections import defaultdict
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
import json
from fastapi import HTTPException
from sqlalchemy import select, update, func
from .db import now, today, uid
from .models import *
from .domain import (
    rows,
    owned,
    plain,
    dec,
    inventory,
    forecasts,
    costs,
    step_size,
    audit,
)

ZERO = Decimal(0)


@contextmanager
def at_branch(db, branch_id):
    old_ids = db.info.get("branch_ids")
    old_write = db.info.get("write_branch")
    db.info["branch_ids"] = [branch_id]
    db.info["write_branch"] = branch_id
    try:
        yield
    finally:
        db.info["branch_ids"] = old_ids
        db.info["write_branch"] = old_write


def fingerprint(payload):
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def require_role(request, *roles):
    if request.state.role not in roles:
        raise HTTPException(403, "This action is not available for your role")
    if request.state.role in ("owner", "manager") and request.method not in (
        "GET",
        "HEAD",
    ):
        if not request.state.session.mfa_verified:
            # Demonstration workspaces intentionally permit the seeded owner.
            if not getattr(request.state, "demo", False):
                raise HTTPException(
                    403,
                    "Sign in with an authenticator before approval or financial actions",
                )


def one_branch(request):
    if not request.state.branch_id:
        raise HTTPException(422, "Choose one branch for this action")
    return request.state.branch_id


def branch(db, bid, branch_id):
    return owned(db, Branch, branch_id, bid)


def budget_reserve(db, bid, branch_id, amount):
    changed = db.execute(
        update(Branch)
        .where(
            Branch.id == branch_id,
            Branch.business_id == bid,
            Branch.committed + amount <= Branch.budget,
        )
        .values(committed=Branch.committed + amount, version=Branch.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(
            409,
            "Branch purchasing budget would be exceeded; ask the owner to increase it",
        )


def history(order, action, actor, note=""):
    order.history = order.history + [
        {"action": action, "actor": actor, "at": now().isoformat(), "note": note}
    ]


def all_order_lines(db, bid, order_id):
    return db.scalars(
        select(OrderLine)
        .where(OrderLine.business_id == bid, OrderLine.order_id == order_id)
        .execution_options(unscoped=True)
    ).all()


def get_order(db, bid, order_id, ids):
    order = db.scalar(
        select(PurchaseOrder)
        .where(PurchaseOrder.id == order_id, PurchaseOrder.business_id == bid)
        .execution_options(unscoped=True)
    )
    if not order or not any(
        l.branch_id in ids for l in all_order_lines(db, bid, order_id)
    ):
        raise HTTPException(404, "Order not found")
    return order


def order_view(db, bid, order, ids):
    lines = [l for l in all_order_lines(db, bid, order.id) if l.branch_id in ids]
    linked = (
        db.scalars(
            select(InvoiceAllocation).where(
                InvoiceAllocation.order_line_id.in_([l.id for l in lines])
            )
        ).all()
        if lines
        else []
    )
    suppliers = {s.id: s.name for s in rows(db, Supplier, bid)}
    products = {p.id: p for p in rows(db, Product, bid)}
    result = plain(order) | {
        "supplier_name": suppliers.get(order.supplier_id),
        "total": sum((l.qty * l.cash_unit for l in lines), ZERO),
        "lines": [
            plain(l)
            | {
                "name": products[l.product_id].name,
                "sku": products[l.product_id].sku,
                "outstanding": max(ZERO, l.qty - l.received),
                "invoiced": sum(
                    (a.qty for a in linked if a.order_line_id == l.id), ZERO
                ),
            }
            for l in lines
        ],
    }
    result["receipts"] = [
        plain(r) for r in rows(db, GoodsReceipt, bid) if r.order_id == order.id
    ]
    result["invoices"] = [
        plain(t)
        for t in rows(db, Transaction, bid)
        if t.id in {db.get(Line, a.invoice_line_id).transaction_id for a in linked}
    ]
    return result


def create_order(db, bid, branch_id, payload, actor, owner=False, editing=None):
    existing = db.scalar(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.business_id == bid,
            PurchaseOrder.source_key == payload.source_key,
        )
        .execution_options(unscoped=True)
    )
    if existing and editing is None:
        if existing.created_by != actor:
            raise HTTPException(409, "Order reference is already in use")
        return existing
    if payload.basket_id:
        basket = owned(db, Basket, payload.basket_id, bid)
        if basket.status not in ("approved", "exported", "partial"):
            raise HTTPException(409, "Approve the basket before conversion")
    if payload.rfq_id:
        rfq = owned(db, RFQ, payload.rfq_id, bid)
        if rfq.status != "awarded":
            raise HTTPException(409, "Award the RFQ before conversion")
    supplier = owned(db, Supplier, payload.supplier_id, bid)
    order = (
        editing
        if editing is not None
        else PurchaseOrder(
            id=uid(),
            business_id=bid,
            branch_id=branch_id,
            number="PO-" + today().strftime("%y%m") + "-" + uid()[:6].upper(),
            source_key=payload.source_key,
            supplier_id=supplier.id,
            basket_id=payload.basket_id,
            rfq_id=payload.rfq_id,
            expected=payload.expected,
            created_by=actor,
            note=payload.note,
            history=[],
        )
    )
    totals = defaultdict(Decimal)
    prepared = []
    for entry in payload.lines:
        q = owned(db, Quote, entry.quote_id, bid)
        target = entry.branch_id or branch_id
        branch(db, bid, target)
        if target != branch_id and not owner:
            raise HTTPException(403, "Only the owner can consolidate branch purchases")
        if q.supplier_id != supplier.id:
            raise HTTPException(422, "All lines must belong to this supplier")
        totals[q.id] += entry.qty
        prepared.append((entry, q, target))
    for qid, quantity in totals.items():
        q = owned(db, Quote, qid, bid)
        if quantity < q.moq or quantity % step_size(q):
            raise HTTPException(
                422, "Order quantities must respect supplier MOQ and pack multiples"
            )
        if q.valid_until and q.valid_until < today():
            raise HTTPException(
                422, "Quote expired; record a current quote before ordering"
            )
    if editing is not None:
        from sqlalchemy import delete

        previous = all_order_lines(db, bid, order.id)
        order.history = order.history + [
            {
                "action": "revision_snapshot",
                "at": now().isoformat(),
                "lines": [
                    {
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in plain(l).items()
                    }
                    for l in previous
                ],
            }
        ]
        if order.reserved_budget:
            for l in previous:
                db.execute(
                    update(Branch)
                    .where(Branch.id == l.branch_id)
                    .values(
                        committed=Branch.committed - l.qty * l.cash_unit,
                        version=Branch.version + 1,
                    )
                )
        db.execute(delete(OrderLine).where(OrderLine.order_id == order.id))
        order.status = "awaiting_approval" if order.status == "approved" else "draft"
        order.supplier_id = supplier.id
        order.expected = payload.expected
        order.note = payload.note
        order.reserved_budget = False
        order.total = ZERO
    db.add(order)
    db.flush()
    business = db.get(Business, bid)
    for entry, q, target in prepared:
        economic, cash = costs(
            q, totals[q.id], business.settings.get("recoverable_gst", True)
        )
        db.add(
            OrderLine(
                business_id=bid,
                branch_id=target,
                order_id=order.id,
                product_id=q.product_id,
                quote_id=q.id,
                qty=entry.qty,
                cash_unit=cash,
                economic_unit=economic,
                allocations=[{"branch_id": target, "qty": str(entry.qty)}],
            )
        )
        order.total += entry.qty * cash
    if order.total < supplier.minimum_order:
        raise HTTPException(422, "Supplier minimum order value is not reached")
    history(order, "edited" if editing is not None else "draft", actor)
    audit(
        db,
        bid,
        actor,
        "order.edited" if editing is not None else "order.created",
        order.id,
    )
    return order


def transition_order(db, bid, order, payload, request, user):
    if order.version != payload.version:
        raise HTTPException(409, "Order changed; reload before continuing")
    require_role(request, "owner", "manager", "reviewer")
    lines = all_order_lines(db, bid, order.id)
    if any(l.branch_id not in request.state.branch_ids for l in lines):
        raise HTTPException(403, "You need access to every allocated branch")
    action = payload.action
    old = order.status
    if action == "submit":
        if old not in ("draft", "returned"):
            raise HTTPException(409, "Only drafts or returned orders can be submitted")
        order.status = "awaiting_approval"
        db.add(
            ApprovalRequest(
                business_id=bid,
                branch_id=order.branch_id,
                order_id=order.id,
                requested_by=user.id,
            )
        )
    elif action in ("approve", "reject", "return"):
        require_role(request, "owner", "manager")
        if old != "awaiting_approval":
            raise HTTPException(409, "Order is not awaiting approval")
        if action != "approve" and not payload.reason.strip():
            raise HTTPException(422, "A reason is required")
        amounts = defaultdict(Decimal)
        for l in lines:
            amounts[l.branch_id] += l.qty * l.cash_unit
        if action == "approve":
            if request.state.role == "manager" and any(
                order.total > branch(db, bid, k).manager_limit for k in amounts
            ):
                raise HTTPException(
                    403,
                    "Order exceeds the manager approval limit; owner approval is required",
                )
            for k, amount in amounts.items():
                budget_reserve(db, bid, k, amount)
            order.reserved_budget = True
            order.status = "approved"
        else:
            order.status = "rejected" if action == "reject" else "returned"
        for a in rows(db, ApprovalRequest, bid):
            if a.order_id == order.id and a.status == "pending":
                a.status = {
                    "approve": "approved",
                    "reject": "rejected",
                    "return": "returned",
                }[action]
                a.decided_by = user.id
                a.reason = payload.reason
    elif action == "ordered":
        require_role(request, "owner", "manager")
        if old != "approved":
            raise HTTPException(409, "Approve the order first")
        order.status = "ordered"
    elif action in ("cancel", "close"):
        require_role(request, "owner", "manager")
        if old in ("cancelled", "closed"):
            raise HTTPException(409, "Order is already final")
        if action == "cancel" and any(l.received for l in lines):
            raise HTTPException(
                409,
                "Received orders must be closed; use a supplier return for received goods",
            )
        if action == "close" and old not in (
            "ordered",
            "partially_received",
            "received",
        ):
            raise HTTPException(409, "Only placed orders can be closed")
        if order.reserved_budget:
            for l in lines:
                release = (l.qty - l.received) * l.cash_unit
                db.execute(
                    update(Branch)
                    .where(Branch.id == l.branch_id)
                    .values(
                        committed=Branch.committed - release, version=Branch.version + 1
                    )
                )
        order.status = "cancelled" if action == "cancel" else "closed"
    changed = db.execute(
        update(PurchaseOrder)
        .where(PurchaseOrder.id == order.id, PurchaseOrder.version == payload.version)
        .values(version=PurchaseOrder.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Another action updated the order")
    history(order, action, user.id, payload.reason)
    audit(db, bid, user.id, "order." + action, order.id, {"reason": payload.reason})


def receive_order(db, bid, order, payload, request, user, returning=False):
    require_role(request, "owner", "manager", "receiving", "reviewer")
    if db.get(Business, bid).mode != "standalone":
        raise HTTPException(
            409, "Receive and return goods in Zoho, then sync the authoritative stock"
        )
    raw = payload.model_dump(mode="json")
    digest = fingerprint(raw)
    old = db.scalar(
        select(GoodsReceipt)
        .where(
            GoodsReceipt.business_id == bid,
            GoodsReceipt.idempotency_key == payload.idempotency_key,
        )
        .execution_options(unscoped=True)
    )
    if old:
        if old.request_hash != digest:
            raise HTTPException(409, "Idempotency key was used for a different receipt")
        return old
    if order.status not in ("ordered", "partially_received", "received", "closed") or (
        order.status in ("received", "closed") and not returning
    ):
        raise HTTPException(409, "This order is not open for receiving")
    changed = db.execute(
        update(PurchaseOrder)
        .where(PurchaseOrder.id == order.id, PurchaseOrder.version == payload.version)
        .values(version=PurchaseOrder.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Order changed; reload before receiving")
    receipt = GoodsReceipt(
        business_id=bid,
        branch_id=one_branch(request),
        order_id=order.id,
        idempotency_key=payload.idempotency_key,
        request_hash=digest,
        kind="return" if returning else "receipt",
        note=payload.note,
        lines=[],
    )
    db.add(receipt)
    db.flush()
    seen = set()
    positive = False
    for entry in payload.lines:
        if entry.order_line_id in seen:
            raise HTTPException(422, "Duplicate receipt line")
        seen.add(entry.order_line_id)
        line = owned(db, OrderLine, entry.order_line_id, bid)
        if line.order_id != order.id or line.branch_id != request.state.branch_id:
            raise HTTPException(
                403, "Receive only lines allocated to the selected branch"
            )
        quantity = entry.accepted
        if quantity + entry.rejected <= 0:
            continue
        positive = True
        if returning:
            if quantity > line.received - line.returned:
                raise HTTPException(422, "Return exceeds accepted receipt quantity")
            with at_branch(db, line.branch_id):
                available = next(
                    x
                    for x in inventory(db, db.get(Business, bid))
                    if x["product_id"] == line.product_id
                )
            if quantity > dec(available["available"]):
                raise HTTPException(409, "Not enough available stock for this return")
            line.returned += quantity
            post_qty = -quantity
        else:
            if quantity + entry.rejected > line.qty - line.received:
                raise HTTPException(422, "Receipt exceeds outstanding quantity")
            # Invoice-first purchases may already have posted inventory.
            allocations = db.scalars(
                select(InvoiceAllocation).where(
                    InvoiceAllocation.order_line_id == line.id
                )
            ).all()
            preposted = sum((a.stock_preposted for a in allocations), ZERO)
            already_received = line.received
            post_qty = max(ZERO, already_received + quantity - preposted) - max(
                ZERO, already_received - preposted
            )
            line.received += quantity
        if post_qty:
            db.add(
                Movement(
                    business_id=bid,
                    branch_id=line.branch_id,
                    product_id=line.product_id,
                    qty=post_qty,
                    kind="supplier_return" if returning else "goods_receipt",
                    reason=f"{order.number} · {receipt.id[:8]}",
                )
            )
        receipt.lines = receipt.lines + [
            {
                "order_line_id": line.id,
                "product_id": line.product_id,
                "accepted": str(quantity),
                "rejected": str(entry.rejected),
                "posted_stock": str(post_qty),
                "cash_unit": str(line.cash_unit),
            }
        ]
    if not positive:
        raise HTTPException(422, "Enter an accepted or rejected quantity")
    db.flush()
    if not returning:
        all_lines = all_order_lines(db, bid, order.id)
        order.status = (
            "received"
            if all(l.received >= l.qty for l in all_lines)
            else "partially_received"
        )
    history(order, "return" if returning else "receipt", user.id, payload.note)
    audit(
        db,
        bid,
        user.id,
        "order.returned" if returning else "order.received",
        order.id,
        {"receipt_id": receipt.id},
    )
    return receipt


def link_invoice(db, bid, order, tx, ids, actor):
    if tx.kind != "purchase" or not tx.active or tx.supplier_id != order.supplier_id:
        raise HTTPException(422, "Select an active purchase invoice for this supplier")
    for line in rows(db, Line, bid):
        if line.transaction_id != tx.id:
            continue
        if db.scalar(
            select(InvoiceAllocation).where(
                InvoiceAllocation.invoice_line_id == line.id
            )
        ):
            continue
        candidates = [
            l
            for l in all_order_lines(db, bid, order.id)
            if l.product_id == line.product_id
            and l.branch_id == tx.branch_id
            and l.branch_id in ids
        ]
        if len(candidates) != 1:
            raise HTTPException(
                422, "Invoice product must map to one order line in its branch"
            )
        target = candidates[0]
        allocated = sum(
            (
                a.qty
                for a in rows(db, InvoiceAllocation, bid)
                if a.order_line_id == target.id
            ),
            ZERO,
        )
        if allocated + line.qty > target.qty:
            raise HTTPException(422, "Invoiced quantity exceeds ordered quantity")
        preposted = sum(
            (
                m.qty
                for m in rows(db, Movement, bid)
                if m.transaction_id == tx.id and m.product_id == line.product_id
            ),
            ZERO,
        )
        if preposted and target.received:
            # Both sources already posted: append the overlap reversal, never erase evidence.
            overlap = min(preposted, target.received, line.qty)
            if overlap:
                db.add(
                    Movement(
                        business_id=bid,
                        branch_id=tx.branch_id,
                        product_id=line.product_id,
                        transaction_id=tx.id,
                        qty=-overlap,
                        kind="invoice_receipt_reconciliation",
                        reason=f"Linked to {order.number}; receipt already posted",
                    )
                )
        db.add(
            InvoiceAllocation(
                business_id=bid,
                branch_id=tx.branch_id,
                order_line_id=target.id,
                invoice_line_id=line.id,
                qty=line.qty,
                stock_preposted=min(preposted, line.qty),
            )
        )
    audit(db, bid, actor, "order.invoice_linked", order.id, {"transaction_id": tx.id})


def ensure_payables(db, bid):
    for tx in rows(db, Transaction, bid):
        if (
            tx.kind == "purchase"
            and tx.supplier_id
            and not db.scalar(select(Payable).where(Payable.transaction_id == tx.id))
        ):
            insert_once(db,Payable,{'business_id':bid,'branch_id':tx.branch_id,'transaction_id':tx.id,'supplier_id':tx.supplier_id,'due':tx.date+timedelta(days=14),'version':1},['transaction_id'])
    db.flush()


def insert_once(db,cls,values,unique_columns):
    if db.bind.dialect.name=='postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(cls.__table__).values(id=uid(),**values).on_conflict_do_nothing(index_elements=unique_columns))


def payable_view(db, payable):
    tx = db.get(Transaction, payable.transaction_id)
    payments = db.scalars(select(Payment).where(Payment.payable_id == payable.id)).all()
    credits = db.scalars(
        select(SupplierCredit).where(SupplierCredit.payable_id == payable.id)
    ).all()
    paid = sum((p.amount for p in payments), ZERO)
    credited = sum((c.amount for c in credits), ZERO)
    outstanding = max(ZERO, tx.total - paid - credited) if tx.active else ZERO
    supplier = db.get(Supplier, payable.supplier_id)
    return plain(payable) | {
        "invoice_no": tx.invoice_no,
        "supplier_name": supplier.name,
        "invoice_date": tx.date,
        "amount": tx.total,
        "paid": paid,
        "credited": credited,
        "outstanding": outstanding,
        "status": "inactive"
        if not tx.active
        else "paid"
        if outstanding == 0
        else "overdue"
        if payable.due < today()
        else "partially_paid"
        if paid
        else "open",
        "payments": [plain(p) for p in payments],
        "credits": [plain(c) for c in credits],
    }


def stock_adjust(db, bid, branch_id, pid, qty, kind, reason):
    db.add(
        Movement(
            business_id=bid,
            branch_id=branch_id,
            product_id=pid,
            qty=qty,
            kind=kind,
            reason=reason,
        )
    )


def lock_stock(db,bid,branch_id):
    b=db.scalar(select(Branch).where(Branch.id==branch_id,Branch.business_id==bid).with_for_update().execution_options(populate_existing=True))
    changed=db.execute(update(Branch).where(Branch.id==branch_id,Branch.version==b.version).values(version=Branch.version+1)).rowcount
    if not changed: raise HTTPException(409,'Branch stock changed; reload before dispatching')


def transfer_action(db, bid, t, payload, request, user):
    if db.get(Business, bid).mode != "standalone":
        raise HTTPException(409, "Transfers are managed in Zoho in mirrored mode")
    require_role(request, "owner", "manager")
    if t.branch_id not in request.state.branch_ids:
        raise HTTPException(403, "Source branch access required")
    if payload.version != t.version:
        raise HTTPException(409, "Transfer changed; reload")
    action = payload.action
    if action == "approve" and t.status == "requested":
        t.status = "approved"
    elif action == "ordered" and t.status == "approved":
        lock_stock(db,bid,t.branch_id)
        for line in t.lines:
            with at_branch(db, t.branch_id):
                item = next(
                    s
                    for s in inventory(db, db.get(Business, bid))
                    if s["product_id"] == line["product_id"]
                )
                if dec(line["qty"]) > dec(item["available"]):
                    raise HTTPException(
                        409, "Source branch has insufficient available stock"
                    )
            stock_adjust(
                db,
                bid,
                t.branch_id,
                line["product_id"],
                -dec(line["qty"]),
                "transfer_dispatch",
                t.number,
            )
        t.status = "dispatched"
    elif action == "cancel" and t.status in ("requested", "approved"):
        t.status = "cancelled"
    else:
        raise HTTPException(
            409,
            "Invalid transfer transition; dispatched transfers must be received or reconciled",
        )
    changed = db.execute(
        update(Transfer)
        .where(Transfer.id == t.id, Transfer.version == payload.version)
        .values(version=Transfer.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Transfer changed; reload")
    t.history = t.history + [
        {"action": action, "at": now().isoformat(), "actor": user.id}
    ]
    audit(db, bid, user.id, "transfer." + action, t.id)


def refresh_notifications(db, bid, ids):
    candidates = []
    for a in rows(db, ApprovalRequest, bid):
        if a.status == "pending":
            candidates.append(
                (
                    a.branch_id,
                    "approval:" + a.id,
                    "Purchase awaiting approval",
                    "Review the purchase order and budget.",
                    "/purchasing/approvals",
                    "approval",
                )
            )
    for order in rows(db, PurchaseOrder, bid):
        if (
            order.status in ("ordered", "partially_received")
            and order.expected < today()
        ):
            candidates.append(
                (
                    order.branch_id,
                    "late:" + order.id,
                    "Delivery is overdue",
                    order.number + " was expected " + order.expected.isoformat(),
                    "/purchasing/orders/" + order.id,
                    "delivery",
                )
            )
    for p in rows(db, Payable, bid):
        view = payable_view(db, p)
        if view["status"] == "overdue":
            candidates.append(
                (
                    p.branch_id,
                    "payable:" + p.id,
                    "Supplier payment is overdue",
                    view["invoice_no"] + " · ₹" + str(view["outstanding"]),
                    "/purchasing/payables",
                    "payable",
                )
            )
    for q in rows(db, Quote, bid):
        if q.valid_until and today() <= q.valid_until <= today() + timedelta(days=3):
            for branch_id in ids:
                candidates.append(
                    (
                        branch_id,
                        "quote:" + q.id + ":" + branch_id,
                        "Supplier quote expires soon",
                        str(q.valid_until),
                        "/purchasing/suppliers",
                        "quote",
                    )
                )
    for j in rows(db, Job, bid):
        if j.status == "failed":
            candidates.append(
                (
                    j.branch_id,
                    "job:" + j.id,
                    "Document or sync processing failed",
                    j.kind,
                    "/administration/activity",
                    "processing",
                )
            )
    for branch_id in ids:
        with at_branch(db, branch_id):
            for s in inventory(db, db.get(Business, bid)):
                if dec(s["available"]) <= 0:
                    candidates.append(
                        (
                            branch_id,
                            "stock:" + branch_id + ":" + s["product_id"],
                            "Product is out of stock",
                            s["name"],
                            "/inventory/stock",
                            "stock",
                        )
                    )
    for branch_id, key, title, detail, href, category in candidates:
        if not db.scalar(
            select(Notification).where(
                Notification.business_id == bid, Notification.fingerprint == key
            )
        ):
            insert_once(db,Notification,{'business_id':bid,'branch_id':branch_id,'fingerprint':key,'title':title,'detail':detail,'href':href,'category':category,'read_by':[],'created':now()},['business_id','fingerprint'])
    db.flush()
