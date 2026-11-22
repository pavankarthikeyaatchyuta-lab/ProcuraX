from .db import today
from datetime import date as DateValue, datetime as DateTimeValue
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Login(Input):
    email: str
    password: str
    code: str = ""


class NewBusiness(Input):
    name: str = Field(min_length=2, max_length=120)


class Settings(Input):
    version: int
    lead_days: int = Field(3, ge=0, le=365)
    review_days: int = Field(7, ge=1, le=365)
    safety_days: int = Field(2, ge=0, le=365)
    max_cover: int = Field(30, ge=1, le=365)
    recoverable_gst: bool = True
    retention_days: int = Field(365, ge=1, le=3650)
    ocr_consent: bool = False
    minimum_reliability: float | None = Field(None, ge=0, le=1)


class ProductInput(Input):
    sku: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    brand: str = ""
    variant: str = ""
    size: str = ""
    unit: str = "unit"
    barcode: str = ""
    pack: Decimal = Field(Decimal(1), gt=0, decimal_places=4)
    sell_price: Decimal = Field(Decimal(0), ge=0)
    manual_demand: Decimal | None = Field(None, ge=0)
    storage_limit: Decimal | None = Field(None, gt=0)


class SupplierInput(Input):
    name: str = Field(min_length=1, max_length=200)
    gstin: str | None = Field(
        None, pattern=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$"
    )
    minimum_order: Decimal = Field(Decimal(0), ge=0)
    payment_terms: str = "Due on receipt"


class Tier(Input):
    min_qty: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)


class QuoteInput(Input):
    product_id: str
    supplier_id: str
    supplier_sku: str = ""
    unit_cost: Decimal = Field(gt=0)
    tax_pct: Decimal = Field(Decimal(0), ge=0, le=100)
    freight_unit: Decimal = Field(Decimal(0), ge=0)
    pack: Decimal = Field(Decimal(1), gt=0, decimal_places=4)
    moq: Decimal = Field(Decimal(1), gt=0)
    multiple: Decimal = Field(Decimal(1), gt=0, decimal_places=4)
    lead_days: int = Field(3, ge=0, le=365)
    valid_until: DateValue | None = None
    observed: DateValue = Field(default_factory=today)
    tiers: list[Tier] = Field(default_factory=list)
    tax_id: str | None = None


class PurchaseLine(Input):
    product_id: str
    raw_description: str = ""
    qty: Decimal = Field(gt=0)
    factor: Decimal = Field(Decimal(1), gt=0)
    unit: str = "unit"
    rate: Decimal = Field(ge=0)
    discount: Decimal = Field(Decimal(0), ge=0)
    tax_pct: Decimal = Field(Decimal(0), ge=0, le=100)
    freight: Decimal = Field(Decimal(0), ge=0)


class Review(Input):
    version: int
    supplier_id: str
    invoice_no: str = Field(min_length=1)
    date: DateValue
    total: Decimal = Field(gt=0)
    lines: list[PurchaseLine] = Field(min_length=1)
    order_id: str | None = None


class StockInput(Input):
    product_id: str
    qty: Decimal
    reserved: Decimal = Field(Decimal(0), ge=0)
    on_order: Decimal = Field(Decimal(0), ge=0)
    reason: str = Field(min_length=3, max_length=500)
    kind: Literal["opening", "adjustment", "count"] = "count"


class LostInput(Input):
    product_id: str | None = None
    category: str = ""
    qty: Decimal = Field(gt=0)
    date: DateValue = Field(default_factory=today)


class ReceiptInput(Input):
    supplier_id: str
    product_id: str
    basket_id: str | None = None
    ordered_on: DateValue
    expected: DateValue
    actual: DateValue
    ordered_qty: Decimal = Field(gt=0)
    received_qty: Decimal = Field(ge=0)
    actual_cost: Decimal | None = Field(None, gt=0)


class NewBasket(Input):
    budget: Decimal = Field(gt=0, le=Decimal("100000000"))


class BasketItem(Input):
    quote_id: str
    qty: Decimal = Field(gt=0)
    price_confirmed: bool = False


class BasketEdit(Input):
    version: int
    lines: list[BasketItem]
    feedback: str = ""


class Approval(Input):
    version: int
    action: Literal["approve", "reject", "create_zoho_drafts"]
    feedback: str = ""


class ImportCommit(Input):
    mapping: dict[str, str]


class AliasInput(Input):
    product_id: str
    text: str = Field(min_length=1)
    supplier_key: str = ""
    factor: Decimal = Field(Decimal(1), gt=0)


class SwitchMode(Input):
    mode: Literal["standalone", "zoho"]
    reason: str = Field(min_length=3)
    version: int
    opening: list[StockInput] = Field(min_length=1)


class MemberInput(Login):
    role: Literal["owner", "reviewer"] = "reviewer"


class MFA(Input):
    code: str


class OrganizationInput(Input):
    organization_id: str = Field(min_length=1, pattern=r"^\d+$")


class BankChange(Input):
    fingerprint: str = Field(min_length=4, max_length=200)
    verified: bool = False


class ProductView(ProductInput):
    id: str
    business_id: str
    source_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class QuoteView(QuoteInput):
    id: str
    business_id: str


class StockView(BaseModel):
    product_id: str
    sku: str
    name: str
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
    on_order: Decimal
    reconciliation_gap: Decimal | None
    updated: str | None
    stale: bool
    history_unknown: bool


class ForecastView(BaseModel):
    product_id: str
    name: str
    method: str
    model_version: str
    daily_demand: Decimal | None
    eligible: bool
    observed_days: int
    excluded_stockout_days: int
    unknown_availability_days: int
    uncertainty_daily_sd: float
    confidence: str
    backtests: dict[str, dict[str, float | None]]


class BasketLineView(BaseModel):
    quote_id: str
    product_id: str
    supplier_id: str
    name: str
    qty: Decimal
    unit_cost: Decimal
    cash_unit: Decimal
    cash_spend: Decimal
    benefit_estimate: Decimal
    explanation: str
    price_confirmed: bool


class BasketView(BaseModel):
    id: str
    business_id: str
    budget: Decimal
    status: str
    version: int
    lines: list[BasketLineView]
    snapshot: dict
    feedback: str
    created: DateTimeValue
    orders: list[dict] = Field(default_factory=list)


class UnmetDemandInput(Input):
    product_name: str = Field(min_length=1, max_length=200)
    brand: str = ""
    variant: str = ""
    category: str = "General"
    request_count: int = Field(1, ge=1)
    requested_qty: Decimal = Field(Decimal(1), gt=0)
    estimated_sell_price: Decimal | None = Field(None, ge=0)
    customer_notes: str = ""
    status: str = "logged"
    request_date: DateValue | None = None


class UnmetDemandUpdate(Input):
    status: str | None = None
    request_count: int | None = Field(None, ge=1)
    customer_notes: str | None = None


class LocalMarketSignalInput(Input):
    title: str = Field(min_length=1, max_length=200)
    category: str = "General"
    signal_type: str = "seasonal"
    source: str = "Local Observation"
    source_date: DateValue | None = None
    impact_multiplier: Decimal = Field(Decimal("1.2"), gt=0)
    notes: str = ""


class AssistantQueryInput(Input):
    query: str = Field(min_length=1, max_length=1000)
    language: str = "en"


class QuickSaleInput(Input):
    product_name: str = Field(min_length=1, max_length=200)
    qty: Decimal = Field(Decimal(1), gt=0)
    unit_price: Decimal = Field(..., gt=0)
    payment_mode: str = "cash"
    customer_notes: str = ""
