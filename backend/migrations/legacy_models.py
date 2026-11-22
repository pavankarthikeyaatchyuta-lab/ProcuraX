from datetime import date
from decimal import Decimal
from sqlalchemy import (
    String,
    Text,
    Numeric,
    DateTime,
    Date,
    Integer,
    Boolean,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db import uid, now, today
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


Money = Numeric(18, 4)


class Business(Base):
    __tablename__ = "businesses"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str]
    demo: Mapped[bool] = mapped_column(default=False)
    mode: Mapped[str] = mapped_column(default="standalone")
    settings: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "lead_days": 3,
            "review_days": 7,
            "safety_days": 2,
            "max_cover": 30,
            "recoverable_gst": True,
            "retention_days": 365,
            "ocr_consent": False,
        },
    )
    version: Mapped[int] = mapped_column(default=1)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    totp_secret: Mapped[str | None]
    mfa_enabled: Mapped[bool] = mapped_column(default=False)
    last_totp: Mapped[int] = mapped_column(default=0)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("business_id", "user_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str]


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    csrf: Mapped[str]
    expires: Mapped[object] = mapped_column(DateTime)
    mfa_verified: Mapped[bool] = mapped_column(default=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("business_id", "sku"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    sku: Mapped[str]
    name: Mapped[str]
    brand: Mapped[str] = mapped_column(default="")
    variant: Mapped[str] = mapped_column(default="")
    size: Mapped[str] = mapped_column(default="")
    unit: Mapped[str] = mapped_column(default="unit")
    barcode: Mapped[str] = mapped_column(default="")
    pack: Mapped[Decimal] = mapped_column(Money, default=1)
    sell_price: Mapped[Decimal] = mapped_column(Money, default=0)
    manual_demand: Mapped[Decimal | None] = mapped_column(Money)
    storage_limit: Mapped[Decimal | None] = mapped_column(Money)
    source_id: Mapped[str | None]
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class Alias(Base):
    __tablename__ = "aliases"
    __table_args__ = (UniqueConstraint("business_id", "supplier_key", "text"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    supplier_key: Mapped[str] = mapped_column(default="")
    text: Mapped[str]
    factor: Mapped[Decimal] = mapped_column(Money, default=1)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("business_id", "gstin"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    name: Mapped[str]
    gstin: Mapped[str | None]
    source_id: Mapped[str | None]
    bank_fingerprint: Mapped[str] = mapped_column(default="")
    minimum_order: Mapped[Decimal] = mapped_column(Money, default=0)
    payment_terms: Mapped[str] = mapped_column(default="Due on receipt")


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    supplier_sku: Mapped[str] = mapped_column(default="")
    # All amounts are per base unit; pack/MOQ/multiple quantities are base units.
    unit_cost: Mapped[Decimal] = mapped_column(Money)
    tax_pct: Mapped[Decimal] = mapped_column(Money, default=0)
    freight_unit: Mapped[Decimal] = mapped_column(Money, default=0)
    pack: Mapped[Decimal] = mapped_column(Money, default=1)
    moq: Mapped[Decimal] = mapped_column(Money, default=1)
    multiple: Mapped[Decimal] = mapped_column(Money, default=1)
    lead_days: Mapped[int] = mapped_column(default=3)
    valid_until: Mapped[date | None] = mapped_column(Date)
    observed: Mapped[date] = mapped_column(Date, default=today)
    tiers: Mapped[list] = mapped_column(JSON, default=list)
    tax_id: Mapped[str | None]


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("business_id", "sha256"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    name: Mapped[str]
    sha256: Mapped[str]
    mime: Mapped[str]
    path: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)
    versions: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(default=1)
    transaction_id: Mapped[str | None]
    created: Mapped[object] = mapped_column(DateTime, default=now)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("business_id", "source", "source_key"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    source: Mapped[str]
    source_key: Mapped[str]
    kind: Mapped[str]
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id"))
    invoice_no: Mapped[str] = mapped_column(default="")
    date: Mapped[date] = mapped_column(Date)
    total: Mapped[Decimal] = mapped_column(Money, default=0)
    active: Mapped[bool] = mapped_column(default=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(default=1)


class Line(Base):
    __tablename__ = "lines"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[Decimal] = mapped_column(Money)
    unit_cost: Mapped[Decimal] = mapped_column(Money)
    cash_unit: Mapped[Decimal] = mapped_column(Money)
    discount: Mapped[Decimal] = mapped_column(Money, default=0)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class Movement(Base):
    __tablename__ = "movements"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"))
    qty: Mapped[Decimal] = mapped_column(Money)
    kind: Mapped[str]
    reason: Mapped[str]
    reversal_of: Mapped[str | None] = mapped_column(ForeignKey("movements.id"))
    at: Mapped[object] = mapped_column(DateTime, default=now)


class Stock(Base):
    __tablename__ = "stock_snapshots"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    on_hand: Mapped[Decimal] = mapped_column(Money)
    reserved: Mapped[Decimal] = mapped_column(Money, default=0)
    on_order: Mapped[Decimal] = mapped_column(Money, default=0)
    source: Mapped[str]
    at: Mapped[object] = mapped_column(DateTime, default=now)


class LostSale(Base):
    __tablename__ = "lost_sales"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"))
    category: Mapped[str] = mapped_column(default="")
    qty: Mapped[Decimal] = mapped_column(Money)
    date: Mapped[date] = mapped_column(Date, default=today)


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    basket_id: Mapped[str | None]
    ordered_on: Mapped[date] = mapped_column(Date)
    expected: Mapped[date] = mapped_column(Date)
    actual: Mapped[date] = mapped_column(Date)
    ordered_qty: Mapped[Decimal] = mapped_column(Money)
    received_qty: Mapped[Decimal] = mapped_column(Money)
    actual_cost: Mapped[Decimal | None] = mapped_column(Money)


class Basket(Base):
    __tablename__ = "baskets"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    budget: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[str] = mapped_column(default="draft")
    version: Mapped[int] = mapped_column(default=1)
    lines: Mapped[list] = mapped_column(JSON, default=list)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    feedback: Mapped[str] = mapped_column(default="")
    created: Mapped[object] = mapped_column(DateTime, default=now)


class OrderAttempt(Base):
    __tablename__ = "order_attempts"
    __table_args__ = (UniqueConstraint("basket_id", "supplier_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    basket_id: Mapped[str] = mapped_column(ForeignKey("baskets.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    reference: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(default="pending")
    external_id: Mapped[str | None]
    error: Mapped[str] = mapped_column(default="")


class Integration(Base):
    __tablename__ = "integrations"
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id"), primary_key=True
    )
    region: Mapped[str] = mapped_column(default="in")
    refresh_token: Mapped[str] = mapped_column(default="")
    organization_id: Mapped[str] = mapped_column(default="")
    last_sync: Mapped[object | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(default="disconnected")
    gaps: Mapped[list] = mapped_column(JSON, default=list)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(default="")
    created: Mapped[object] = mapped_column(DateTime, default=now)


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    actor: Mapped[str]
    action: Mapped[str]
    target: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[object] = mapped_column(DateTime, default=now)


class LoginThrottle(Base):
    __tablename__ = "login_throttle"
    id: Mapped[str] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    until: Mapped[object] = mapped_column(DateTime)


class OAuthState(Base):
    __tablename__ = "oauth_states"
    id: Mapped[str] = mapped_column(primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    session_id: Mapped[str]
    region: Mapped[str]
    expires: Mapped[object] = mapped_column(DateTime)
