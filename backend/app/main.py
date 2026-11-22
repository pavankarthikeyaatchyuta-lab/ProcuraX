from .db import today
import csv
import io
import os
import json
import secrets
import hashlib
from pathlib import Path
from datetime import date, timedelta, datetime
from decimal import Decimal
from urllib.parse import urlencode
import httpx
import pyotp
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from sqlalchemy import select, update, delete, text
from sqlalchemy.exc import IntegrityError
from .db import get_db, now, uid
from .models import *
from .schemas import *
from .domain import (
    owned,
    rows,
    plain,
    audit,
    inventory,
    forecasts,
    scorecards,
    alerts,
    matching,
    recommend,
    validate_basket,
    dec,
    profit_leak_analysis,
    local_demand_analysis,
    ai_assistant_query,
    unified_decision_summary,
)
from .security import hasher, encrypt, decrypt, current, access, owner
from .imports import TEMPLATES, read_table, commit_import, einvoice, post_transaction
from .integrations import REGIONS, SCOPES, Zoho, enqueue, run_job, scan_file
from .metrics import quality_metrics
from .realtime import manager, RealtimeEvent

app = FastAPI(title="Vyaya Procurement Intelligence", version="1.0.0")
from .operations_api import router as operations_router

app.include_router(operations_router)
PREFIX = "/api/v1"
DATA = Path(os.getenv("DOCUMENT_DIR", "./data/documents")).resolve()
DATA.mkdir(parents=True, exist_ok=True)


def out(value, status=200):
    return JSONResponse(
        jsonable_encoder(value, custom_encoder={Decimal: str}), status_code=status
    )


@app.middleware("http")
async def boundaries(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        allowed_raw = os.getenv(
            "APP_ORIGIN",
            "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001",
        )
        allowed = [o.strip() for o in allowed_raw.split(",") if o.strip()]
        if origin and origin not in allowed:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        size = int(request.headers.get("content-length", "0"))
        if size > 12_000_000:
            return JSONResponse({"detail": "Upload limit is 10 MB"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(
        {
            "detail": "A matching record already exists, or this record is referenced elsewhere"
        },
        status_code=409,
    )


@app.get(PREFIX + "/health")
def health(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    redis_status = "local background tasks"
    if os.getenv("REDIS_URL"):
        from redis import Redis

        try:
            Redis.from_url(os.environ["REDIS_URL"]).ping()
            redis_status = "connected"
        except Exception:
            redis_status = "unavailable"
    return {
        "database": "connected",
        "queue": redis_status,
        "zoho_configured": bool(os.getenv("ZOHO_CLIENT_ID")),
        "ocr_configured": bool(os.getenv("GOOGLE_DOCUMENT_AI_PROCESSOR")),
        "scanner_configured": bool(os.getenv("CLAMAV_HOST")),
    }


@app.post(PREFIX + "/auth/login")
def login(payload: Login, request: Request, response: Response, db=Depends(get_db)):
    # Database-backed throttle survives restarts and spans API processes.
    key = hashlib.sha256(
        (request.client.host + "|" + payload.email.lower()).encode()
    ).hexdigest()
    from .models import LoginThrottle

    throttle = db.get(LoginThrottle, key)
    if throttle and throttle.until > now() and throttle.count >= 8:
        raise HTTPException(429, "Too many attempts; wait 15 minutes")
    if not throttle:
        throttle = LoginThrottle(id=key, count=0, until=now() + timedelta(minutes=15))
        db.add(throttle)
    if throttle.until < now():
        throttle.count = 0
        throttle.until = now() + timedelta(minutes=15)
    throttle.count += 1
    db.commit()
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    valid = False
    try:
        valid = hasher.verify(user.password if user else DUMMY_HASH, payload.password)
    except Exception:
        pass
    if not valid or not user:
        raise HTTPException(401, "Invalid email or password")
    if user.mfa_enabled:
        totp = pyotp.TOTP(decrypt(user.totp_secret))
        step = int(datetime.now().timestamp()) // 30
        if not totp.verify(payload.code, valid_window=0):
            raise HTTPException(401, "Authenticator code required or invalid")
        changed = db.execute(
            update(User)
            .where(User.id == user.id, User.last_totp < step)
            .values(last_totp=step)
        ).rowcount
        if not changed:
            raise HTTPException(401, "Code already used; wait for the next code")
    throttle.count = 0
    token = secrets.token_urlsafe(40)
    csrf = secrets.token_urlsafe(32)
    db.add(
        Session(
            id=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            csrf=csrf,
            expires=now() + timedelta(hours=12),
            mfa_verified=user.mfa_enabled,
        )
    )
    db.commit()
    response.set_cookie(
        "procure_session",
        token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false") == "true",
        samesite="lax",
        max_age=43200,
        path="/",
    )
    return {"csrf": csrf, "email": user.email}


DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


@app.get(PREFIX + "/auth/me")
def me(request: Request, user=Depends(current), db=Depends(get_db)):
    memberships = db.scalars(
        select(Membership).where(Membership.user_id == user.id)
    ).all()
    return out(
        {
            "email": user.email,
            "mfa_enabled": user.mfa_enabled,
            "csrf": request.state.session.csrf,
            "businesses": [
                plain(db.get(Business, m.business_id)) | {"role": m.role}
                for m in memberships
            ],
        }
    )


@app.post(PREFIX + "/auth/logout")
def logout(
    request: Request, response: Response, user=Depends(current), db=Depends(get_db)
):
    db.delete(request.state.session)
    db.commit()
    response.delete_cookie("procure_session", path="/")
    return {"ok": True}


@app.post(PREFIX + "/auth/mfa/setup")
def mfa_setup(user=Depends(current), db=Depends(get_db)):
    if user.mfa_enabled:
        raise HTTPException(409, "MFA already enabled")
    secret = pyotp.random_base32()
    user.totp_secret = encrypt(secret)
    db.commit()
    return {
        "secret": secret,
        "uri": pyotp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name="Vyaya"
        ),
    }


@app.post(PREFIX + "/auth/mfa/verify")
def mfa_verify(
    payload: MFA, request: Request, user=Depends(current), db=Depends(get_db)
):
    if not user.totp_secret or not pyotp.TOTP(decrypt(user.totp_secret)).verify(
        payload.code
    ):
        raise HTTPException(422, "Invalid authenticator code")
    user.mfa_enabled = True
    request.state.session.mfa_verified = True
    db.commit()
    return {"ok": True}


@app.post(PREFIX + "/businesses")
def create_business(
    payload: NewBusiness, request: Request, user=Depends(current), db=Depends(get_db)
):
    if not user.mfa_enabled or not request.state.session.mfa_verified:
        raise HTTPException(
            403, "Verify MFA in this session before creating a real business"
        )
    business = Business(name=payload.name)
    db.add(business)
    db.flush()
    db.add(Membership(business_id=business.id, user_id=user.id, role="owner"))
    audit(db, business.id, user.id, "business.created", business.id)
    db.commit()
    return out(plain(business), 201)


B = PREFIX + "/businesses/{business_id}"


@app.get(B + "/overview")
def overview(business_id, user=Depends(access), db=Depends(get_db)):
    business = db.get(Business, business_id)
    stock = inventory(db, business)
    fs = forecasts(db, business)
    bs = rows(db, Basket, business_id)
    accepted = [b for b in bs if b.status in ("approved", "exported", "partial")]
    verified = [d for d in rows(db, Document, business_id) if d.status == "verified"]
    receipts = rows(db, Receipt, business_id)
    realized = Decimal(0)
    realized_count = 0
    for receipt in receipts:
        basket = (
            owned(db, Basket, receipt.basket_id, business_id)
            if receipt.basket_id
            else None
        )
        if basket and receipt.actual_cost is not None:
            for line in basket.lines:
                if (
                    line["product_id"] == receipt.product_id
                    and line["supplier_id"] == receipt.supplier_id
                ):
                    baseline = basket.snapshot.get("baseline_costs", {}).get(
                        receipt.product_id
                    )
                    if baseline is not None:
                        realized += (
                            dec(baseline) - receipt.actual_cost
                        ) * receipt.received_qty
                        realized_count += 1
    payload = {
        "business": plain(business),
        "inventory": stock,
        "forecasts": fs,
        "alerts": alerts(db, business),
        "metrics": {
            "products": len(stock),
            "suppliers": len(rows(db, Supplier, business_id)),
            "review_queue": len(
                [d for d in rows(db, Document, business_id) if d.status != "verified"]
            ),
            "stockouts": sum(dec(s["available"]) <= 0 for s in stock),
            "stockout_rate": sum(dec(s["available"]) <= 0 for s in stock) / len(stock)
            if stock
            else None,
            "baskets": len(bs),
            "acceptance_rate": len(accepted) / len(bs) if bs else None,
            "estimated_contribution": str(
                sum(
                    (
                        dec(l.get("benefit_estimate", 0))
                        for b in accepted
                        for l in b.lines
                    ),
                    Decimal(0),
                )
            ),
            "realized_cost_reduction": str(realized) if realized_count else None,
            "realized_evidence_count": realized_count,
            "verified_documents": len(verified),
            "review_corrections": sum(len(d.versions) > 1 for d in verified),
            "inventory_turns": None,
            "inventory_turns_reason": "Requires consistent historical inventory valuation; not inferred from current stock",
            "alert_usefulness": None,
            "alert_usefulness_reason": "Record alert feedback to build evidence",
        },
        "setup": {
            "catalog": bool(stock),
            "suppliers": bool(rows(db, Supplier, business_id)),
            "stock": any(s["updated"] for s in stock),
            "sales_history": any(f["observed_days"] >= 28 for f in fs),
            "ocr_consent": business.settings.get("ocr_consent", False),
            "zoho": bool(db.get(Integration, business_id)),
        },
    }
    payload["metrics"].update(quality_metrics(db, business))
    return out(payload)


@app.get(B + "/products", response_model=list[ProductView])
@app.get(B + "/workspace/products")
def products(business_id, user=Depends(access), db=Depends(get_db)):
    return [
        ProductView.model_validate(plain(p)) for p in rows(db, Product, business_id)
    ]


@app.post(B + "/products")
def add_product(
    business_id, payload: ProductInput, user=Depends(access), db=Depends(get_db)
):
    p = Product(business_id=business_id, **payload.model_dump())
    db.add(p)
    db.flush()
    audit(db, business_id, user.id, "product.created", p.id)
    db.commit()
    return out(plain(p), 201)


@app.put(B + "/products/{product_id}")
def edit_product(
    business_id,
    product_id,
    payload: ProductInput,
    user=Depends(access),
    db=Depends(get_db),
):
    p = owned(db, Product, product_id, business_id)
    for key, value in payload.model_dump().items():
        setattr(p, key, value)
    audit(db, business_id, user.id, "product.updated", p.id)
    db.commit()
    return out(plain(p))


@app.get(B + "/products/match/suggest")
def suggest(
    business_id,
    text: str,
    supplier_key: str = "",
    user=Depends(access),
    db=Depends(get_db),
):
    return matching(db, business_id, text, supplier_key)


@app.post(B + "/aliases")
def add_alias(
    business_id, payload: AliasInput, user=Depends(access), db=Depends(get_db)
):
    owned(db, Product, payload.product_id, business_id)
    if payload.supplier_key:
        owned(db, Supplier, payload.supplier_key, business_id)
    alias = Alias(business_id=business_id, **payload.model_dump())
    db.add(alias)
    audit(
        db,
        business_id,
        user.id,
        "alias.confirmed",
        payload.product_id,
        payload.model_dump(mode="json"),
    )
    db.commit()
    return {"ok": True}


@app.get(B + "/suppliers")
def suppliers(business_id, user=Depends(access), db=Depends(get_db)):
    return out(scorecards(db, business_id))


@app.post(B + "/suppliers")
def add_supplier(
    business_id, payload: SupplierInput, user=Depends(access), db=Depends(get_db)
):
    obj = Supplier(business_id=business_id, **payload.model_dump())
    db.add(obj)
    db.flush()
    audit(db, business_id, user.id, "supplier.created", obj.id)
    db.commit()
    return out(plain(obj), 201)


@app.post(B + "/suppliers/{supplier_id}/bank")
def bank_change(
    business_id,
    supplier_id,
    payload: BankChange,
    user=Depends(owner),
    db=Depends(get_db),
):
    s = owned(db, Supplier, supplier_id, business_id)
    fingerprint = hashlib.sha256(payload.fingerprint.encode()).hexdigest()
    if (
        s.bank_fingerprint
        and s.bank_fingerprint != fingerprint
        and not payload.verified
    ):
        raise HTTPException(
            409,
            "Bank details changed; independently verify the supplier before confirming",
        )
    s.bank_fingerprint = fingerprint
    audit(db, business_id, user.id, "supplier.bank_verified", s.id)
    db.commit()
    return {"ok": True}


@app.get(B + "/quotes", response_model=list[QuoteView])
def quotes(business_id, user=Depends(access), db=Depends(get_db)):
    return [QuoteView.model_validate(plain(q)) for q in rows(db, Quote, business_id)]


@app.post(B + "/quotes")
def add_quote(
    business_id, payload: QuoteInput, user=Depends(access), db=Depends(get_db)
):
    owned(db, Product, payload.product_id, business_id)
    owned(db, Supplier, payload.supplier_id, business_id)
    values = payload.model_dump()
    values["tiers"] = [t.model_dump(mode="json") for t in payload.tiers]
    q = Quote(business_id=business_id, **values)
    db.add(q)
    db.flush()
    audit(db, business_id, user.id, "quote.created", q.id)
    db.commit()
    return out(plain(q), 201)


@app.get(B + "/price-history")
def price_history(business_id, user=Depends(access), db=Depends(get_db)):
    txs = {
        t.id: t
        for t in rows(db, Transaction, business_id)
        if t.active and t.kind == "purchase"
    }
    return out(
        [
            plain(l)
            | {
                "date": txs[l.transaction_id].date,
                "supplier_id": txs[l.transaction_id].supplier_id,
            }
            for l in rows(db, Line, business_id)
            if l.transaction_id in txs
        ]
    )


@app.get(B + "/inventory", response_model=list[StockView])
def stock(business_id, user=Depends(access), db=Depends(get_db)):
    return [
        StockView.model_validate(v)
        for v in inventory(db, db.get(Business, business_id))
    ]


@app.get(B + "/movements")
def movements(business_id, user=Depends(access), db=Depends(get_db)):
    return out([plain(m) for m in rows(db, Movement, business_id)])


@app.post(B + "/inventory")
def adjust(business_id, payload: StockInput, user=Depends(access), db=Depends(get_db)):
    business = db.get(Business, business_id)
    owned(db, Product, payload.product_id, business_id)
    if business.mode == "zoho":
        raise HTTPException(409, "Zoho is authoritative; make stock changes in Zoho")
    if payload.kind == "opening" and db.scalar(
        select(Movement).where(
            Movement.business_id == business_id,
            Movement.product_id == payload.product_id,
            Movement.kind == "opening",
        )
    ):
        raise HTTPException(409, "Opening balance already exists")
    if payload.kind != "count":
        db.add(
            Movement(
                business_id=business_id,
                product_id=payload.product_id,
                qty=payload.qty,
                kind=payload.kind,
                reason=payload.reason,
            )
        )
    else:
        db.add(
            Stock(
                business_id=business_id,
                product_id=payload.product_id,
                on_hand=payload.qty,
                reserved=payload.reserved,
                on_order=payload.on_order,
                source="count",
            )
        )
    audit(
        db,
        business_id,
        user.id,
        "stock." + payload.kind,
        payload.product_id,
        payload.model_dump(mode="json"),
    )
    db.commit()
    return {"ok": True}


@app.post(B + "/movements/{movement_id}/reverse")
def reverse(
    business_id,
    movement_id,
    payload: StockInput,
    user=Depends(access),
    db=Depends(get_db),
):
    if db.get(Business, business_id).mode != "standalone":
        raise HTTPException(409, "Stock is managed in Zoho")
    move = owned(db, Movement, movement_id, business_id)
    if move.product_id != payload.product_id:
        raise HTTPException(422, "Product does not match movement")
    if move.reversal_of or db.scalar(
        select(Movement).where(Movement.reversal_of == move.id)
    ):
        raise HTTPException(409, "Movement already reversed or is a reversal")
    db.add(
        Movement(
            business_id=business_id,
            product_id=move.product_id,
            transaction_id=move.transaction_id,
            qty=-move.qty,
            kind="reversal",
            reason=payload.reason,
            reversal_of=move.id,
        )
    )
    db.add(
        Movement(
            business_id=business_id,
            product_id=move.product_id,
            transaction_id=move.transaction_id,
            qty=payload.qty,
            kind="replacement",
            reason=payload.reason,
        )
    )
    audit(
        db,
        business_id,
        user.id,
        "movement.corrected",
        move.id,
        payload.model_dump(mode="json"),
    )
    db.commit()
    return {"ok": True}


@app.post(B + "/inventory/authority")
def authority(
    business_id, payload: SwitchMode, user=Depends(owner), db=Depends(get_db)
):
    business = db.get(Business, business_id)
    if payload.mode == business.mode:
        raise HTTPException(409, "Already using this stock authority")
    ids = {p.id for p in rows(db, Product, business_id)}
    if {s.product_id for s in payload.opening} != ids or len(payload.opening) != len(
        ids
    ):
        raise HTTPException(
            422, "Supply one reconciled opening balance for every product"
        )
    if payload.mode == "zoho":
        integration = db.get(Integration, business_id)
        if (
            not integration
            or not integration.last_sync
            or now() - integration.last_sync > timedelta(hours=24)
        ):
            raise HTTPException(409, "Sync Zoho within 24 hours before switching")
        for s in payload.opening:
            from .domain import latest_stock

            snap = latest_stock(db, business_id, s.product_id)
            if not snap or snap.source != "zoho" or snap.on_hand != s.qty:
                raise HTTPException(
                    409, "Reconcile opening quantities with latest Zoho stock"
                )
    changed = db.execute(
        update(Business)
        .where(Business.id == business_id, Business.version == payload.version)
        .values(mode=payload.mode, version=Business.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Business settings changed; reload")
    for s in payload.opening:
        if payload.mode == "standalone":
            current_qty = sum(
                (
                    m.qty
                    for m in rows(db, Movement, business_id)
                    if m.product_id == s.product_id
                ),
                Decimal(0),
            )
            db.add(
                Movement(
                    business_id=business_id,
                    product_id=s.product_id,
                    qty=s.qty - current_qty,
                    kind="authority_opening",
                    reason=payload.reason,
                )
            )
            db.flush()
            db.add(
                Stock(
                    business_id=business_id,
                    product_id=s.product_id,
                    on_hand=s.qty,
                    reserved=s.reserved,
                    on_order=s.on_order,
                    source="authority_opening",
                )
            )
    audit(
        db,
        business_id,
        user.id,
        "authority.switched",
        business_id,
        payload.model_dump(mode="json"),
    )
    db.commit()
    return {"ok": True}


@app.get(B + "/lost-sales")
def lost_sales(business_id, user=Depends(access), db=Depends(get_db)):
    return out([plain(r) for r in rows(db, LostSale, business_id)])


@app.post(B + "/lost-sales")
def add_lost(business_id, payload: LostInput, user=Depends(access), db=Depends(get_db)):
    if payload.product_id:
        owned(db, Product, payload.product_id, business_id)
    if not payload.product_id and not payload.category:
        raise HTTPException(422, "Product or category is required")
    obj = LostSale(business_id=business_id, **payload.model_dump())
    db.add(obj)
    db.commit()
    return {"ok": True}


@app.get(B + "/receipts")
def receipts(business_id, user=Depends(access), db=Depends(get_db)):
    return out([plain(r) for r in rows(db, Receipt, business_id)])


@app.post(B + "/receipts")
def add_receipt(
    business_id, payload: ReceiptInput, user=Depends(access), db=Depends(get_db)
):
    owned(db, Product, payload.product_id, business_id)
    owned(db, Supplier, payload.supplier_id, business_id)
    if payload.basket_id:
        owned(db, Basket, payload.basket_id, business_id)
    if payload.actual < payload.ordered_on or payload.expected < payload.ordered_on:
        raise HTTPException(422, "Receipt dates precede order")
    obj = Receipt(business_id=business_id, **payload.model_dump())
    db.add(obj)
    audit(db, business_id, user.id, "receipt.recorded", payload.supplier_id)
    db.commit()
    return {
        "ok": True,
        "note": "Delivery evidence recorded. Stock receipt must be posted through invoice verification or Zoho.",
    }


@app.get(B + "/forecasts", response_model=list[ForecastView])
def forecast(business_id, user=Depends(access), db=Depends(get_db)):
    return [
        ForecastView.model_validate(v)
        for v in forecasts(db, db.get(Business, business_id))
    ]


@app.get(B + "/alerts")
def get_alerts(business_id, user=Depends(access), db=Depends(get_db)):
    return out(alerts(db, db.get(Business, business_id)))


@app.post(B + "/alerts/feedback")
def alert_feedback(
    business_id, payload: dict, user=Depends(access), db=Depends(get_db)
):
    if payload.get("useful") not in (True, False) or not isinstance(
        payload.get("type"), str
    ):
        raise HTTPException(422, "type and useful are required")
    audit(
        db,
        business_id,
        user.id,
        "alert.feedback",
        str(payload.get("product_id", "")),
        {"type": payload["type"], "useful": payload["useful"]},
    )
    db.commit()
    return {"ok": True}


@app.get(B + "/documents")
def documents(business_id, user=Depends(access), db=Depends(get_db)):
    return out(
        [
            {k: v for k, v in plain(d).items() if k != "path"}
            for d in rows(db, Document, business_id)
        ]
    )


@app.get(B + "/documents/{document_id}/file")
def document_file(business_id, document_id, user=Depends(access), db=Depends(get_db)):
    d = owned(db, Document, document_id, business_id)
    if not Path(d.path).is_file():
        raise HTTPException(410, "Document removed by retention policy")
    return FileResponse(
        d.path, media_type=d.mime, filename=d.name, content_disposition_type="inline"
    )


def schedule(db, job, background):
    db.add(job)
    db.commit()
    try:
        if not enqueue(job.id):
            background.add_task(run_job, job.id)
    except Exception:
        job.status = "failed"
        job.error = "Queue unavailable; restore Redis and retry"
        db.commit()
    return out(plain(job), 202)


@app.post(B + "/documents")
async def upload_document(
    business_id,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user=Depends(access),
    db=Depends(get_db),
):
    business = db.get(Business, business_id)
    content = await file.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(413, "Maximum upload is 10 MB")
    name = Path(file.filename or "invoice").name
    suffix = Path(name).suffix.lower()
    if suffix not in (".pdf", ".png", ".jpg", ".jpeg", ".json"):
        raise HTTPException(415, "Use PDF, PNG, JPEG or e-invoice JSON")
    try:
        scan_file(content)
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(
        select(Document).where(
            Document.business_id == business_id, Document.sha256 == digest
        )
    )
    if existing:
        return out({"id": existing.id, "duplicate": True}, 200)
    extracted = {}
    mime = "application/json"
    if suffix == ".json":
        try:
            extracted = einvoice(json.loads(content))
        except Exception:
            raise HTTPException(422, "Invalid GST e-invoice JSON")
    else:
        if not business.settings.get("ocr_consent"):
            raise HTTPException(
                403,
                "Enable EU OCR processing consent in Settings before uploading images or PDFs",
            )
        if suffix == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise HTTPException(415, "File is not a PDF")
            mime = "application/pdf"
        else:
            from PIL import Image

            try:
                image = Image.open(io.BytesIO(content))
                image.verify()
                if image.format not in ("PNG", "JPEG"):
                    raise ValueError()
                mime = "image/png" if image.format == "PNG" else "image/jpeg"
            except Exception:
                raise HTTPException(415, "Invalid image")
    did = uid()
    path = DATA / business_id / did
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    d = Document(
        id=did,
        business_id=business_id,
        name=name,
        sha256=digest,
        mime=mime,
        path=str(path),
        extracted=extracted,
        status="review" if suffix == ".json" else "queued",
        versions=[{"version": 1, "extracted": extracted}],
    )
    db.add(d)
    audit(db, business_id, user.id, "document.uploaded", d.id)
    db.commit()
    if suffix == ".json":
        return out({"id": d.id, "status": "review"}, 201)
    return schedule(
        db,
        Job(business_id=business_id, kind="ocr", payload={"document_id": d.id}),
        background,
    )


@app.post(B + "/documents/{document_id}/verify")
def verify_document(
    business_id, document_id, payload: Review, user=Depends(access), db=Depends(get_db)
):
    business = db.get(Business, business_id)
    d = owned(db, Document, document_id, business_id)
    owned(db, Supplier, payload.supplier_id, business_id)
    if d.status == "verified":
        raise HTTPException(
            409, "Already verified; correct the recorded transaction explicitly"
        )
    if payload.date > today():
        raise HTTPException(422, "Invoice date cannot be in the future")
    total = sum(
        (
            (l.qty * l.rate - l.discount) * (1 + l.tax_pct / 100) + l.freight
            for l in payload.lines
        ),
        Decimal(0),
    )
    if abs(total - payload.total) > Decimal(".02"):
        raise HTTPException(
            422,
            f"Line arithmetic totals ₹{total:.2f}, not invoice total ₹{payload.total:.2f}; allocate all charges explicitly",
        )
    changed = db.execute(
        update(Document)
        .where(
            Document.id == d.id,
            Document.business_id == business_id,
            Document.version == payload.version,
            Document.status != "verified",
        )
        .values(version=Document.version + 1, status="verified")
    ).rowcount
    if not changed:
        raise HTTPException(409, "Document changed; reload before verifying")
    tx = post_transaction(
        db,
        business,
        source="document",
        source_key=d.sha256,
        kind="purchase",
        invoice_no=payload.invoice_no,
        occurred=payload.date,
        supplier_id=payload.supplier_id,
        total=payload.total,
        lines=payload.lines,
        raw=payload.model_dump(mode="json"),
        actor=user.id,
    )
    d.transaction_id = tx.id
    d.versions = d.versions + [
        {
            "version": payload.version + 1,
            "verified": payload.model_dump(mode="json"),
            "actor": user.id,
            "at": now().isoformat(),
        }
    ]
    audit(
        db, business_id, user.id, "document.verified", d.id, {"transaction_id": tx.id}
    )
    db.commit()
    return {"transaction_id": tx.id}


@app.get(B + "/imports/templates/{kind}")
def template(business_id, kind, user=Depends(access)):
    if kind not in TEMPLATES:
        raise HTTPException(404, "Template not found")
    return Response(
        ",".join(TEMPLATES[kind]) + "\n",
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'},
    )


@app.post(B + "/documents/{document_id}/correct")
def correct_document(
    business_id, document_id, payload: Review, user=Depends(access), db=Depends(get_db)
):
    business = db.get(Business, business_id)
    document = owned(db, Document, document_id, business_id)
    if document.status != "verified" or not document.transaction_id:
        raise HTTPException(409, "Verify the invoice before correcting it")
    original = owned(db, Transaction, document.transaction_id, business_id)
    if original.source == "zoho":
        raise HTTPException(
            409,
            "This evidence links to Zoho. Correct the authoritative bill in Zoho and sync it.",
        )
    owned(db, Supplier, payload.supplier_id, business_id)
    total = sum(
        (
            (l.qty * l.rate - l.discount) * (1 + l.tax_pct / 100) + l.freight
            for l in payload.lines
        ),
        Decimal(0),
    )
    if abs(total - payload.total) > Decimal(".02") or payload.date > today():
        raise HTTPException(
            422, "Reconcile invoice arithmetic and date before correction"
        )
    changed = db.execute(
        update(Document)
        .where(
            Document.id == document_id,
            Document.business_id == business_id,
            Document.version == payload.version,
            Document.status == "verified",
        )
        .values(version=Document.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Document changed; reload before correcting")
    payable = db.scalar(select(Payable).where(Payable.transaction_id == original.id))
    if payable and (
        db.scalar(select(Payment).where(Payment.payable_id == payable.id))
        or db.scalar(
            select(SupplierCredit).where(SupplierCredit.payable_id == payable.id)
        )
    ):
        raise HTTPException(
            409,
            "This invoice has financial allocations; preserve the invoice and reconcile with supplier credit evidence",
        )
    if db.scalar(
        select(InvoiceAllocation).where(
            InvoiceAllocation.invoice_line_id.in_(
                select(Line.id).where(Line.transaction_id == original.id)
            )
        )
    ):
        raise HTTPException(
            409,
            "This invoice is matched to received goods; reconcile order and credit evidence before correcting it",
        )
    original.active = False
    original.version += 1
    db.flush()
    if business.mode == "standalone":
        movements = [
            m
            for m in rows(db, Movement, business_id)
            if m.transaction_id == original.id
        ]
        reversed_ids = {m.reversal_of for m in movements if m.reversal_of}
        for movement in movements:
            if not movement.reversal_of and movement.id not in reversed_ids:
                db.add(
                    Movement(
                        business_id=business_id,
                        product_id=movement.product_id,
                        transaction_id=original.id,
                        qty=-movement.qty,
                        kind="invoice_reversal",
                        reason=f"Invoice correction v{payload.version + 1}",
                        reversal_of=movement.id,
                    )
                )
    replacement = post_transaction(
        db,
        business,
        source="document_correction",
        source_key=f"{document_id}:{payload.version + 1}",
        kind="purchase",
        invoice_no=payload.invoice_no,
        occurred=payload.date,
        supplier_id=payload.supplier_id,
        total=payload.total,
        lines=payload.lines,
        raw=payload.model_dump(mode="json"),
        actor=user.id,
    )
    document.transaction_id = replacement.id
    document.versions = document.versions + [
        {
            "version": payload.version + 1,
            "verified": payload.model_dump(mode="json"),
            "actor": user.id,
            "at": now().isoformat(),
            "corrects_transaction": original.id,
        }
    ]
    audit(
        db,
        business_id,
        user.id,
        "document.corrected",
        document_id,
        {
            "original_transaction": original.id,
            "replacement_transaction": replacement.id,
        },
    )
    db.commit()
    return {"transaction_id": replacement.id}


@app.post(B + "/imports/preview")
async def preview(
    business_id,
    kind: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(access),
    db=Depends(get_db),
):
    if kind not in TEMPLATES:
        raise HTTPException(422, "Unknown import type")
    content = await file.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(413, "Maximum upload is 10 MB")
    try:
        scan_file(content)
        table = read_table(content, file.filename or "")
        if not table or len(table) > 10000:
            raise ValueError("Provide 1–10,000 rows")
    except Exception as exc:
        raise HTTPException(422, str(exc)[:300])
    job = Job(
        business_id=business_id,
        kind="import",
        status="preview",
        payload={"import_kind": kind, "rows": table},
    )
    db.add(job)
    db.commit()
    return out(
        {
            "id": job.id,
            "columns": list(table[0]),
            "fields": TEMPLATES[kind],
            "preview": table[:20],
            "total_rows": len(table),
            "mapping": {f: f for f in TEMPLATES[kind] if f in table[0]},
        }
    )


@app.post(B + "/imports/{job_id}/commit")
def import_commit(
    business_id, job_id, payload: ImportCommit, user=Depends(access), db=Depends(get_db)
):
    job = owned(db, Job, job_id, business_id)
    if job.kind != "import":
        raise HTTPException(422, "Not a tabular import")
    if job.status == "completed":
        return job.result
    if job.status != "preview":
        raise HTTPException(409, "Import is not ready")
    result = commit_import(
        db, db.get(Business, business_id), job, payload.mapping, user.id
    )
    db.commit()
    return result


@app.get(B + "/jobs")
def jobs(business_id, user=Depends(access), db=Depends(get_db)):
    return out(
        [
            {k: v for k, v in plain(j).items() if k != "payload"}
            for j in sorted(
                rows(db, Job, business_id), key=lambda j: j.created, reverse=True
            )[:100]
        ]
    )


@app.post(B + "/jobs/{job_id}/retry")
def retry_job(
    business_id,
    job_id,
    background: BackgroundTasks,
    user=Depends(owner),
    db=Depends(get_db),
):
    job = owned(db, Job, job_id, business_id)
    if job.status != "failed" or job.kind == "import":
        raise HTTPException(409, "Only failed processing jobs can be retried")
    job.status = "queued"
    return schedule(db, job, background)


@app.get(B + "/baskets", response_model=list[BasketView])
def baskets(business_id, user=Depends(access), db=Depends(get_db)):
    return [
        BasketView.model_validate(
            plain(b)
            | {
                "orders": [
                    plain(a)
                    for a in rows(db, OrderAttempt, business_id)
                    if a.basket_id == b.id
                ]
            }
        )
        for b in sorted(
            rows(db, Basket, business_id), key=lambda b: b.created, reverse=True
        )
    ]


@app.post(B + "/baskets")
def make_basket(
    business_id, payload: NewBasket, user=Depends(owner), db=Depends(get_db)
):
    business = db.get(Business, business_id)
    lines, snapshot = recommend(db, business, payload.budget)
    txs = {
        t.id: t
        for t in rows(db, Transaction, business_id)
        if t.active and t.kind == "purchase"
    }
    baseline = {}
    for l in sorted(
        [l for l in rows(db, Line, business_id) if l.transaction_id in txs],
        key=lambda l: txs[l.transaction_id].date,
    ):
        baseline[l.product_id] = str(l.unit_cost)
    snapshot["baseline_costs"] = baseline
    basket = Basket(
        business_id=business_id, budget=payload.budget, lines=lines, snapshot=snapshot
    )
    db.add(basket)
    db.flush()
    audit(db, business_id, user.id, "basket.created", basket.id)
    db.commit()
    return out(plain(basket), 201)


@app.put(B + "/baskets/{basket_id}")
def edit_basket(
    business_id, basket_id, payload: BasketEdit, user=Depends(owner), db=Depends(get_db)
):
    basket = owned(db, Basket, basket_id, business_id)
    if basket.status != "draft":
        raise HTTPException(409, "Only draft baskets can be edited")
    lines, total, errors = validate_basket(
        db,
        db.get(Business, business_id),
        [l.model_dump(mode="json") for l in payload.lines],
        basket.budget,
    )
    if errors:
        raise HTTPException(422, errors)
    changed = db.execute(
        update(Basket)
        .where(
            Basket.id == basket_id,
            Basket.business_id == business_id,
            Basket.version == payload.version,
            Basket.status == "draft",
        )
        .values(lines=lines, version=Basket.version + 1, feedback=payload.feedback)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Basket changed; reload")
    audit(
        db, business_id, user.id, "basket.edited", basket_id, {"cash_spend": str(total)}
    )
    db.commit()
    return {"ok": True}


@app.post(B + "/baskets/{basket_id}/approve")
def approve(
    business_id,
    basket_id,
    payload: Approval,
    background: BackgroundTasks,
    user=Depends(owner),
    db=Depends(get_db),
):
    basket = owned(db, Basket, basket_id, business_id)
    business = db.get(Business, business_id)
    if payload.action == "reject":
        if not payload.feedback.strip():
            raise HTTPException(422, "Rejection reason required")
        status = "rejected"
    else:
        if payload.action == "approve" and basket.status != "draft":
            raise HTTPException(409, "Only draft baskets can be approved")
        if payload.action == "create_zoho_drafts" and basket.status not in (
            "approved",
            "partial",
        ):
            raise HTTPException(409, "Approve the basket before creating drafts")
        if not basket.lines:
            raise HTTPException(422, "Basket has no lines")
        lines, total, errors = validate_basket(
            db, business, basket.lines, basket.budget
        )
        stocks = {s["product_id"]: s for s in inventory(db, business)}
        for line in lines:
            if not line["price_confirmed"]:
                errors.append(
                    f"{line['name']}: confirm proposed supplier price, including expired/historical quotes"
                )
            if stocks[line["product_id"]]["stale"]:
                errors.append(f"{line['name']}: refresh stock within 24 hours")
        if payload.action == "create_zoho_drafts" and business.mode != "zoho":
            errors.append("Switch to reconciled Zoho stock before external ordering")
        if errors:
            raise HTTPException(422, errors)
        if any(
            dec(a["cash_spend"]) != dec(b["cash_spend"])
            for a, b in zip(lines, basket.lines)
        ):
            raise HTTPException(409, "Prices changed; edit and reconfirm basket")
        status = "approved" if payload.action == "approve" else "exporting"
    snapshot = dict(basket.snapshot)
    if payload.action == "approve":
        snapshot["approved_inputs"] = jsonable_encoder(
            {
                "settings": business.settings,
                "quotes": [
                    plain(owned(db, Quote, l["quote_id"], business_id))
                    for l in basket.lines
                ],
                "inventory": inventory(db, business),
                "lines": basket.lines,
                "approved_at": now(),
            },
            custom_encoder={Decimal: str},
        )
    changed = db.execute(
        update(Basket)
        .where(
            Basket.id == basket_id,
            Basket.business_id == business_id,
            Basket.version == payload.version,
        )
        .values(
            status=status,
            feedback=payload.feedback,
            snapshot=snapshot,
            version=Basket.version + 1,
        )
    ).rowcount
    if not changed:
        raise HTTPException(409, "Basket changed; reload")
    audit(
        db,
        business_id,
        user.id,
        "basket." + payload.action,
        basket_id,
        {"version": payload.version, "feedback": payload.feedback},
    )
    db.commit()
    if payload.action == "create_zoho_drafts":
        return schedule(
            db,
            Job(
                business_id=business_id,
                kind="zoho_drafts",
                payload={"basket_id": basket_id},
            ),
            background,
        )
    return {"ok": True}


@app.get(B + "/baskets/{basket_id}/export")
def export_basket(business_id, basket_id, user=Depends(access), db=Depends(get_db)):
    basket = owned(db, Basket, basket_id, business_id)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(
        [
            "product",
            "supplier_id",
            "quantity_base_units",
            "economic_unit_cost",
            "cash_unit_cost",
            "cash_spend",
            "status",
        ]
    )
    for l in basket.lines:
        writer.writerow(
            [
                safe_csv(l["name"]),
                l["supplier_id"],
                l["qty"],
                l["unit_cost"],
                l["cash_unit"],
                l["cash_spend"],
                basket.status,
            ]
        )
    audit(db, business_id, user.id, "basket.exported_csv", basket_id)
    db.commit()
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="basket-{basket_id[:8]}.csv"'
        },
    )


def safe_csv(value):
    return (
        "'" + str(value)
        if str(value).startswith(("=", "+", "-", "@", "\t", "\r"))
        else value
    )


@app.put(B + "/settings")
def settings(business_id, payload: Settings, user=Depends(owner), db=Depends(get_db)):
    values = payload.model_dump(exclude={"version"})
    changed = db.execute(
        update(Business)
        .where(Business.id == business_id, Business.version == payload.version)
        .values(settings=values, version=Business.version + 1)
    ).rowcount
    if not changed:
        raise HTTPException(409, "Settings changed; reload")
    audit(db, business_id, user.id, "settings.updated", business_id, values)
    db.commit()
    return {"ok": True}


@app.post(B + "/memberships")
def add_member(
    business_id, payload: MemberInput, user=Depends(owner), db=Depends(get_db)
):
    if len(payload.password) < 12:
        raise HTTPException(422, "Use at least 12 characters")
    email = payload.email.strip().lower()
    member = db.scalar(select(User).where(User.email == email))
    if member:
        raise HTTPException(
            409,
            "User exists; use the local admin CLI to grant membership without changing their password",
        )
    member = User(email=email, password=hasher.hash(payload.password))
    db.add(member)
    db.flush()
    db.add(Membership(business_id=business_id, user_id=member.id, role=payload.role))
    audit(db, business_id, user.id, "member.created", member.id, {"role": payload.role})
    db.commit()
    return {"ok": True}


@app.get(B + "/audit")
def get_audit(business_id, user=Depends(access), db=Depends(get_db)):
    events = [a for a in rows(db, Audit, business_id) if a.actor != "seed"]
    return out(
        [
            plain(a)
            for a in sorted(events, key=lambda a: a.at, reverse=True)[:500]
        ]
    )


@app.get(B + "/export")
def export_business(business_id, user=Depends(owner), db=Depends(get_db)):
    classes = [
        Product,
        Supplier,
        Quote,
        Alias,
        Transaction,
        Line,
        Movement,
        Stock,
        LostSale,
        Receipt,
        Basket,
        OrderAttempt,
        Audit,
    ]
    payload = {
        cls.__tablename__: [plain(r) for r in rows(db, cls, business_id)]
        for cls in classes
    }
    payload["business"] = plain(db.get(Business, business_id))
    payload["documents"] = [
        {k: v for k, v in plain(d).items() if k != "path"}
        for d in rows(db, Document, business_id)
    ]
    audit(db, business_id, user.id, "business.exported", business_id)
    db.commit()
    return out(payload)


@app.delete(B)
def delete_business(
    business_id, confirmation: str, user=Depends(owner), db=Depends(get_db)
):
    business = db.get(Business, business_id)
    db.info.pop("branch_ids", None)
    if confirmation != business.name:
        raise HTTPException(422, "Business name confirmation does not match")
    if any(
        j.status in ("running", "queued") and j.kind != "import"
        for j in rows(db, Job, business_id)
    ):
        raise HTTPException(409, "Wait for active processing jobs before deletion")
    for d in rows(db, Document, business_id):
        Path(d.path).unlink(missing_ok=True)
    # Delete dependent rows in FK order; audit remains append-only until owner deletion.
    for cls in [
        Notification,
        ApprovalRequest,
        Payment,
        SupplierCredit,
        InvoiceAllocation,
        GoodsReceipt,
        OrderLine,
        PurchaseOrder,
        Transfer,
        Payable,
        BranchProduct,
        BranchGrant,
        RFQ,
        OrderAttempt,
        Document,
        Line,
        Movement,
        Stock,
        Alias,
        Quote,
        Receipt,
        LostSale,
        Basket,
        Transaction,
        Product,
        Supplier,
        Job,
        Integration,
        OAuthState,
        Membership,
        Audit,
        Branch,
    ]:
        db.execute(delete(cls).where(cls.business_id == business_id))
    db.delete(business)
    db.commit()
    return {
        "ok": True,
        "note": "Active data deleted. Offline backups expire under the documented backup policy.",
    }


@app.get(B + "/zoho")
def integration_status(business_id, user=Depends(owner), db=Depends(get_db)):
    i = db.get(Integration, business_id)
    return out(
        {k: v for k, v in plain(i).items() if k != "refresh_token"}
        if i
        else {"status": "disconnected"}
    )


@app.get(B + "/zoho/connect")
def connect(
    business_id,
    request: Request,
    region: str = "in",
    user=Depends(owner),
    db=Depends(get_db),
):
    if region not in REGIONS:
        raise HTTPException(422, "Unsupported Zoho region")
    if not os.getenv("ZOHO_CLIENT_ID"):
        raise HTTPException(
            503, "Configure ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET first"
        )
    state = secrets.token_urlsafe(32)
    # Bind state to the authenticated session, business and region; consume once.
    db.add(
        OAuthState(
            id=hashlib.sha256(state.encode()).hexdigest(),
            business_id=business_id,
            session_id=request.state.session.id,
            region=region,
            expires=now() + timedelta(minutes=10),
        )
    )
    db.commit()
    url = f"https://{REGIONS[region][0]}/oauth/v2/auth?" + urlencode(
        {
            "scope": SCOPES,
            "client_id": os.environ["ZOHO_CLIENT_ID"],
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "redirect_uri": os.getenv(
                "ZOHO_REDIRECT_URI", "http://localhost:3000/api/v1/zoho/callback"
            ),
            "state": state,
        }
    )
    return {"url": url}


@app.get(PREFIX + "/zoho/callback")
def oauth_callback(
    state: str,
    request: Request,
    code: str = "",
    error: str = "",
    user=Depends(current),
    db=Depends(get_db),
):
    hashed = hashlib.sha256(state.encode()).hexdigest()
    saved = db.get(OAuthState, hashed)
    if (
        not saved
        or saved.expires < now()
        or saved.session_id != request.state.session.id
    ):
        raise HTTPException(403, "OAuth state expired or invalid")
    membership = db.scalar(
        select(Membership).where(
            Membership.business_id == saved.business_id,
            Membership.user_id == user.id,
            Membership.role == "owner",
        )
    )
    if not membership:
        raise HTTPException(403, "Owner required")
    bid, region = saved.business_id, saved.region
    db.delete(saved)
    db.commit()
    if error or not code:
        raise HTTPException(400, "Zoho authorization was not granted")
    try:
        response = httpx.post(
            f"https://{REGIONS[region][0]}/oauth/v2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": os.environ["ZOHO_CLIENT_ID"],
                "client_secret": os.environ["ZOHO_CLIENT_SECRET"],
                "redirect_uri": os.getenv(
                    "ZOHO_REDIRECT_URI", "http://localhost:3000/api/v1/zoho/callback"
                ),
                "code": code,
            },
            timeout=30,
        )
        response.raise_for_status()
        token = response.json().get("refresh_token")
        if not token:
            raise ValueError()
    except Exception:
        raise HTTPException(502, "Zoho token exchange failed; reconnect")
    i = db.get(Integration, bid)
    if not i:
        i = Integration(business_id=bid)
        db.add(i)
    i.region = region
    i.refresh_token = encrypt(token)
    i.status = "choose_organization"
    audit(db, bid, user.id, "zoho.connected", bid)
    db.commit()
    return RedirectResponse("/?connected=zoho")


@app.get(B + "/zoho/organizations")
def organizations(business_id, user=Depends(owner), db=Depends(get_db)):
    i = db.get(Integration, business_id)
    if not i:
        raise HTTPException(409, "Connect Zoho first")
    z = Zoho(i)
    try:
        return z.call("GET", "organizations").get("organizations", [])
    except Exception:
        raise HTTPException(502, "Could not fetch Zoho organizations; check connection")
    finally:
        z.close()


@app.post(B + "/zoho/organization")
def choose_org(
    business_id, payload: OrganizationInput, user=Depends(owner), db=Depends(get_db)
):
    i = db.get(Integration, business_id)
    if not i:
        raise HTTPException(409, "Connect Zoho first")
    if i.organization_id and i.organization_id != payload.organization_id:
        raise HTTPException(
            409, "Create a separate business for a different Zoho organization"
        )
    z = Zoho(i)
    try:
        allowed = z.call("GET", "organizations").get("organizations", [])
    except Exception:
        raise HTTPException(502, "Unable to validate organization")
    finally:
        z.close()
    if not any(str(o["organization_id"]) == payload.organization_id for o in allowed):
        raise HTTPException(403, "Organization is not authorized")
    i.organization_id = payload.organization_id
    i.status = "connected"
    db.commit()
    return {"ok": True}


@app.post(B + "/zoho/sync")
def sync(
    business_id, background: BackgroundTasks, user=Depends(owner), db=Depends(get_db)
):
    if not db.get(Integration, business_id):
        raise HTTPException(409, "Connect Zoho first")
    if any(
        j.kind == "zoho_sync" and j.status in ("queued", "running")
        for j in rows(db, Job, business_id)
    ):
        raise HTTPException(409, "A sync is already active")
    return schedule(db, Job(business_id=business_id, kind="zoho_sync"), background)

# -------------------------------------------------------------
# Module 4: Local Market Demand Intelligence Endpoints
# -------------------------------------------------------------
@app.get(B + "/local-demand")
@app.get(B + "/intelligence/local-demand")
def get_local_demand(business_id: str, user=Depends(access), db=Depends(get_db)):
    b = db.get(Business, business_id)
    if not b:
        raise HTTPException(404, "Business not found")
    return out(local_demand_analysis(db, b))


@app.post(B + "/local-demand/requests")
def create_unmet_demand(
    business_id: str, payload: UnmetDemandInput, background: BackgroundTasks, user=Depends(access), db=Depends(get_db)
):
    b = db.get(Business, business_id)
    if not b:
        raise HTTPException(404, "Business not found")
    req = UnmetDemandRequest(
        business_id=b.id,
        product_name=payload.product_name,
        brand=payload.brand,
        variant=payload.variant,
        category=payload.category,
        request_count=payload.request_count,
        requested_qty=payload.requested_qty,
        estimated_sell_price=payload.estimated_sell_price,
        customer_notes=payload.customer_notes,
        status=payload.status,
        request_date=payload.request_date or today(),
    )
    db.add(req)
    db.commit()
    audit(db, b.id, user.email, "create", "unmet_demand_request", {"product_name": req.product_name})
    background.add_task(
        manager.broadcast,
        b.id,
        RealtimeEvent(
            event_id=uid(),
            type="DEMAND_LOGGED",
            business_id=b.id,
            title="Customer Request Logged",
            message=f"Logged demand: {req.product_name} ({req.request_count} customer asks)",
            data={"id": req.id, "product_name": req.product_name, "request_count": req.request_count},
        ),
    )
    return out(plain(req), 201)


@app.patch(B + "/local-demand/requests/{req_id}")
def update_unmet_demand(
    business_id: str, req_id: str, payload: UnmetDemandUpdate, background: BackgroundTasks, user=Depends(access), db=Depends(get_db)
):
    b = db.get(Business, business_id)
    if not b:
        raise HTTPException(404, "Business not found")
    req = owned(db, UnmetDemandRequest, req_id, b.id)
    if payload.status is not None:
        req.status = payload.status
    if payload.request_count is not None:
        req.request_count = payload.request_count
    if payload.customer_notes is not None:
        req.customer_notes = payload.customer_notes
    db.commit()
    audit(db, b.id, user.email, "update", "unmet_demand_request", {"id": req.id, "status": req.status})
    background.add_task(
        manager.broadcast,
        b.id,
        RealtimeEvent(
            event_id=uid(),
            type="DEMAND_UPDATED",
            business_id=b.id,
            title="Customer Request Updated",
            message=f"{req.product_name} status is now {req.status}",
            data={"id": req.id, "status": req.status},
        ),
    )
    return out(plain(req))


@app.post(B + "/local-demand/signals")
def create_local_signal(
    business_id: str, payload: LocalMarketSignalInput, user=Depends(access), db=Depends(get_db)
):
    b = db.get(Business, business_id)
    if not b:
        raise HTTPException(404, "Business not found")
    sig = LocalMarketSignal(
        business_id=b.id,
        title=payload.title,
        category=payload.category,
        signal_type=payload.signal_type,
        source=payload.source,
        source_date=payload.source_date or today(),
        impact_multiplier=payload.impact_multiplier,
        notes=payload.notes,
    )
    db.add(sig)
    db.commit()
    audit(db, b.id, user.email, "create", "local_market_signal", {"title": sig.title})
    return out(plain(sig), 201)


# -------------------------------------------------------------
# Module 5: Profit Leak Detector Endpoint
# -------------------------------------------------------------
@app.get(B + "/profit-leaks")
@app.get(B + "/intelligence/profit-leaks")
def get_profit_leaks(business_id: str, user=Depends(access), db=Depends(get_db)):
    b = db.get(Business, business_id)
    if not b:
        raise HTTPException(404, "Business not found")
    return out(profit_leak_analysis(db, b))


# -------------------------------------------------------------
# Module 6: Grounded AI Business Assistant Endpoint
# -------------------------------------------------------------
@app.post(B + "/assistant/ask")
def ask_assistant(
    business_id: str, payload: AssistantQueryInput, user=Depends(access), db=Depends(get_db)
):
    b = db.get(Business, business_id)
    if not b:
        raise HTTPException(404, "Business not found")
    res = ai_assistant_query(db, b, payload.query, payload.language)
    return out(res)


# -------------------------------------------------------------
# Module 7: Unified Decision Engine & Negotiation Summary Endpoint
# -------------------------------------------------------------
@app.get(B + "/decision-engine")
def get_decision_engine(
    business_id: str, budget: float | None = None, user=Depends(access), db=Depends(get_db)
):
    b = db.get(Business, business_id)
    if not b:
        raise HTTPException(404, "Business not found")
    saved_budget = b.settings.get("purchasing_budget")
    eff_budget = None
    if budget is not None and budget > 0:
        eff_budget = Decimal(str(budget))
    elif saved_budget is not None and float(saved_budget) > 0:
        eff_budget = Decimal(str(saved_budget))

    if eff_budget is None:
        low_items = [s for s in inventory(db, b) if s.get("risk") != "healthy"]
        unmet = db.scalars(
            select(UnmetDemandRequest).where(UnmetDemandRequest.business_id == b.id)
        ).all()
        return out({
            "budget_configured": False,
            "running_low_count": len(low_items),
            "running_low_preview": [{"product": s["name"]} for s in low_items[:5]],
            "unmet_requests_count": len(unmet),
            "unmet_requests_preview": [{"product": u.product_name} for u in unmet[:5]],
            "budget": "0",
            "message": "No cash budget declared. Enter available purchasing budget to compute order quantities.",
        })

    res = unified_decision_summary(db, b, eff_budget)
    res["budget_configured"] = True
    return out(res)


# -------------------------------------------------------------
# Quick POS Sale Entry Endpoint (Real-Time Stock Deduction)
# -------------------------------------------------------------
@app.post(B + "/sales/quick-record")
async def quick_record_sale(
    business_id: str,
    payload: QuickSaleInput,
    background: BackgroundTasks,
    user=Depends(access),
    db=Depends(get_db),
):
    b = db.get(Business, business_id)
    if not b:
        raise HTTPException(404, "Business not found")

    products = rows(db, Product, b.id)
    p = next((x for x in products if x.name.lower() == payload.product_name.lower() or x.sku.lower() == payload.product_name.lower()), None)
    if not p:
        p = Product(
            business_id=b.id,
            name=payload.product_name,
            sku=uid()[:8].upper(),
            sell_price=payload.unit_price,
            pack_size=Decimal("1"),
            unit="unit",
            lead_time_days=2,
            review_period_days=7,
        )
        db.add(p)
        db.flush()

    tx = Transaction(
        business_id=b.id,
        source="pos",
        source_key=uid(),
        kind="sale",
        date=today(),
        total=payload.qty * payload.unit_price,
        raw={"note": f"Quick Sale ({payload.payment_mode}) - {payload.customer_notes}".strip(), "payment_mode": payload.payment_mode},
    )
    db.add(tx)
    db.flush()

    line = Line(
        business_id=b.id,
        transaction_id=tx.id,
        product_id=p.id,
        qty=payload.qty,
        unit_cost=payload.unit_price,
        cash_unit=payload.unit_price,
        discount=Decimal("0"),
        raw={"payment_mode": payload.payment_mode},
    )
    db.add(line)

    mov = Movement(
        business_id=b.id,
        product_id=p.id,
        qty=-payload.qty,
        kind="sale",
        reason="pos_sale",
        transaction_id=tx.id,
    )
    db.add(mov)
    db.commit()

    audit(db, b.id, user.email, "sale.recorded", "transaction", {"id": tx.id, "product": p.name, "qty": str(payload.qty), "price": str(payload.unit_price)})

    event = RealtimeEvent(
        event_id=uid(),
        type="STOCK_UPDATE",
        business_id=b.id,
        title="Live Retail Sale Recorded",
        message=f"Sold {payload.qty}x {p.name} for ₹{payload.qty * payload.unit_price:.2f} ({payload.payment_mode})",
        data={"transaction_id": tx.id, "product_id": p.id, "product_name": p.name, "qty": str(payload.qty), "total": str(payload.qty * payload.unit_price)},
    )
    background.add_task(manager.broadcast, b.id, event)

    return out({
        "status": "success",
        "message": f"Sale of {payload.qty}x {p.name} recorded in real-time.",
        "transaction_id": tx.id,
        "product_id": p.id,
        "product_name": p.name,
        "total_amount": str(payload.qty * payload.unit_price),
    }, 201)


# -------------------------------------------------------------
# Clean Slate / Reset Sample Data Endpoint
# -------------------------------------------------------------
@app.post(B + "/reset-data")
async def reset_business_data(
    business_id: str,
    background: BackgroundTasks,
    wipe_catalog: bool = False,
    user=Depends(access),
    db=Depends(get_db),
):
    b = db.get(Business, business_id)
    if not b:
        raise HTTPException(404, "Business not found")

    # Clean out transactional and demand records in foreign key order
    models_to_clear = [
        Line,
        Transaction,
        Movement,
        LostSale,
        OrderAttempt,
        InvoiceAllocation,
        GoodsReceipt,
        OrderLine,
        PurchaseOrder,
        RFQ,
        Payable,
        Payment,
        SupplierCredit,
        ApprovalRequest,
        Notification,
        Document,
        Receipt,
        UnmetDemandRequest,
        LocalMarketSignal,
    ]
    for model in models_to_clear:
        db.execute(delete(model).where(model.business_id == b.id))

    if wipe_catalog:
        for model in [Quote, Alias, Stock, BranchProduct, Product, Supplier]:
            db.execute(delete(model).where(model.business_id == b.id))
    else:
        # Reset stock on hand to zero and clear quotes
        db.execute(update(Stock).where(Stock.business_id == b.id).values(on_hand=Decimal("0")))
        db.execute(delete(Quote).where(Quote.business_id == b.id))

    db.commit()
    audit(db, b.id, user.email, "reset_data", "business", {"wipe_catalog": wipe_catalog})

    event = RealtimeEvent(
        event_id=uid(),
        type="DATA_RESET",
        business_id=b.id,
        title="Clean Slate Activated",
        message="All mock and sample transactions have been purged. System running with zero default data.",
        data={"wipe_catalog": wipe_catalog},
    )
    background.add_task(manager.broadcast, b.id, event)
    return out({
        "status": "success",
        "message": "Business data reset to clean slate. Ready for live input.",
        "wipe_catalog": wipe_catalog,
    })


# -------------------------------------------------------------
# Real-Time WebSocket Endpoint
# -------------------------------------------------------------
@app.websocket(PREFIX + "/ws/{business_id}")
async def realtime_ws_endpoint(websocket: WebSocket, business_id: str):
    await manager.connect(websocket, business_id)
    try:
        welcome = RealtimeEvent(
            event_id=uid(),
            type="SYSTEM_STATUS",
            business_id=business_id,
            title="Real-Time Connected",
            message="Live bi-directional synchronization active.",
            data={"status": "live", "server_time": now().isoformat()},
        )
        await websocket.send_json(welcome.model_dump())
        while True:
            raw = await websocket.receive_text()
            if raw == "ping":
                await websocket.send_text("pong")
            else:
                try:
                    payload = json.loads(raw)
                    if payload.get("type") == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": now().isoformat()})
                except Exception:
                    pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket, business_id)
    except Exception:
        await manager.disconnect(websocket, business_id)

