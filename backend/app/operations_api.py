import csv, io, json
from datetime import timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update, delete, or_, func
from .db import get_db, uid, today, now
from .models import *
from .security import access, hasher
from .domain import (
    rows,
    owned,
    plain,
    audit,
    inventory,
    forecasts,
    alerts,
    recommend,
    dec,
)
from .operations import *
from .operations_schemas import *
from .schemas import QuoteInput
from .imports import read_table
from .integrations import scan_file

router = APIRouter(
    prefix="/api/v1/businesses/{business_id}/workspace", tags=["Procurement workspace"]
)


def out(value, status=200):
    return JSONResponse(
        jsonable_encoder(value, custom_encoder={Decimal: str}), status_code=status
    )


def context(
    request: Request, business_id: str, user=Depends(access), db=Depends(get_db)
):
    request.state.demo = db.get(Business, business_id).demo
    return user


def paged(items, page=1, page_size=25, q="", sort="", direction="asc"):
    if q:
        items = [
            i
            for i in items
            if q.lower()
            in json.dumps(jsonable_encoder(i, custom_encoder={Decimal: str})).lower()
        ]
    if sort:
        items = sorted(
            items,
            key=lambda i: (i.get(sort) is None, str(i.get(sort, ""))),
            reverse=direction == "desc",
        )
    return {
        "items": items[(page - 1) * page_size : page * page_size],
        "total": len(items),
        "page": page,
        "page_size": page_size,
    }


def branch_list(db, bid, request):
    return db.scalars(
        select(Branch).where(
            Branch.business_id == bid, Branch.id.in_(request.state.branch_ids)
        )
    ).all()


@router.get("/session")
def session_info(
    business_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    return {
        "role": request.state.role,
        "branch_id": request.state.branch_id,
        "branch_ids": request.state.branch_ids,
        "business_owner": request.state.business_owner,
    }


@router.get("/transactions")
def transactions(
    business_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    return out([plain(t) for t in rows(db, Transaction, business_id) if t.active])


@router.get("/branches", response_model=list[BranchView])
def branches(business_id, request: Request, user=Depends(context), db=Depends(get_db)):
    # The switcher lists all assigned branches even if one is selected.
    membership = db.scalar(
        select(Membership).where(
            Membership.business_id == business_id, Membership.user_id == user.id
        )
    )
    query = select(Branch).where(Branch.business_id == business_id)
    if membership.role != "owner":
        query = query.where(
            Branch.id.in_(
                select(BranchGrant.branch_id).where(
                    BranchGrant.user_id == user.id,
                    BranchGrant.business_id == business_id,
                )
            )
        )
    return [BranchView.model_validate(plain(b)) for b in db.scalars(query).all()]


@router.post("/branches")
def add_branch(
    business_id,
    payload: BranchInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner")
    b = Branch(business_id=business_id, **payload.model_dump(exclude={"version"}))
    db.add(b)
    db.flush()
    audit(db, business_id, user.id, "branch.created", b.id)
    db.commit()
    return out(plain(b), 201)


@router.put("/branches/{branch_id}")
def edit_branch(
    business_id,
    branch_id,
    payload: BranchInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner")
    b = owned(db, Branch, branch_id, business_id)
    if payload.budget < b.committed:
        raise HTTPException(409, "Budget cannot be below existing commitments")
    if payload.zoho_location_id and db.get(Business, business_id).mode == "zoho":
        # Mapping is explicit; live sync must verify this location before activation.
        integration = db.get(Integration, business_id)
        if not integration or not integration.organization_id:
            raise HTTPException(409, "Connect a Zoho organization first")
    changed = db.execute(
        update(Branch)
        .where(Branch.id == b.id, Branch.version == payload.version)
        .values(**payload.model_dump(exclude={"version"}), version=Branch.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Branch changed; reload")
    audit(db, business_id, user.id, "branch.updated", b.id)
    db.commit()
    return {"ok": True}


@router.get("/staff")
def staff(business_id, request: Request, user=Depends(context), db=Depends(get_db)):
    require_role(request, "owner")
    people = {
        u.id: u.email
        for u in db.scalars(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.business_id == business_id)
        ).all()
    }
    return out(
        [
            plain(g) | {"email": people.get(g.user_id, "")}
            for g in rows(db, BranchGrant, business_id)
        ]
    )


@router.post("/staff")
def add_staff(
    business_id,
    payload: StaffInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner")
    owned(db, Branch, payload.branch_id, business_id)
    email = payload.email.strip().lower()
    person = db.scalar(select(User).where(User.email == email))
    if not person:
        if len(payload.password) < 12:
            raise HTTPException(
                422, "New users need a password of at least 12 characters"
            )
        person = User(email=email, password=hasher.hash(payload.password))
        db.add(person)
        db.flush()
    membership = db.scalar(
        select(Membership).where(
            Membership.business_id == business_id, Membership.user_id == person.id
        )
    )
    if not membership:
        db.add(Membership(business_id=business_id, user_id=person.id, role="staff"))
    grant = db.scalar(
        select(BranchGrant).where(
            BranchGrant.branch_id == payload.branch_id, BranchGrant.user_id == person.id
        )
    )
    if not grant:
        grant = BranchGrant(
            business_id=business_id,
            branch_id=payload.branch_id,
            user_id=person.id,
            role=payload.role,
        )
        db.add(grant)
    else:
        grant.role = payload.role
    audit(
        db,
        business_id,
        user.id,
        "branch.access_granted",
        person.id,
        {"branch_id": payload.branch_id, "role": payload.role},
    )
    db.commit()
    return {"ok": True}


@router.put("/products/{product_id}/settings")
def product_settings(
    business_id,
    product_id,
    payload: BranchProductInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager", "reviewer")
    owned(db, Product, product_id, business_id)
    branch_id = one_branch(request)
    config = db.scalar(
        select(BranchProduct).where(
            BranchProduct.branch_id == branch_id, BranchProduct.product_id == product_id
        )
    )
    if not config:
        config = BranchProduct(
            business_id=business_id, branch_id=branch_id, product_id=product_id
        )
        db.add(config)
    for k, v in payload.model_dump().items():
        setattr(config, k, v)
    audit(db, business_id, user.id, "branch.product_configured", product_id)
    db.commit()
    return {"ok": True}


@router.get("/catalog/{kind}", response_model=Page)
def catalog(
    business_id,
    kind,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str = "",
    sort: str = "name",
    direction: str = "asc",
    user=Depends(context),
    db=Depends(get_db),
):
    cls = {"products": Product, "suppliers": Supplier}.get(kind)
    if cls is None:
        raise HTTPException(404, "Catalog not found")
    query = select(cls).where(cls.business_id == business_id)
    if q:
        query = query.where(
            or_(
                cls.name.ilike("%" + q + "%"),
                (cls.sku if kind == "products" else cls.gstin).ilike("%" + q + "%"),
            )
        )
    column = (
        getattr(cls, sort, None)
        if sort in ("name", "sku", "sell_price", "pack", "minimum_order")
        else cls.name
    )
    if column is None:
        column = cls.name
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    values = db.scalars(
        query.order_by(column.desc() if direction == "desc" else column.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return out(
        {
            "items": [plain(v) for v in values],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/catalog/{kind}/{record_id}")
def catalog_detail(
    business_id,
    kind,
    record_id,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    cls = {"products": Product, "suppliers": Supplier}.get(kind)
    if not cls:
        raise HTTPException(404, "Catalog not found")
    record = owned(db, cls, record_id, business_id)
    txs = {t.id: t for t in rows(db, Transaction, business_id) if t.active}
    evidence = []
    for l in rows(db, Line, business_id):
        tx = txs.get(l.transaction_id)
        if tx and (
            l.product_id == record_id
            if kind == "products"
            else tx.supplier_id == record_id
        ):
            evidence.append(
                plain(l)
                | {
                    "date": tx.date,
                    "invoice_no": tx.invoice_no,
                    "kind": tx.kind,
                    "supplier_id": tx.supplier_id,
                }
            )
    return out(
        {
            "record": plain(record),
            "history": sorted(evidence, key=lambda v: v["date"], reverse=True)[:200],
            "quotes": [
                plain(q)
                for q in rows(db, Quote, business_id)
                if (
                    q.product_id == record_id
                    if kind == "products"
                    else q.supplier_id == record_id
                )
            ],
            "stock": inventory(db, db.get(Business, business_id))
            if kind == "products"
            else [],
            "deliveries": [
                plain(r)
                for r in rows(db, Receipt, business_id)
                if (
                    r.product_id == record_id
                    if kind == "products"
                    else r.supplier_id == record_id
                )
            ],
            "branch_settings": [
                plain(c)
                for c in rows(db, BranchProduct, business_id)
                if kind == "products"
                and c.product_id == record_id
                and c.branch_id in request.state.branch_ids
            ],
        }
    )


@router.get("/inventory")
def branch_inventory(
    business_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    result = []
    for b in branch_list(db, business_id, request):
        with at_branch(db, b.id):
            result.extend(
                [
                    s | {"branch_id": b.id, "branch_name": b.name}
                    for s in inventory(db, db.get(Business, business_id))
                ]
            )
    return out(result)


@router.get("/forecasts")
def branch_forecasts(
    business_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    result = []
    for b in branch_list(db, business_id, request):
        with at_branch(db, b.id):
            result.extend(
                [
                    f | {"branch_id": b.id, "branch_name": b.name}
                    for f in forecasts(db, db.get(Business, business_id))
                ]
            )
    return out(result)


@router.post("/baskets")
def branch_basket(
    business_id,
    payload: dict,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager", "reviewer")
    branch_id = one_branch(request)
    budget = dec(payload.get("budget", 0))
    if budget <= 0:
        raise HTTPException(422, "A positive cash budget is required")
    lines, snapshot = recommend(db, db.get(Business, business_id), budget)
    b = Basket(
        business_id=business_id,
        branch_id=branch_id,
        budget=budget,
        lines=lines,
        snapshot=snapshot,
        status="draft",
    )
    db.add(b)
    db.flush()
    audit(db, business_id, user.id, "basket.created", b.id)
    db.commit()
    return out(plain(b), 201)


@router.post("/baskets/{basket_id}/submit")
def submit_basket(
    business_id, basket_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    require_role(request, "owner", "manager", "reviewer")
    b = owned(db, Basket, basket_id, business_id)
    if not b.lines:
        raise HTTPException(422, "Basket contains no feasible lines")
    # Basket recommendations are planning evidence; final approval reserves PO budgets.
    b.status = "approved"
    b.version += 1
    audit(db, business_id, user.id, "basket.submitted_for_order", b.id)
    db.commit()
    return {"ok": True}


@router.get("/rfqs", response_model=Page)
def rfqs(
    business_id,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str = "",
    user=Depends(context),
    db=Depends(get_db),
):
    return out(
        paged(
            [
                plain(r)
                for r in sorted(
                    rows(db, RFQ, business_id), key=lambda r: r.created, reverse=True
                )
            ],
            page,
            page_size,
            q,
        )
    )


@router.post("/rfqs")
def add_rfq(
    business_id,
    payload: RFQInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager", "reviewer")
    if payload.deadline < today():
        raise HTTPException(422, "Response deadline is in the past")
    if len({l.product_id for l in payload.lines}) != len(payload.lines):
        raise HTTPException(422, "Choose each product once")
    for s in payload.supplier_ids:
        owned(db, Supplier, s, business_id)
    for l in payload.lines:
        owned(db, Product, l.product_id, business_id)
    r = RFQ(
        business_id=business_id,
        branch_id=one_branch(request),
        number="RFQ-" + uid()[:7].upper(),
        **payload.model_dump(exclude={"lines"}),
        lines=[l.model_dump(mode="json") for l in payload.lines],
    )
    db.add(r)
    db.flush()
    audit(db, business_id, user.id, "rfq.created", r.id)
    db.commit()
    return out(plain(r), 201)


@router.get("/rfqs/{rfq_id}")
def rfq_detail(
    business_id, rfq_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    r = owned(db, RFQ, rfq_id, business_id)
    return out(
        plain(r)
        | {
            "quotes": [
                plain(q) for q in rows(db, Quote, business_id) if q.id in r.responses
            ]
        }
    )


@router.post("/rfqs/{rfq_id}/responses")
def rfq_response(
    business_id,
    rfq_id,
    payload: RFQResponse,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager", "reviewer")
    r = owned(db, RFQ, rfq_id, business_id)
    for qid in payload.quote_ids:
        q = owned(db, Quote, qid, business_id)
        if q.supplier_id not in r.supplier_ids or q.product_id not in [
            l["product_id"] for l in r.lines
        ]:
            raise HTTPException(422, "Quote is not from a requested supplier/product")
    values = list(dict.fromkeys(r.responses + payload.quote_ids))
    changed = db.execute(
        update(RFQ)
        .where(RFQ.id == r.id, RFQ.version == payload.version, RFQ.status == "open")
        .values(responses=values, version=RFQ.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "RFQ changed or was already awarded")
    db.commit()
    return {"ok": True}


@router.post("/rfqs/{rfq_id}/responses/import")
async def rfq_import(
    business_id,
    rfq_id,
    request: Request,
    file: UploadFile = File(...),
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager", "reviewer")
    r = owned(db, RFQ, rfq_id, business_id)
    if r.status != "open":
        raise HTTPException(409, "RFQ is no longer open")
    content = await file.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(413, "File exceeds 10 MB")
    try:
        scan_file(content)
        table = read_table(content, file.filename)
    except Exception as exc:
        raise HTTPException(422, str(exc)[:200])
    if not table or len(table) > 10000:
        raise HTTPException(422, "Provide 1–10,000 rows")
    ids = []
    errors = []
    for index, row in enumerate(table, 2):
        p = db.scalar(
            select(Product).where(
                Product.business_id == business_id, Product.sku == row.get("sku")
            )
        )
        s = db.scalar(
            select(Supplier).where(
                Supplier.business_id == business_id,
                Supplier.gstin == row.get("supplier_gstin"),
            )
        )
        try:
            if not p or not s:
                raise ValueError("SKU or supplier GSTIN not found")
            if s.id not in r.supplier_ids or p.id not in [
                l["product_id"] for l in r.lines
            ]:
                raise ValueError("Product/supplier not requested")
            values = QuoteInput(
                product_id=p.id,
                supplier_id=s.id,
                **{
                    k: v
                    for k, v in row.items()
                    if k not in ("sku", "supplier_gstin") and v != ""
                },
            )
            quote = Quote(
                business_id=business_id,
                **values.model_dump(exclude={"tiers"}),
                tiers=[t.model_dump(mode="json") for t in values.tiers],
            )
            db.add(quote)
            db.flush()
            ids.append(quote.id)
        except Exception as exc:
            errors.append({"row": index, "message": str(exc)[:250]})
    if errors:
        raise HTTPException(422, {"message": "Nothing imported", "errors": errors})
    r.responses = list(dict.fromkeys(r.responses + ids))
    r.version += 1
    db.commit()
    return {"imported": len(ids)}


@router.post("/rfqs/{rfq_id}/award")
def award_rfq(
    business_id,
    rfq_id,
    payload: Award,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager")
    r = owned(db, RFQ, rfq_id, business_id)
    awards = []
    seen = set()
    for qid in payload.quote_ids:
        if qid not in r.responses:
            raise HTTPException(422, "Choose a received quote")
        q = owned(db, Quote, qid, business_id)
        if q.product_id in seen:
            raise HTTPException(422, "Award one supplier per product")
        if q.valid_until and q.valid_until < today():
            raise HTTPException(422, "Quote expired")
        seen.add(q.product_id)
        awards.append(
            {
                "quote_id": q.id,
                "product_id": q.product_id,
                "supplier_id": q.supplier_id,
                "qty": next(
                    l["qty"] for l in r.lines if l["product_id"] == q.product_id
                ),
            }
        )
    changed = db.execute(
        update(RFQ)
        .where(RFQ.id == r.id, RFQ.version == payload.version, RFQ.status == "open")
        .values(status="awarded", awards=awards, version=RFQ.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "RFQ changed; reload")
    audit(db, business_id, user.id, "rfq.awarded", r.id)
    db.commit()
    return {"ok": True}


@router.get("/rfqs/{rfq_id}/export")
def export_rfq(
    business_id, rfq_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    r = owned(db, RFQ, rfq_id, business_id)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "sku",
            "supplier_gstin",
            "unit_cost",
            "tax_pct",
            "freight_unit",
            "pack",
            "moq",
            "multiple",
            "lead_days",
            "valid_until",
        ]
    )
    for line in r.lines:
        p = owned(db, Product, line["product_id"], business_id)
        for sid in r.supplier_ids:
            s = owned(db, Supplier, sid, business_id)
            writer.writerow(
                [
                    safe_csv(p.sku),
                    s.gstin or "",
                    "",
                    0,
                    0,
                    p.pack,
                    p.pack,
                    p.pack,
                    3,
                    "",
                ]
            )
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{r.number}.csv"'},
    )


@router.get("/orders", response_model=Page)
def orders(
    business_id,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str = "",
    status: str = "",
    supplier_id: str = "",
    user=Depends(context),
    db=Depends(get_db),
):
    ids = request.state.branch_ids
    query = (
        select(PurchaseOrder)
        .where(
            PurchaseOrder.business_id == business_id,
            PurchaseOrder.id.in_(
                select(OrderLine.order_id).where(
                    OrderLine.business_id == business_id, OrderLine.branch_id.in_(ids)
                )
            ),
        )
        .execution_options(unscoped=True)
    )
    if status:
        query = query.where(PurchaseOrder.status == status)
    if supplier_id:
        query = query.where(PurchaseOrder.supplier_id == supplier_id)
    values = db.scalars(query.order_by(PurchaseOrder.created.desc())).all()
    return out(
        paged([order_view(db, business_id, o, ids) for o in values], page, page_size, q)
    )


@router.post("/orders")
def add_order(
    business_id,
    payload: OrderInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager", "reviewer")
    o = create_order(
        db,
        business_id,
        one_branch(request),
        payload,
        user.id,
        request.state.business_owner,
    )
    db.commit()
    return out(order_view(db, business_id, o, request.state.branch_ids), 201)


@router.get("/orders/{order_id}")
def get_order_detail(
    business_id, order_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    return out(
        order_view(
            db,
            business_id,
            get_order(db, business_id, order_id, request.state.branch_ids),
            request.state.branch_ids,
        )
    )


@router.put("/orders/{order_id}")
def edit_order(
    business_id,
    order_id,
    payload: OrderInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager", "reviewer")
    o = get_order(db, business_id, order_id, request.state.branch_ids)
    if o.status not in ("draft", "returned", "approved"):
        raise HTTPException(
            409, "Only draft, returned or approved orders can be edited"
        )
    old_lines = all_order_lines(db, business_id, o.id)
    if any(l.branch_id not in request.state.branch_ids for l in old_lines):
        raise HTTPException(403, "Access to every allocated branch is required")
    if db.scalar(
        select(InvoiceAllocation).where(
            InvoiceAllocation.order_line_id.in_([l.id for l in old_lines])
        )
    ):
        raise HTTPException(409, "Matched invoices must be reconciled before editing")
    changed = db.execute(
        update(PurchaseOrder)
        .where(PurchaseOrder.id == o.id, PurchaseOrder.version == payload.version)
        .values(version=PurchaseOrder.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Order changed; reload")
    o = create_order(
        db,
        business_id,
        one_branch(request),
        payload,
        user.id,
        request.state.business_owner,
        editing=o,
    )
    if o.status == "awaiting_approval":
        db.add(
            ApprovalRequest(
                business_id=business_id,
                branch_id=o.branch_id,
                order_id=o.id,
                requested_by=user.id,
            )
        )
    db.commit()
    return out(order_view(db, business_id, o, request.state.branch_ids))


@router.post("/orders/{order_id}/transition")
def order_transition(
    business_id,
    order_id,
    payload: Transition,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    o = get_order(db, business_id, order_id, request.state.branch_ids)
    transition_order(db, business_id, o, payload, request, user)
    db.commit()
    return {"ok": True}


@router.post("/orders/{order_id}/receive")
def order_receive(
    business_id,
    order_id,
    payload: Receive,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    o = get_order(db, business_id, order_id, request.state.branch_ids)
    r = receive_order(db, business_id, o, payload, request, user)
    db.commit()
    return out(plain(r), 201)


@router.post("/orders/{order_id}/returns")
def order_return(
    business_id,
    order_id,
    payload: Receive,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager")
    o = get_order(db, business_id, order_id, request.state.branch_ids)
    r = receive_order(db, business_id, o, payload, request, user, True)
    db.commit()
    return out(plain(r), 201)


@router.post("/orders/{order_id}/invoices")
def invoice_link(
    business_id,
    order_id,
    payload: LinkInvoice,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager", "reviewer")
    o = get_order(db, business_id, order_id, request.state.branch_ids)
    tx = owned(db, Transaction, payload.transaction_id, business_id)
    link_invoice(db, business_id, o, tx, request.state.branch_ids, user.id)
    db.commit()
    return {"ok": True}


def safe_csv(value):
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@router.get("/orders/{order_id}/export")
def order_export(
    business_id, order_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    order = get_order(db, business_id, order_id, request.state.branch_ids)
    view = order_view(db, business_id, order, request.state.branch_ids)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "order",
            "sku",
            "product",
            "branch_id",
            "ordered",
            "received",
            "returned",
            "cash_unit",
            "cash_total",
        ]
    )
    for l in view["lines"]:
        writer.writerow(
            [
                order.number,
                safe_csv(l["sku"]),
                safe_csv(l["name"]),
                l["branch_id"],
                l["qty"],
                l["received"],
                l["returned"],
                l["cash_unit"],
                l["qty"] * l["cash_unit"],
            ]
        )
    audit(db, business_id, user.id, "order.exported", order.id)
    db.commit()
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{order.number}.csv"'},
    )


@router.get("/approvals")
def approvals(business_id, request: Request, user=Depends(context), db=Depends(get_db)):
    return out(
        [
            plain(a)
            | {
                "order": order_view(
                    db,
                    business_id,
                    get_order(db, business_id, a.order_id, request.state.branch_ids),
                    request.state.branch_ids,
                )
            }
            for a in sorted(
                rows(db, ApprovalRequest, business_id),
                key=lambda a: a.created,
                reverse=True,
            )
        ]
    )


@router.get("/payables", response_model=Page)
def payables(
    business_id,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str = "",
    status: str = "",
    user=Depends(context),
    db=Depends(get_db),
):
    ensure_payables(db, business_id)
    items = [payable_view(db, p) for p in rows(db, Payable, business_id)]
    db.commit()
    if status:
        items = [i for i in items if i["status"] == status]
    return out(paged(sorted(items, key=lambda i: i["due"]), page, page_size, q))


@router.get("/payables/{payable_id}")
def payable_detail(
    business_id, payable_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    ensure_payables(db, business_id)
    p = owned(db, Payable, payable_id, business_id)
    value = payable_view(db, p)
    db.commit()
    return out(value)


@router.get("/returns")
def returns(business_id, request: Request, user=Depends(context), db=Depends(get_db)):
    result = []
    for r in rows(db, GoodsReceipt, business_id):
        if r.kind == "return":
            o = get_order(db, business_id, r.order_id, request.state.branch_ids)
            result.append(
                plain(r) | {"supplier_id": o.supplier_id, "order_number": o.number}
            )
    return out(result)


@router.post("/payables/{payable_id}/payments")
def record_payment(
    business_id,
    payable_id,
    payload: PaymentInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager")
    p = owned(db, Payable, payable_id, business_id)
    digest = fingerprint(payload.model_dump(mode="json"))
    old = db.scalar(
        select(Payment).where(
            Payment.business_id == business_id,
            Payment.idempotency_key == payload.idempotency_key,
        )
    )
    if old:
        if old.request_hash != digest:
            raise HTTPException(409, "Idempotency key reused with another payment")
        return out(plain(old))
    if payload.date > today():
        raise HTTPException(422, "Payment date cannot be in the future")
    changed = db.execute(
        update(Payable)
        .where(Payable.id == p.id, Payable.version == payload.version)
        .values(version=Payable.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Payable changed; reload")
    if payload.amount > payable_view(db, p)["outstanding"]:
        raise HTTPException(422, "Payment exceeds the outstanding balance")
    obj = Payment(
        business_id=business_id,
        branch_id=p.branch_id,
        payable_id=p.id,
        request_hash=digest,
        **payload.model_dump(exclude={"version"}),
    )
    db.add(obj)
    audit(
        db,
        business_id,
        user.id,
        "payment.recorded",
        p.id,
        {"amount": str(payload.amount), "reference": payload.reference},
    )
    db.commit()
    return out(plain(obj), 201)


@router.post("/payables/{payable_id}/credits")
def record_credit(
    business_id,
    payable_id,
    payload: CreditInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager")
    p = owned(db, Payable, payable_id, business_id)
    r = owned(db, GoodsReceipt, payload.return_id, business_id)
    db.scalar(select(GoodsReceipt).where(GoodsReceipt.id==r.id).with_for_update())
    if payload.date>today(): raise HTTPException(422,'Credit date cannot be in the future')
    o = get_order(db, business_id, r.order_id, request.state.branch_ids)
    if r.kind != "return" or o.supplier_id != p.supplier_id:
        raise HTTPException(422, "Credit must reference a return to this supplier")
    max_credit = sum((dec(l["accepted"]) * dec(l["cash_unit"]) for l in r.lines), ZERO)
    used = sum(
        (
            c.amount
            for c in rows(db, SupplierCredit, business_id)
            if c.return_id == r.id
        ),
        ZERO,
    )
    if (
        payload.amount + used > max_credit
        or payload.amount > payable_view(db, p)["outstanding"]
    ):
        raise HTTPException(422, "Credit exceeds return value or payable balance")
    changed = db.execute(
        update(Payable)
        .where(Payable.id == p.id, Payable.version == payload.version)
        .values(version=Payable.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Payable changed; reload")
    c = SupplierCredit(
        business_id=business_id,
        branch_id=p.branch_id,
        payable_id=p.id,
        **payload.model_dump(exclude={"version"}),
    )
    db.add(c)
    audit(
        db,
        business_id,
        user.id,
        "credit.recorded",
        p.id,
        {"reference": payload.reference},
    )
    db.commit()
    return {"ok": True}


@router.get("/transfers", response_model=Page)
def transfers(
    business_id,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str = "",
    user=Depends(context),
    db=Depends(get_db),
):
    return out(
        paged(
            [
                plain(t)
                for t in sorted(
                    rows(db, Transfer, business_id),
                    key=lambda t: t.created,
                    reverse=True,
                )
            ],
            page,
            page_size,
            q,
        )
    )


@router.post("/transfers")
def create_transfer(
    business_id,
    payload: TransferInput,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager")
    source = one_branch(request)
    owned(db, Branch, payload.destination_id, business_id)
    if source == payload.destination_id:
        raise HTTPException(422, "Choose a different destination")
    if len(set(l.product_id for l in payload.lines)) != len(payload.lines):
        raise HTTPException(422, "Choose each product once")
    for l in payload.lines:
        owned(db, Product, l.product_id, business_id)
    t = Transfer(
        business_id=business_id,
        branch_id=source,
        destination_id=payload.destination_id,
        number="TR-" + uid()[:7].upper(),
        lines=[
            l.model_dump(mode="json") | {"received": "0", "shortage": "0"}
            for l in payload.lines
        ],
        history=[],
    )
    db.add(t)
    db.flush()
    audit(db, business_id, user.id, "transfer.requested", t.id)
    db.commit()
    return out(plain(t), 201)


@router.get("/transfers/{transfer_id}")
def transfer_detail(
    business_id,
    transfer_id,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    return out(plain(owned(db, Transfer, transfer_id, business_id)))


@router.post("/transfers/{transfer_id}/transition")
def change_transfer(
    business_id,
    transfer_id,
    payload: Transition,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    t = owned(db, Transfer, transfer_id, business_id)
    transfer_action(db, business_id, t, payload, request, user)
    db.commit()
    return {"ok": True}


@router.post("/transfers/{transfer_id}/receive")
def receive_transfer(
    business_id,
    transfer_id,
    payload: TransferReceive,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    require_role(request, "owner", "manager", "receiving")
    t = owned(db, Transfer, transfer_id, business_id)
    if db.get(Business, business_id).mode != "standalone":
        raise HTTPException(409, "Stock is managed by Zoho")
    if t.destination_id != one_branch(request):
        raise HTTPException(
            403, "Select the destination branch to receive this transfer"
        )
    digest = fingerprint(payload.model_dump(mode="json"))
    previous = next(
        (h for h in t.history if h.get("key") == payload.idempotency_key), None
    )
    if previous:
        if previous["hash"] != digest:
            raise HTTPException(409, "Idempotency key reused")
        return {"ok": True}
    if t.status not in ("dispatched", "partially_received"):
        raise HTTPException(409, "Transfer is not in transit")
    if payload.shortages:
        require_role(request, "owner", "manager")
        if not payload.reason.strip():
            raise HTTPException(422, "Shortage reconciliation reason required")
    changed = db.execute(
        update(Transfer)
        .where(Transfer.id == t.id, Transfer.version == payload.version)
        .values(version=Transfer.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Transfer changed; reload")
    received = {l.product_id: l.qty for l in payload.lines}
    shortages = {l.product_id: l.qty for l in payload.shortages}
    lines = []
    if len(received) != len(payload.lines):
        raise HTTPException(422, "Duplicate product")
    if any(k not in [l["product_id"] for l in t.lines] for k in received | shortages):
        raise HTTPException(422, "Product not in transfer")
    for l in t.lines:
        qty = received.get(l["product_id"], ZERO)
        short = shortages.get(l["product_id"], ZERO)
        if qty + short + dec(l["received"]) + dec(l["shortage"]) > dec(l["qty"]):
            raise HTTPException(
                422, "Received and reconciled quantities exceed dispatch"
            )
        if qty:
            stock_adjust(
                db,
                business_id,
                t.destination_id,
                l["product_id"],
                qty,
                "transfer_receipt",
                t.number,
            )
        lines.append(
            l
            | {
                "received": str(dec(l["received"]) + qty),
                "shortage": str(dec(l["shortage"]) + short),
            }
        )
    t.lines = lines
    t.status = (
        "received"
        if all(dec(l["received"]) + dec(l["shortage"]) == dec(l["qty"]) for l in lines)
        else "partially_received"
    )
    t.history = t.history + [
        {
            "action": "receive",
            "key": payload.idempotency_key,
            "hash": digest,
            "reason": payload.reason,
            "at": now().isoformat(),
            "actor": user.id,
        }
    ]
    audit(
        db,
        business_id,
        user.id,
        "transfer.received",
        t.id,
        {"shortages": [l.model_dump(mode="json") for l in payload.shortages]},
    )
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def notifications(
    business_id, request: Request, user=Depends(context), db=Depends(get_db)
):
    ensure_payables(db, business_id)
    refresh_notifications(db, business_id, request.state.branch_ids)
    db.commit()
    return out(
        [
            plain(n) | {"read": user.id in n.read_by}
            for n in sorted(
                rows(db, Notification, business_id),
                key=lambda n: n.created,
                reverse=True,
            )
        ]
    )


@router.post("/notifications/{notification_id}/read")
def read_notification(
    business_id,
    notification_id,
    request: Request,
    user=Depends(context),
    db=Depends(get_db),
):
    n = owned(db, Notification, notification_id, business_id)
    n.read_by = list(set(n.read_by + [user.id]))
    db.commit()
    return {"ok": True}


@router.get("/reports")
def reports(
    business_id,
    request: Request,
    start: str = "",
    end: str = "",
    supplier_id: str = "",
    product_id: str = "",
    user=Depends(context),
    db=Depends(get_db),
):
    ensure_payables(db, business_id)
    transactions = [
        t
        for t in rows(db, Transaction, business_id)
        if t.active
        and (not start or str(t.date) >= start)
        and (not end or str(t.date) <= end)
        and (not supplier_id or t.supplier_id == supplier_id)
    ]
    txs = {t.id: t for t in transactions}
    lines = [
        l
        for l in rows(db, Line, business_id)
        if l.transaction_id in txs and (not product_id or l.product_id == product_id)
    ]
    monthly = defaultdict(Decimal)
    purchase_rows = []
    purchase_total = ZERO
    products = {p.id: p for p in rows(db, Product, business_id)}
    suppliers = {s.id: s.name for s in rows(db, Supplier, business_id)}
    for l in lines:
        t = txs[l.transaction_id]
        if t.kind != "purchase":
            continue
        value = l.qty * l.cash_unit
        purchase_total += value
        monthly[str(t.date)[:7]] += value
        purchase_rows.append(
            {
                "date": t.date,
                "invoice": t.invoice_no,
                "branch_id": t.branch_id,
                "supplier": suppliers.get(t.supplier_id, ""),
                "product": products[l.product_id].name,
                "qty": l.qty,
                "economic_unit": l.unit_cost,
                "cash_total": value,
                "margin_pct": (products[l.product_id].sell_price - l.unit_cost)
                / products[l.product_id].sell_price
                * 100
                if products[l.product_id].sell_price
                else None,
            }
        )
    inventory_rows = []
    forecast_rows = []
    for b in branch_list(db, business_id, request):
        with at_branch(db, b.id):
            fs = forecasts(db, db.get(Business, business_id))
            forecast_rows.extend(fs)
            for s in inventory(db, db.get(Business, business_id)):
                f = next(f for f in fs if f["product_id"] == s["product_id"])
                cover = (
                    dec(s["available"]) / dec(f["daily_demand"])
                    if f["daily_demand"] and dec(f["daily_demand"]) > 0
                    else None
                )
                inventory_rows.append(
                    s
                    | {
                        "branch_id": b.id,
                        "branch_name": b.name,
                        "days_cover": cover,
                        "risk": "stockout"
                        if dec(s["available"]) <= 0
                        else "excess"
                        if cover
                        and cover
                        > db.get(Business, business_id).settings.get("max_cover", 30)
                        else "reorder"
                        if cover is not None and cover < 7
                        else "healthy",
                    }
                )
    payable_rows = [
        payable_view(db, p)
        for p in rows(db, Payable, business_id)
        if (not supplier_id or p.supplier_id == supplier_id)
    ]
    commitments = sum(
        (b.committed for b in branch_list(db, business_id, request)), ZERO
    )
    db.commit()
    return out(
        {
            "purchases": purchase_rows,
            "purchase_total": purchase_total,
            "spend_trend": [
                {"month": k, "amount": v} for k, v in sorted(monthly.items())
            ],
            "stock": inventory_rows,
            "payables": payable_rows,
            "outstanding": sum((p["outstanding"] for p in payable_rows), ZERO),
            "overdue": sum(
                (p["outstanding"] for p in payable_rows if p["status"] == "overdue"),
                ZERO,
            ),
            "commitments": commitments,
            "forecasts": forecast_rows,
            "note": "Purchase spend uses verified invoice lines. Commitments and recommendation benefits are separate.",
        }
    )


@router.get("/reports/export")
def report_export(
    business_id,
    request: Request,
    start: str = "",
    end: str = "",
    supplier_id: str = "",
    product_id: str = "",
    user=Depends(context),
    db=Depends(get_db),
):
    result = reports(
        business_id, request, start, end, supplier_id, product_id, user, db
    )
    payload = json.loads(result.body)
    stream = io.StringIO()
    fields = [
        "date",
        "invoice",
        "branch_id",
        "supplier",
        "product",
        "qty",
        "economic_unit",
        "cash_total",
        "margin_pct",
    ]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for r in payload["purchases"]:
        writer.writerow({k: safe_csv(r.get(k, "")) for k in fields})
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="purchase-report.csv"'},
    )
