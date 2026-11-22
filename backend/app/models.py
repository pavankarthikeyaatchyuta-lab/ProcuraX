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
from .db import Base, uid, now, today

Money = Numeric(18, 4)


class BranchScoped:
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id"), index=True)


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


class Document(BranchScoped, Base):
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


class Transaction(BranchScoped, Base):
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


class Line(BranchScoped, Base):
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


class Movement(BranchScoped, Base):
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


class Stock(BranchScoped, Base):
    __tablename__ = "stock_snapshots"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    on_hand: Mapped[Decimal] = mapped_column(Money)
    reserved: Mapped[Decimal] = mapped_column(Money, default=0)
    on_order: Mapped[Decimal] = mapped_column(Money, default=0)
    source: Mapped[str]
    at: Mapped[object] = mapped_column(DateTime, default=now)


class LostSale(BranchScoped, Base):
    __tablename__ = "lost_sales"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"))
    category: Mapped[str] = mapped_column(default="")
    qty: Mapped[Decimal] = mapped_column(Money)
    date: Mapped[date] = mapped_column(Date, default=today)


class Receipt(BranchScoped, Base):
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


class Basket(BranchScoped, Base):
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


class OrderAttempt(BranchScoped, Base):
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


class Job(BranchScoped, Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(default="")
    created: Mapped[object] = mapped_column(DateTime, default=now)


class Audit(BranchScoped, Base):
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


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("business_id", "code"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    code: Mapped[str]
    name: Mapped[str]
    address: Mapped[str] = mapped_column(default="")
    budget: Mapped[Decimal] = mapped_column(Money, default=200000)
    committed: Mapped[Decimal] = mapped_column(Money, default=0)
    manager_limit: Mapped[Decimal] = mapped_column(Money, default=20000)
    zoho_location_id: Mapped[str | None]
    version: Mapped[int] = mapped_column(default=1)


class BranchGrant(Base):
    __tablename__ = "branch_grants"
    __table_args__ = (UniqueConstraint("branch_id", "user_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(default="reviewer")


class BranchProduct(Base):
    __tablename__ = "branch_products"
    __table_args__ = (UniqueConstraint("branch_id", "product_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    manual_demand: Mapped[Decimal | None] = mapped_column(Money)
    safety_days: Mapped[int | None]
    storage_limit: Mapped[Decimal | None] = mapped_column(Money)


class RFQ(BranchScoped, Base):
    __tablename__ = "rfqs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    number: Mapped[str]
    title: Mapped[str]
    deadline: Mapped[date] = mapped_column(Date)
    supplier_ids: Mapped[list] = mapped_column(JSON, default=list)
    lines: Mapped[list] = mapped_column(JSON, default=list)
    responses: Mapped[list] = mapped_column(JSON, default=list)
    awards: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default="open")
    version: Mapped[int] = mapped_column(default=1)
    created: Mapped[object] = mapped_column(DateTime, default=now)


class PurchaseOrder(BranchScoped, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("business_id", "number"),
        UniqueConstraint("business_id", "source_key"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    number: Mapped[str]
    source_key: Mapped[str]
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    basket_id: Mapped[str | None] = mapped_column(ForeignKey("baskets.id"))
    rfq_id: Mapped[str | None] = mapped_column(ForeignKey("rfqs.id"))
    status: Mapped[str] = mapped_column(default="draft")
    total: Mapped[Decimal] = mapped_column(Money, default=0)
    expected: Mapped[date] = mapped_column(Date)
    created_by: Mapped[str]
    note: Mapped[str] = mapped_column(default="")
    history: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(default=1)
    reserved_budget: Mapped[bool] = mapped_column(default=False)
    created: Mapped[object] = mapped_column(DateTime, default=now)


class OrderLine(BranchScoped, Base):
    __tablename__ = "order_lines"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"))
    qty: Mapped[Decimal] = mapped_column(Money)
    received: Mapped[Decimal] = mapped_column(Money, default=0)
    returned: Mapped[Decimal] = mapped_column(Money, default=0)
    cash_unit: Mapped[Decimal] = mapped_column(Money)
    economic_unit: Mapped[Decimal] = mapped_column(Money)
    allocations: Mapped[list] = mapped_column(JSON, default=list)


class GoodsReceipt(BranchScoped, Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (UniqueConstraint("business_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"))
    idempotency_key: Mapped[str]
    request_hash: Mapped[str]
    kind: Mapped[str] = mapped_column(default="receipt")
    lines: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(default="")
    created: Mapped[object] = mapped_column(DateTime, default=now)


class InvoiceAllocation(BranchScoped, Base):
    __tablename__ = "invoice_allocations"
    __table_args__ = (UniqueConstraint("order_line_id", "invoice_line_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    order_line_id: Mapped[str] = mapped_column(ForeignKey("order_lines.id"))
    invoice_line_id: Mapped[str] = mapped_column(ForeignKey("lines.id"))
    qty: Mapped[Decimal] = mapped_column(Money)
    stock_preposted: Mapped[Decimal] = mapped_column(Money, default=0)


class Payable(BranchScoped, Base):
    __tablename__ = "payables"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("transactions.id"), unique=True
    )
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    due: Mapped[date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(default=1)


class Payment(BranchScoped, Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("business_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    payable_id: Mapped[str] = mapped_column(ForeignKey("payables.id"))
    amount: Mapped[Decimal] = mapped_column(Money)
    date: Mapped[date] = mapped_column(Date, default=today)
    method: Mapped[str]
    reference: Mapped[str]
    idempotency_key: Mapped[str]
    request_hash: Mapped[str]


class SupplierCredit(BranchScoped, Base):
    __tablename__ = "supplier_credits"
    __table_args__ = (UniqueConstraint("business_id", "reference"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    payable_id: Mapped[str] = mapped_column(ForeignKey("payables.id"))
    return_id: Mapped[str] = mapped_column(ForeignKey("goods_receipts.id"))
    amount: Mapped[Decimal] = mapped_column(Money)
    reference: Mapped[str]
    date: Mapped[date] = mapped_column(Date, default=today)


class Transfer(BranchScoped, Base):
    __tablename__ = "transfers"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    destination_id: Mapped[str] = mapped_column(ForeignKey("branches.id"))
    number: Mapped[str]
    lines: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(default="requested")
    version: Mapped[int] = mapped_column(default=1)
    history: Mapped[list] = mapped_column(JSON, default=list)
    created: Mapped[object] = mapped_column(DateTime, default=now)


class ApprovalRequest(BranchScoped, Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id"))
    status: Mapped[str] = mapped_column(default="pending")
    requested_by: Mapped[str]
    decided_by: Mapped[str | None]
    reason: Mapped[str] = mapped_column(default="")
    created: Mapped[object] = mapped_column(DateTime, default=now)


class Notification(BranchScoped, Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("business_id", "fingerprint"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    fingerprint: Mapped[str]
    title: Mapped[str]
    detail: Mapped[str]
    href: Mapped[str]
    category: Mapped[str]
    read_by: Mapped[list] = mapped_column(JSON, default=list)
    created: Mapped[object] = mapped_column(DateTime, default=now)

class UnmetDemandRequest(BranchScoped, Base):
    __tablename__ = "unmet_demand_requests"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    product_name: Mapped[str]
    brand: Mapped[str] = mapped_column(default="")
    variant: Mapped[str] = mapped_column(default="")
    category: Mapped[str] = mapped_column(default="General")
    request_count: Mapped[int] = mapped_column(default=1)
    requested_qty: Mapped[Decimal] = mapped_column(Money, default=1)
    estimated_sell_price: Mapped[Decimal | None] = mapped_column(Money)
    customer_notes: Mapped[str] = mapped_column(default="")
    status: Mapped[str] = mapped_column(default="logged")
    request_date: Mapped[date] = mapped_column(Date, default=today)
    created: Mapped[object] = mapped_column(DateTime, default=now)


class LocalMarketSignal(BranchScoped, Base):
    __tablename__ = "local_market_signals"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    title: Mapped[str]
    category: Mapped[str] = mapped_column(default="General")
    signal_type: Mapped[str] = mapped_column(default="seasonal")
    source: Mapped[str] = mapped_column(default="Local Observation")
    source_date: Mapped[date] = mapped_column(Date, default=today)
    impact_multiplier: Mapped[Decimal] = mapped_column(Money, default=1.2)
    notes: Mapped[str] = mapped_column(default="")
    created: Mapped[object] = mapped_column(DateTime, default=now)

